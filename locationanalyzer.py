"""Analyze Accuracy, Stability and Latency of Wi-Fi client locations.

Implements the calculations from the RTLS Location Performance QA Runbook
(§5) against a single positions CSV produced by the `apistream` capture
(locationcsvwriter), joined with a ground-truth CSV of the real-world
locations of the Wi-Fi clients under test.

All math is done in the map Cartesian frame (meters) using only the standard
library — no pandas/numpy required.

  Accuracy  : per-sample distance to ground truth        -> avg/dev/p90/max
  Stability : per-sample drift about the device centroid -> avg/dev/p90/max
  Latency   : settle time after a device arrives at its
              ground-truth point (needs t_arrival)       -> avg/dev/p90/max
  Update interval (supporting): inter-arrival of samples -> avg/dev/p90/max
"""

import argparse
import csv
import datetime
import math
import statistics
import sys

SUPPORTED_DENSITIES = ("10m", "15m")

# Ground-truth CSV columns. t_arrival is optional per device: when present the
# device is treated as a latency DUT (moved to that point at t_arrival).
TRUTH_REQUIRED = ("device_mac", "x_true", "y_true")
TRUTH_OPTIONAL = ("t_arrival",)

# Positions CSV columns consumed from the capture.
POSITIONS_REQUIRED = ("ingest_ts", "device_mac", "x", "y")


class AnalysisError(Exception):
    """Fatal input/validation problem; message is user-facing."""


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Analyze Accuracy, Stability and Latency of Wi-Fi client "
                    "locations from a capture CSV (QA runbook §5).")
    parser.add_argument("positions_csv",
                        help="Capture CSV from apistream (wifi_client_locations_v1_*.csv)")
    parser.add_argument("--truth", required=True,
                        help="Ground-truth CSV: device_mac,x_true,y_true[,t_arrival]")
    parser.add_argument("--density", required=True, choices=SUPPORTED_DENSITIES,
                        help="AP density of this run; rows annotated with a "
                             "different density are rejected")
    parser.add_argument("--settle-tolerance", type=float, default=None,
                        help="Latency settle tolerance in meters "
                             "(default: the run's measured accuracy P90)")
    parser.add_argument("--settle-hold", type=int, default=2,
                        help="Consecutive in-tolerance samples required to "
                             "declare settled (default: %(default)s)")
    parser.add_argument("--min-samples", type=int, default=30,
                        help="Warn when a device has fewer samples than this "
                             "(default: %(default)s, per runbook §6.1)")
    return parser.parse_args()


def _parse_ts(value, context):
    """Parse an ISO-8601 timestamp (Z suffix allowed) to an aware datetime."""
    try:
        ts = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AnalysisError(f"{context}: invalid ISO-8601 timestamp {value!r}")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts


def _parse_float(value, context):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise AnalysisError(f"{context}: expected a number, got {value!r}")
    if not math.isfinite(result):
        raise AnalysisError(f"{context}: non-finite value {value!r}")
    return result


def _norm_mac(mac):
    return mac.strip().lower()


def load_truth(path):
    """Load ground truth keyed by normalized device MAC."""
    truth = {}
    try:
        fh = open(path, newline="", encoding="utf-8")
    except OSError as exc:
        raise AnalysisError(f"Cannot open ground-truth CSV: {exc}")
    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise AnalysisError(f"{path}: file is empty (no header row)")
        missing = [c for c in TRUTH_REQUIRED if c not in reader.fieldnames]
        if missing:
            raise AnalysisError(
                f"{path}: missing required column(s) {', '.join(missing)}; "
                f"expected header: {','.join(TRUTH_REQUIRED + TRUTH_OPTIONAL)}")
        for lineno, row in enumerate(reader, start=2):
            mac = _norm_mac(row.get("device_mac") or "")
            if not mac:
                raise AnalysisError(f"{path}:{lineno}: empty device_mac")
            if mac in truth:
                raise AnalysisError(f"{path}:{lineno}: duplicate device_mac {mac!r}")
            ctx = f"{path}:{lineno}"
            arrival_raw = (row.get("t_arrival") or "").strip()
            truth[mac] = {
                "x": _parse_float(row.get("x_true"), f"{ctx} x_true"),
                "y": _parse_float(row.get("y_true"), f"{ctx} y_true"),
                "t_arrival": _parse_ts(arrival_raw, f"{ctx} t_arrival")
                             if arrival_raw else None,
            }
    if not truth:
        raise AnalysisError(f"{path}: no ground-truth rows found")
    return truth


def load_positions(path, truth, density):
    """Load capture rows for known DUTs; returns samples keyed by MAC,
    each a time-sorted list of (ingest_ts, x, y)."""
    samples = {mac: [] for mac in truth}
    skipped_unknown = 0
    skipped_no_xy = 0
    density_mismatch = 0
    try:
        fh = open(path, newline="", encoding="utf-8")
    except OSError as exc:
        raise AnalysisError(f"Cannot open positions CSV: {exc}")
    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise AnalysisError(f"{path}: file is empty (no header row)")
        missing = [c for c in POSITIONS_REQUIRED if c not in reader.fieldnames]
        if missing:
            raise AnalysisError(
                f"{path}: missing required column(s) {', '.join(missing)}; "
                "is this a capture from apistream?")
        has_density = "density" in reader.fieldnames
        for lineno, row in enumerate(reader, start=2):
            mac = _norm_mac(row.get("device_mac") or "")
            if mac not in samples:
                skipped_unknown += 1
                continue
            if has_density:
                row_density = (row.get("density") or "").strip()
                if row_density and row_density != density:
                    density_mismatch += 1
                    continue
            x_raw, y_raw = (row.get("x") or "").strip(), (row.get("y") or "").strip()
            if not x_raw or not y_raw:
                skipped_no_xy += 1  # location not computable for this event
                continue
            ctx = f"{path}:{lineno}"
            samples[mac].append((
                _parse_ts(row.get("ingest_ts") or "", f"{ctx} ingest_ts"),
                _parse_float(x_raw, f"{ctx} x"),
                _parse_float(y_raw, f"{ctx} y"),
            ))
    for rows in samples.values():
        rows.sort(key=lambda s: s[0])
    total = sum(len(rows) for rows in samples.values())
    if total == 0:
        raise AnalysisError(
            f"{path}: no usable samples for any device in the ground-truth CSV "
            "(check device_mac values and the density label)")
    if density_mismatch:
        print(f"warning: skipped {density_mismatch} row(s) annotated with a "
              f"density other than {density}", file=sys.stderr)
    if skipped_no_xy:
        print(f"warning: skipped {skipped_no_xy} DUT row(s) without x/y "
              "(location not computed)", file=sys.stderr)
    if skipped_unknown:
        print(f"note: ignored {skipped_unknown} row(s) from devices not in the "
              "ground-truth CSV", file=sys.stderr)
    return samples


def percentile(values, pct):
    """Linear-interpolation percentile (matches numpy's default)."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    frac = rank - lower
    if lower + 1 >= len(ordered):
        return ordered[-1]
    return ordered[lower] * (1 - frac) + ordered[lower + 1] * frac


def stats(values):
    """avg / dev / p90 / max, or None when there is no data."""
    if not values:
        return None
    return {
        "avg": statistics.fmean(values),
        "dev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "p90": percentile(values, 90),
        "max": max(values),
    }


def accuracy_errors(samples, truth):
    """Runbook §5.1–5.2: per-sample distance to ground truth."""
    errors = {}
    for mac, rows in samples.items():
        xt, yt = truth[mac]["x"], truth[mac]["y"]
        errors[mac] = [math.hypot(x - xt, y - yt) for _, x, y in rows]
    return errors


def stability_drifts(samples):
    """Runbook §5.3: per-sample drift about the device's own centroid."""
    drifts = {}
    for mac, rows in samples.items():
        if not rows:
            drifts[mac] = []
            continue
        cx = statistics.fmean(x for _, x, _ in rows)
        cy = statistics.fmean(y for _, _, y in rows)
        drifts[mac] = [math.hypot(x - cx, y - cy) for _, x, y in rows]
    return drifts


def latency_seconds(samples, truth, tolerance, hold):
    """Runbook §5.4: settle time after arrival, per latency DUT.

    Returns (latencies, unsettled_macs). A device settles at the first sample
    after t_arrival that is within `tolerance` meters of ground truth and is
    followed by `hold`-1 further consecutive in-tolerance samples.
    """
    latencies = []
    unsettled = []
    for mac, rows in samples.items():
        arrival = truth[mac]["t_arrival"]
        if arrival is None:
            continue
        xt, yt = truth[mac]["x"], truth[mac]["y"]
        post = [(ts, x, y) for ts, x, y in rows if ts >= arrival]
        settled_at = None
        for i in range(len(post)):
            window = post[i:i + hold]
            if len(window) < hold:
                break
            if all(math.hypot(x - xt, y - yt) <= tolerance
                   for _, x, y in window):
                settled_at = post[i][0]
                break
        if settled_at is None:
            unsettled.append(mac)
        else:
            latencies.append((settled_at - arrival).total_seconds())
    return latencies, unsettled


def update_intervals(samples):
    """Runbook §5.5: inter-arrival times between consecutive samples."""
    deltas = []
    for rows in samples.values():
        deltas.extend(
            (rows[i][0] - rows[i - 1][0]).total_seconds()
            for i in range(1, len(rows)))
    return deltas


def print_table(title, unit, density, row_stats):
    print(f"\n### {title} ({unit})\n")
    print("| AP Density | Average | Deviation | 90th Percentile | Max |")
    print("| --- | --- | --- | --- | --- |")
    if row_stats is None:
        print(f"| {density.rstrip('m')} | n/a | n/a | n/a | n/a |")
    else:
        print(f"| {density.rstrip('m')} "
              f"| {row_stats['avg']:.2f} | {row_stats['dev']:.2f} "
              f"| {row_stats['p90']:.2f} | {row_stats['max']:.2f} |")


def print_per_device(title, per_device):
    print(f"\n#### {title} per device\n")
    print("| Device | Samples | Average | Deviation | 90th Percentile | Max |")
    print("| --- | --- | --- | --- | --- | --- |")
    for mac in sorted(per_device):
        s = stats(per_device[mac])
        if s is None:
            print(f"| {mac} | 0 | n/a | n/a | n/a | n/a |")
        else:
            print(f"| {mac} | {len(per_device[mac])} | {s['avg']:.2f} "
                  f"| {s['dev']:.2f} | {s['p90']:.2f} | {s['max']:.2f} |")


def main():
    args = parse_arguments()
    if args.settle_hold < 1:
        print("Error: --settle-hold must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.settle_tolerance is not None and args.settle_tolerance <= 0:
        print("Error: --settle-tolerance must be > 0", file=sys.stderr)
        sys.exit(1)

    try:
        truth = load_truth(args.truth)
        samples = load_positions(args.positions_csv, truth, args.density)
    except AnalysisError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Accuracy/Stability apply to stationary intervals only (§5.2–§5.3): for
    # moved devices, drop everything before t_arrival.
    metric_samples = {
        mac: rows if truth[mac]["t_arrival"] is None
        else [s for s in rows if s[0] >= truth[mac]["t_arrival"]]
        for mac, rows in samples.items()
    }

    for mac, rows in sorted(metric_samples.items()):
        if len(rows) < args.min_samples:
            print(f"warning: {mac} has only {len(rows)} sample(s) "
                  f"(< {args.min_samples}); statistics may be unstable",
                  file=sys.stderr)

    per_device_err = accuracy_errors(metric_samples, truth)
    all_errors = [e for errs in per_device_err.values() for e in errs]
    accuracy = stats(all_errors)

    per_device_drift = stability_drifts(metric_samples)
    stability = stats([d for ds in per_device_drift.values() for d in ds])

    tolerance = args.settle_tolerance
    if tolerance is None and accuracy is not None:
        tolerance = accuracy["p90"]
    latency_devices = [m for m in truth if truth[m]["t_arrival"] is not None]
    latencies, unsettled = ([], [])
    if latency_devices and tolerance is not None:
        latencies, unsettled = latency_seconds(
            samples, truth, tolerance, args.settle_hold)
    latency = stats(latencies)

    intervals = stats(update_intervals(samples))

    n_samples = len(all_errors)
    print(f"## Wi-Fi client location performance — AP density {args.density}")
    print(f"\nDevices analyzed: {len(samples)}  |  Samples: {n_samples}")

    print_table("Accuracy", "meters", args.density, accuracy)
    print_per_device("Accuracy", per_device_err)
    print_table("Stability", "meters", args.density, stability)
    print_per_device("Stability", per_device_drift)

    print_table("Latency", "seconds", args.density, latency)
    if latency_devices:
        print(f"\nSettle tolerance: {tolerance:.2f} m "
              f"({'user-specified' if args.settle_tolerance is not None else 'accuracy P90'}), "
              f"hold window: {args.settle_hold} sample(s), "
              f"moves measured: {len(latencies)}/{len(latency_devices)}")
        for mac in unsettled:
            print(f"warning: {mac} never settled within {tolerance:.2f} m of "
                  "its ground-truth point after t_arrival", file=sys.stderr)
    else:
        print("\n(no t_arrival values in the ground-truth CSV; "
              "latency not measured)")

    print_table("Update interval", "seconds", args.density, intervals)


if __name__ == "__main__":
    main()
