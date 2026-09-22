"""Append-only CSV sink for v1 WiFi client-location events.

Designed to be lightweight: every decoded location is written straight to disk
and flushed, so nothing is held in memory and the file stays a valid CSV even if
the process is killed mid-run (SIGINT/SIGTERM close it cleanly; a hard SIGKILL
still leaves a complete file up to the last flushed row because each row is
flushed as soon as it is written).
"""

import csv
import datetime
import os


# Only v1 WiFi client-location events are persisted by this writer.
WIFI_CLIENT_LOCATION_V1_TYPE = (
    "com.hpe.greenlake.network-services.v1.wifi-client-locations.created"
)

# Column order for the CSV. device_mac/error_level/reporting_ap_count map to the
# runbook's device_id/accuracy_radius/reporting_aps fields.
CSV_FIELDNAMES = [
    "ingest_ts",
    "event_ts",
    "run_id",
    "density",
    "event_type",
    "tenant_id",
    "customer_id",
    "device_mac",
    "x",
    "y",
    "latitude",
    "longitude",
    "error_level",
    "associated",
    "connected",
    "assoc_bssid",
    "site_id",
    "building_id",
    "floor_id",
    "reporting_ap_count",
    "reporting_ap_serials",
]


def _optional(message, field_name):
    """Return a proto3 optional field's value, or '' when it is not set."""
    try:
        if message.HasField(field_name):
            return getattr(message, field_name)
    except ValueError:
        # Field has no presence tracking; fall back to the raw value.
        return getattr(message, field_name)
    return ""


class LocationCsvWriter:
    """Streams v1 WiFi client-location rows to an append-only CSV file."""

    def __init__(self, output_dir="captures", run_id="", density="",
                 filename_prefix="wifi_client_locations_v1"):
        self.run_id = run_id
        self.density = density
        os.makedirs(output_dir, exist_ok=True)

        # Human-readable local timestamp so multiple captures sort and read
        # naturally, e.g. wifi_client_locations_v1_2026-09-21_14-36-31.csv
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.path = os.path.join(output_dir, f"{filename_prefix}_{stamp}.csv")

        # Line-buffered text handle: each completed row is pushed to the OS as
        # soon as its newline is written, keeping the file consistent on kill.
        self._fh = open(self.path, "a", newline="", buffering=1, encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=CSV_FIELDNAMES)
        if self._fh.tell() == 0:
            self._writer.writeheader()
            self._fh.flush()
        self.rows_written = 0
        self._closed = False

    def write_wifi_location(self, event, stream_message):
        """Extract a WifiClientLocation from a decoded v1 envelope and persist it.

        `event` is the CloudEvent, `stream_message` the parsed
        StreamLocationMessage. Returns True when a row was written.
        """
        if self._closed:
            return False
        if stream_message.WhichOneof("location_event") != "wifi_client_location":
            return False

        loc = stream_message.wifi_client_location

        ingest_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        event_ts = ""
        if event.HasField("time"):
            event_ts = event.time.ToDatetime(
                tzinfo=datetime.timezone.utc
            ).isoformat()

        customer_id = ""
        subject = event.attributes.get("subject")
        if subject is not None:
            customer_id = subject.ce_string

        row = {
            "ingest_ts": ingest_ts,
            "event_ts": event_ts,
            "run_id": self.run_id,
            "density": self.density,
            "event_type": event.type,
            "tenant_id": _optional(stream_message, "tenant_id"),
            "customer_id": customer_id,
            "device_mac": _optional(loc, "sta_eth_mac"),
            "x": _optional(loc, "x"),
            "y": _optional(loc, "y"),
            "latitude": _optional(loc, "latitude"),
            "longitude": _optional(loc, "longitude"),
            "error_level": _optional(loc, "error_level"),
            "associated": _optional(loc, "associated"),
            "connected": _optional(loc, "connected"),
            "assoc_bssid": _optional(loc, "assoc_bssid"),
            "site_id": _optional(loc, "site_id"),
            "building_id": _optional(loc, "building_id"),
            "floor_id": _optional(loc, "floor_id"),
            "reporting_ap_count": len(loc.reporting_ap_serial),
            "reporting_ap_serials": ";".join(loc.reporting_ap_serial),
        }

        self._writer.writerow(row)
        self._fh.flush()
        self.rows_written += 1
        return True

    def close(self):
        """Flush and close the file; safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        try:
            self._fh.flush()
            os.fsync(self._fh.fileno())
        except (OSError, ValueError):
            pass
        finally:
            self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
