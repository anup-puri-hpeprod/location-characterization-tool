# CNX API Streaming Test

A Python client for streaming API events from HPE GreenLake Network Services. This project provides real-time streaming of network events including WiFi client locations, WIDS (Wireless Intrusion Detection System) rules, and signatures through WebSocket connections.

## Features

- **Real-time Event Streaming**: Connect to HPE GreenLake Network Services via WebSocket
- **OAuth2 Authentication**: Secure authentication using client credentials flow
- **Protocol Buffer Support**: Efficient binary serialization for network events
- **Multiple Event Types**: Support for WIDS rules, WIDS signatures, and WiFi client location events
- **Configurable**: Command-line arguments and environment variable support

## Supported Event Types

- `com.hpe.greenlake.network-services.v1alpha1.wids-rules`
- `com.hpe.greenlake.network-services.v1alpha1.wids-signatures` 
- `com.hpe.greenlake.network-services.v1alpha1.wifi-client-locations.created`
- `com.hpe.greenlake.network-services.v1alpha1.asset-tags.last-known-location.created`
- `com.hpe.greenlake.network-services.v1alpha1.asset-tag-geofence-crossed`

## Requirements

- Python 3.8+
- Poetry (for dependency management)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cnx-api-streaming-test
```

2. Install dependencies using Poetry:
```bash
poetry install
```
This also registers the console-script entry points (`apistream` and `fetch-token`) inside the Poetry virtual environment.

3. Activate the virtual environment:
```bash
poetry shell
```

4. Configure your credentials and endpoints (see [Configuration](#configuration)):
```bash
cp .env.example .env
# edit .env — paste the Token Issuer URL from the GreenLake Cloud Platform
```

## Configuration

The application reads its settings from environment variables. You can provide them in three ways (highest precedence first): command-line flags, exported shell variables, or a `.env` file that the scripts auto-load.

### Settings

| Variable | Flag | Description |
|----------|------|-------------|
| `CNX_CLIENT_ID` | `--client-id` | OAuth2 API client ID (from GreenLake) |
| `CNX_CLIENT_SECRET` | `--client-secret` | OAuth2 API client secret (from GreenLake) |
| `CNX_TOKEN_URL` | `--token-url` | Token issuer (SSO) URL — **environment-specific, see note below** |
| `CNX_WEBSOCKET_URL` | `--websocket-url` | CNX API gateway websocket host for the target cluster |
| (n/a) | `--endpoint` | Websocket subscription path, e.g. `/network-services/v1/location-events` |

> **Where to get the Token Issuer URL:** it is **not** always production SSO. Look it up on the **GreenLake Cloud Platform** — create/open your API client under **Manage → API / Personal API Clients** and copy the **Token Issuer URL** shown there, verbatim. It must come from the account/tenant that owns your target environment.
>
> Examples:
> - Production: `https://sso.common.cloud.hpe.com/as/token.oauth2`
> - evian3 (QA): `https://pavo-sso.common.cloud.hpe.com/as/token.oauth2`
>
> The websocket host follows the pattern `wss://cnx-apigw-<cluster>.arubadev.cloud.hpe.com` (e.g. `cnx-apigw-evian3...`, `cnx-apigw-aqua...`).

### Using a .env file (recommended)

Copy the template and fill in your values once — the scripts load `.env` automatically, so you don't need to re-export anything per shell:

```bash
cp .env.example .env
# edit .env with your client id/secret, token issuer URL, and cluster websocket host
```

The same `.env` is also source-able for shell/curl workflows:

```bash
set -a; source .env; set +a
```

### Exported environment variables

```bash
export CNX_CLIENT_ID="your-client-id"
export CNX_CLIENT_SECRET="your-client-secret"
# Token Issuer URL — copy from GreenLake Cloud Platform (environment-specific)
export CNX_TOKEN_URL="https://pavo-sso.common.cloud.hpe.com/as/token.oauth2"
export CNX_WEBSOCKET_URL="wss://cnx-apigw-evian3.arubadev.cloud.hpe.com"
```

### Command Line Arguments

```bash
poetry run apistream \
  --client-id <your-client-id> \
  --client-secret <your-client-secret> \
  --token-url <token-issuer-url-from-greenlake> \
  --websocket-url <cluster-websocket-url> \
  --endpoint <websocket-endpoint-path>
```

## Usage

### Console Scripts (recommended)

After `poetry install`, two entry points are available in the Poetry environment:

| Command | Runs | Purpose |
|---------|------|---------|
| `apistream` | `apistreamingtest:main` | Connect and stream/decode events |
| `fetch-token` | `apitokenfetcher:main` | Fetch and print an OAuth2 token only |
| `analyze-locations` | `locationanalyzer:main` | Analyze Accuracy/Stability/Latency from a capture CSV |

First, verify your credentials and token issuer URL resolve to a token:
```bash
poetry run fetch-token
```

Then start streaming (location/asset-tag/geofence events):
```bash
poetry run apistream --endpoint "/network-services/v1/location-events"
```

If you have activated the environment with `poetry shell`, you can drop the `poetry run` prefix:
```bash
apistream --endpoint "/network-services/v1/location-events"
```

See all options with `poetry run apistream --help`.

### Basic Usage

With configuration in `.env` or exported:
```bash
poetry run apistream --endpoint "/network-services/v1/location-events"
```

Both `v1` and `v1alpha1` location/geofence routes are supported (their payloads have
different wire layouts and are decoded with version-matched Protobuf modules):

| Endpoint | Events |
| --- | --- |
| `/network-services/v1/location-events` | v1 wifi-client & asset-tag locations |
| `/network-services/v1/geofence-events` | v1 wifi-client & asset-tag geofence crossings |
| `/network-services/v1alpha1/location` | v1alpha1 wifi-client & asset-tag locations |
| `/network-services/v1alpha1/geofence` | v1alpha1 wifi-client & asset-tag geofence crossings |
| `/network-services/v1alpha1/wids` | WIDS rules & signatures |

### Full Command Line Usage

```bash
poetry run apistream \
  --client-id "your-client-id" \
  --client-secret "your-client-secret" \
  --token-url "https://pavo-sso.common.cloud.hpe.com/as/token.oauth2" \
  --websocket-url "wss://cnx-apigw-evian3.arubadev.cloud.hpe.com" \
  --endpoint "/network-services/v1/location-events"
```

### Capturing v1 WiFi client locations to CSV

When streaming the v1 location route, every
`com.hpe.greenlake.network-services.v1.wifi-client-locations.created` event is
appended to a CSV under `captures/` (override with `--csv-dir`). Each capture
file is created exclusively, named with the AP density and a human-readable
local timestamp (microsecond precision), e.g.
`captures/wifi_client_locations_v1_10m_2026-09-21_14-36-31_512430.csv`.

`--density` is **required** when CSV capture is enabled (choose `10m` or
`15m`): it becomes part of the capture filename, every row is annotated with
it, and the analysis script uses it to group and validate results per AP
density. Pass `--no-csv` if you only want console decoding.

`--duration <minutes>` (integer > 0) makes the run self-terminating: after the
given number of minutes the stream disconnects and the CSV is flushed and
closed cleanly. Omit it to run until `Ctrl-C`.

The writer is intentionally lightweight: each decoded location is written and
flushed straight to disk (nothing is buffered in memory), so the file stays a
valid CSV even if the process is killed mid-run. `Ctrl-C` (SIGINT) and `kill`
(SIGTERM) close the file cleanly; a hard `kill -9` (SIGKILL) still leaves a
complete file up to the last flushed row.

```bash
# 30-minute accuracy run at 10 m density (per the QA runbook §6.1)
poetry run apistream \
  --endpoint "/network-services/v1/location-events" \
  --run-id R001 --density 10m --duration 30 --csv-dir captures

# Open-ended run (stop with Ctrl-C), e.g. overnight stability capture
poetry run apistream \
  --endpoint "/network-services/v1/location-events" \
  --run-id R002 --density 15m

# Disable CSV capture (console decode only; --density not needed)
poetry run apistream --endpoint "/network-services/v1/location-events" --no-csv
```

Columns: `ingest_ts, event_ts, run_id, density, event_type, tenant_id,
customer_id, device_mac, x, y, latitude, longitude, error_level, associated,
connected, assoc_bssid, site_id, building_id, floor_id, reporting_ap_count,
reporting_ap_serials`.

### Analyzing Accuracy, Stability and Latency

`analyze-locations` implements the QA-runbook calculations (§5) against a
single capture CSV and prints Meridian-style result tables for the AP density
under test. It needs two inputs:

1. the **positions CSV** produced by `apistream` (above), and
2. a **ground-truth CSV** with the real-world location of every Wi-Fi client
   under test, in map Cartesian meters.

#### Ground-truth CSV format

```csv
device_mac,x_true,y_true,t_arrival
aa:bb:cc:00:11:22,42.5,31.0,
aa:bb:cc:00:33:44,10.0,25.5,
aa:bb:cc:00:55:66,58.2,12.7,2026-09-21T14:05:30Z
```

- `device_mac` — client MAC as it appears in the capture (case-insensitive).
- `x_true`, `y_true` — surveyed position in meters (runbook §2.5).
- `t_arrival` — optional ISO-8601 timestamp; set it only for devices that were
  **moved** to `(x_true, y_true)` during the run. Devices with a `t_arrival`
  feed the Latency metric (settle time after arrival, §5.4); leave it empty
  for stationary Accuracy/Stability devices.

#### Running the analysis

```bash
poetry run analyze-locations \
  captures/wifi_client_locations_v1_10m_2026-09-21_14-36-31_512430.csv \
  --truth ground_truth.csv \
  --density 10m
```

Options:

| Flag | Meaning |
| --- | --- |
| `--density {10m,15m}` | AP density of the run (required). Rows annotated with a different density are skipped with a warning. |
| `--settle-tolerance <m>` | Latency settle tolerance in meters. Default: the run's measured accuracy P90 (§5.4). |
| `--settle-hold <n>` | Consecutive in-tolerance samples required to declare a device settled (default 2). |
| `--min-samples <n>` | Warn when a device has fewer samples than this (default 30, §6.1). |

#### Output

Markdown tables per metric, aggregated across all devices at the density, in
the runbook's reporting format — plus a per-device breakdown and the
supporting update-interval table:

```
## Wi-Fi client location performance — AP density 10m

Devices analyzed: 3  |  Samples: 412

### Accuracy (meters)

| AP Density | Average | Deviation | 90th Percentile | Max |
| --- | --- | --- | --- | --- |
| 10 | 3.12 | 1.45 | 5.02 | 8.91 |

### Stability (meters)
...

### Latency (seconds)
...

### Update interval (seconds)
...
```

Calculations follow the runbook: **Accuracy** is the per-sample Euclidean
distance to ground truth (§5.1–5.2); **Stability** is per-sample drift about
each device's own computed centroid (§5.3); **Latency** is the time from
`t_arrival` until the first sample that stays within the settle tolerance for
the hold window (§5.4); **Update interval** is the inter-arrival time between
consecutive samples (§5.5). For moved devices (those with a `t_arrival`),
only samples **after** arrival count toward Accuracy and Stability, matching
the runbook's stationary-device requirement.

Error handling: the script exits non-zero with a clear message on missing or
malformed files, missing columns, bad numbers/timestamps, duplicate or empty
MACs, and when no capture rows match the ground-truth devices. It warns (but
continues) on rows without a computed position, density mismatches,
under-sampled devices, and latency devices that never settle.

### Using the Client Library

```python
from apistreamingclient import ApiStreamingClient

# Initialize the client
client = ApiStreamingClient(websocket_url, access_token)

# Create WebSocket connection and start streaming
client.create_ws_connection_with_client_decoding(access_token, endpoint)
```

## Project Structure

```
├── apistreamingclient.py     # Main streaming client class
├── apistreamingtest.py       # CLI application and example usage (apistream)
├── apitokenfetcher.py        # OAuth2 token fetcher + .env loader (fetch-token)
├── locationcsvwriter.py      # Append-only CSV sink for v1 WiFi client locations
├── locationanalyzer.py       # Accuracy/Stability/Latency analysis (analyze-locations)
├── .env.example              # Configuration template (copy to .env)
├── protobuf/                    # Protocol Buffer generated files
│   ├── __init__.py             # Package initialization
│   ├── event_pb2.py            # CloudEvent envelope classes
│   ├── location_v1_pb2.py      # v1 location classes (StreamLocationMessage)
│   ├── location_v1alpha1_pb2.py # v1alpha1 location classes
│   ├── geofence_v1_pb2.py      # v1 geofence classes (StreamGeofenceMessage)
│   ├── geofence_v1alpha1_pb2.py # v1alpha1 geofence classes
│   └── wids_pb2.py             # WIDS rules/signatures classes
├── pyproject.toml           # Poetry configuration and dependencies
└── README.md                # This file
```

## Dependencies

- `websocket-client`: WebSocket client library
- `requests-oauthlib`: OAuth2 authentication
- `oauthlib`: OAuth2 protocol implementation
- `protobuf`: Protocol Buffer support

## Event Processing

The client automatically:

1. **Authenticates** using OAuth2 client credentials flow
2. **Connects** to the WebSocket endpoint
3. **Receives** binary Protocol Buffer messages
4. **Decodes** events based on their type
5. **Displays** event information and decoded data

Events are classified as UDP (< 32KB) or GRPC (≥ 32KB) based on their size.

## Error Handling

The client handles:
- WebSocket connection errors
- Authentication failures
- Protocol Buffer parsing errors
- Graceful shutdown on Ctrl-C

## Development

### Prerequisites

- Python 3.8+
- Poetry

### Setup Development Environment

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Protocol Buffer Files

The Protocol Buffer files (`*_pb2.py`) are located in the `protobuf/` directory and are
generated from the `.proto` definitions in the `api-streaming-proto` module
(`apigw-common-libs/api-streaming-proto/src/main/proto/payloads/network-services`).
Never hand-edit them — they are marked `DO NOT EDIT`.

**Important:** the `protoc` version must match the installed `protobuf` runtime
(`poetry run python -c "import google.protobuf; print(google.protobuf.__version__)"`).
For the `5.29.x` runtime use a standalone **protoc 29.x** (libprotoc `29.x`). A newer
Homebrew `protoc` (libprotoc `30+`) emits gencode that refuses to load against a 5.x
runtime, and `grpcio-tools` does not build on Python 3.14.

Because `v1` and `v1alpha1` define a `StreamLocationMessage`/`StreamGeofenceMessage`
with different field numbers, each version is staged under a distinct filename so the
Protobuf descriptor pool keeps them separate:

```bash
# 1. Get a matching standalone protoc (example: 29.3 on Apple Silicon)
curl -fsSL -o /tmp/protoc.zip \
  https://github.com/protocolbuffers/protobuf/releases/download/v29.3/protoc-29.3-osx-aarch_64.zip
unzip -q -o /tmp/protoc.zip -d /tmp/protoc29

# 2. Stage version-specific proto filenames
NS=../apigw-common-libs/api-streaming-proto/src/main/proto/payloads/network-services
mkdir -p /tmp/protostage
cp "$NS/v1/location.proto"        /tmp/protostage/location_v1.proto
cp "$NS/v1alpha1/location.proto" /tmp/protostage/location_v1alpha1.proto
cp "$NS/v1/geofence.proto"        /tmp/protostage/geofence_v1.proto
cp "$NS/v1alpha1/geofence.proto" /tmp/protostage/geofence_v1alpha1.proto
cp "$NS/v1alpha1/wids.proto"      /tmp/protostage/wids.proto

# 3. Generate the Python classes
/tmp/protoc29/bin/protoc -I /tmp/protostage --python_out=protobuf \
  location_v1.proto location_v1alpha1.proto \
  geofence_v1.proto geofence_v1alpha1.proto wids.proto
```

## License

This project is part of HPE GreenLake Network Services development and testing.

## Support

For issues and questions related to HPE GreenLake Network Services API, please refer to the official HPE documentation or contact support.
