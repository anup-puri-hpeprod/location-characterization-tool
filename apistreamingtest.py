from apitokenfetcher import ApiTokenFetcher, load_env_file
import argparse
import os
import sys
from apistreamingclient import ApiStreamingClient

def parse_arguments():
    """Parse command line arguments with environment variable fallbacks."""
    parser = argparse.ArgumentParser(description='API Streaming Client for CNX events')

    parser.add_argument('--client-id',
                       help='OAuth2 client ID (default: from CNX_CLIENT_ID env var)')
    parser.add_argument('--client-secret',
                       help='OAuth2 client secret (default: from CNX_CLIENT_SECRET env var)')
    parser.add_argument('--token-url',
                       help='OAuth2 token URL (default: from CNX_TOKEN_URL env var)')
    parser.add_argument('--websocket-url',
                       help='WebSocket URL (default: from CNX_WEBSOCKET_URL env var)')
    parser.add_argument('--endpoint',
                       help='WebSocket endpoint path (default: %(default)s)')

    args = parser.parse_args()

    load_env_file()

    # Get values from arguments or environment variables
    client_id = args.client_id or os.getenv('CNX_CLIENT_ID')
    client_secret = args.client_secret or os.getenv('CNX_CLIENT_SECRET')
    token_url = args.token_url or os.getenv('CNX_TOKEN_URL')
    websocket_url = args.websocket_url or os.getenv('CNX_WEBSOCKET_URL')

    # Check for missing required values
    missing_vars = []
    if not client_id:
        missing_vars.append('--client-id or CNX_CLIENT_ID')
    if not client_secret:
        missing_vars.append('--client-secret or CNX_CLIENT_SECRET')
    if not token_url:
        missing_vars.append('--token-url or CNX_TOKEN_URL')
    if not websocket_url:
        missing_vars.append('--websocket-url or CNX_WEBSOCKET_URL')
    if not args.endpoint:
        missing_vars.append('--endpoint')

    if missing_vars:
        print("Error: Missing required configuration:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nExample usage:")
        print("  python apistreamingtest.py --client-id <id> --client-secret <secret> --token-url <url> --websocket-url <ws_url> --endpoint <ws_endpoint>")
        print("\nOr set environment variables:")
        print("  export CNX_CLIENT_ID=<id>")
        print("  export CNX_CLIENT_SECRET=<secret>")
        print("  export CNX_TOKEN_URL=<url>")
        print("  export CNX_WEBSOCKET_URL=<ws_url>")
        sys.exit(1)

    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'token_url': token_url,
        'websocket_url': websocket_url,
        'endpoint': args.endpoint
    }

def main():
    """Main function to run the API streaming client."""
    config = parse_arguments()

    # Fetch API token using the new class
    token_fetcher = ApiTokenFetcher(
        config['client_id'],
        config['client_secret'],
        config['token_url']
    )
    try:
        token = token_fetcher.fetch_token()
        print(f"Successfully obtained access token")

        # Create API streaming client
        streaming_client = ApiStreamingClient(config['websocket_url'], token)

        print(f"Connecting to {config['websocket_url']}{config['endpoint']}")
        ws = streaming_client.create_ws_connection_with_client_decoding(token, config['endpoint'])

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
