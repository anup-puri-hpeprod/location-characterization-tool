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
