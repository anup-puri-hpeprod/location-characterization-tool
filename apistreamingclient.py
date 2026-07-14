from typing import Optional, Type
from websocket import create_connection
import ssl
import websocket
from typing import TypedDict
from websocket._exceptions import WebSocketBadStatusException

# Load the Protobuf message definitions.
# Location and geofence payloads differ between API versions (v1 carries a
# tenant_id and shifts the oneof field numbers), so each version has its own
# generated module and must be decoded with the matching one.
from protobuf import (
    event_pb2,
    location_v1_pb2,
    location_v1alpha1_pb2,
    geofence_v1_pb2,
    geofence_v1alpha1_pb2,
    wids_pb2,
)

class EventTypeDecoder(TypedDict):
    top_level_decoder: Type
    # Field of the parsed envelope to surface. When None, the entire top-level
    # message is shown (e.g. location events, so the v1 tenant_id is visible).
    sub_msg_field: Optional[str]


# Keyed by the full, version-specific CloudEvent type. v1 and v1alpha1 are NOT
# collapsed because their wire layouts differ and must be parsed with the
# version-matched message class.
event_type_decoders: dict[str, EventTypeDecoder] = {
    # network-services v1
    "com.hpe.greenlake.network-services.v1.wifi-client-locations.created": {"top_level_decoder": location_v1_pb2.StreamLocationMessage, "sub_msg_field": None},
    "com.hpe.greenlake.network-services.v1.asset-tags.last-known-location.created": {"top_level_decoder": location_v1_pb2.StreamLocationMessage, "sub_msg_field": None},
    "com.hpe.greenlake.network-services.v1.wifi-client-geofence-crossed": {"top_level_decoder": geofence_v1_pb2.StreamGeofenceMessage, "sub_msg_field": "wifi_client_geofence"},
    "com.hpe.greenlake.network-services.v1.asset-tag-geofence-crossed": {"top_level_decoder": geofence_v1_pb2.StreamGeofenceMessage, "sub_msg_field": "asset_tag_geofence"},
    # network-services v1alpha1
    "com.hpe.greenlake.network-services.v1alpha1.wifi-client-locations.created": {"top_level_decoder": location_v1alpha1_pb2.StreamLocationMessage, "sub_msg_field": None},
    "com.hpe.greenlake.network-services.v1alpha1.asset-tags.last-known-location.created": {"top_level_decoder": location_v1alpha1_pb2.StreamLocationMessage, "sub_msg_field": None},
    "com.hpe.greenlake.network-services.v1alpha1.wifi-client-geofence-crossed": {"top_level_decoder": geofence_v1alpha1_pb2.StreamGeofenceMessage, "sub_msg_field": "wifi_client_geofence"},
    "com.hpe.greenlake.network-services.v1alpha1.asset-tag-geofence-crossed": {"top_level_decoder": geofence_v1alpha1_pb2.StreamGeofenceMessage, "sub_msg_field": "asset_tag_geofence"},
    "com.hpe.greenlake.network-services.v1alpha1.wids-rules.detection.created": {"top_level_decoder": wids_pb2.WidsStreamMessage, "sub_msg_field": "wids_rules_event"},
    "com.hpe.greenlake.network-services.v1alpha1.wids-signatures.detection.created": {"top_level_decoder": wids_pb2.WidsStreamMessage, "sub_msg_field": "wids_signatures_event"},
}

class ApiStreamingClient:
    def __init__(self, cnx_ws_url, access_token):
        self.cnx_ws_url = cnx_ws_url
        self.access_token = access_token

    def decode_stream_event(self, event, proto):
        """Decode the stream event."""
        print(f"Event type: {event.type}")
        subject_customer_id = event.attributes['subject'].ce_string
        print(event)
        decoder_info = event_type_decoders.get(event.type)
        if decoder_info is None:
            decoded_event = f"Unhandled event type: {event.type} via {proto}"
        else:
            message_class = decoder_info["top_level_decoder"]
            try:
                top_level_message = message_class()
                top_level_message.ParseFromString(event.proto_data.value)
                sub_msg_field = decoder_info["sub_msg_field"]
                if sub_msg_field is None:
                    # Surface the whole envelope (e.g. location events) so fields
                    # like the v1 tenant_id are visible alongside the payload.
                    decoded_event = top_level_message
                else:
                    decoded_event = getattr(top_level_message, sub_msg_field)
            except Exception as e:
                print(f"Error decoding event: {e}")
                decoded_event = f"Error decoding event: {e}"

        print("Decoded Event:")
        print("==============")
        print(decoded_event)

    def create_ws_connection(self, access_token, end_point, header_param=None):
        if header_param is None:
            headers = {"Authorization": "Bearer {}".format(access_token)}
        else:
            headers = header_param
        url = self.cnx_ws_url + end_point
        res = create_connection(url, header=headers, sslopt={"cert_reqs": ssl.CERT_NONE})
        return res

    def create_ws_connection_with_client_decoding(self, access_token, end_point, header_param=None):
        if header_param is None:
            headers = {"Authorization": "Bearer {}".format(access_token)}
        else:
            headers = header_param
        url = self.cnx_ws_url + end_point
        ws = create_connection(url, header=headers, sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=30)
        print("ws connected")
        total = 6
        try:
            while True:
                message = ws.recv()
                print("Message recvd")
                
                # Handle non-binary messages
                if not isinstance(message, bytes):
                    if isinstance(message, str):
                        # cases like keepalive/ping messages
                        print(f"Received text frame: {message}")
                    else:
                        print(f"Received unexpected message type {type(message)}: {message}")
                    continue
                
                event = event_pb2.CloudEvent()
                event.ParseFromString(message)
                event_kb_size = event.ByteSize() / 1024
                if event_kb_size < 32:
                    event_proto = 'UDP'
                else:
                    event_proto = "GRPC"
                print(f"{event_proto} Event and size is {event_kb_size} KB")
                self.decode_stream_event(event, event_proto)
        except KeyboardInterrupt:
            print("\nReceived Ctrl-C, shutting down gracefully...")
        except websocket.WebSocketException as e:
            print(f"WebSocketException Error occurred: {e}")
            raise
        except Exception as e:
            print(f"Exception : {e}")
            raise
        ws.close()
