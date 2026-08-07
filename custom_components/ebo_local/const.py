"""Constants for the EBO Local integration.

Local-first companion to the cloud add-on: this talks to the robot over its own LAN surfaces
(Kalay P2P tunnel to :9036 for SD recordings today; UDP 32761 for control, later). See ../../ROADMAP.md.

SECRETS RULE: TUTK credentials, device tokens and cloud keys are entered by the user at config time
and stored by Home Assistant — never hardcode them here or anywhere in this repo.
"""

DOMAIN = "ebo_local"

# --- config-entry keys (collected by the config flow) ---
CONF_ROBOT_ID = "robot_id"        # the robot's id / serial
CONF_TUTK_UID = "tutk_uid"        # Kalay UID (WKX… — from the vendor cloud, user-supplied)
CONF_TUTK_LICENSE = "tutk_license"
CONF_TUTK_IDENTITY = "tutk_identity"
CONF_TUTK_TOKEN = "tutk_token"    # Kalay token value (secret)
CONF_NAME = "name"
CONF_TUNNEL_HELPER = "tunnel_helper"
CONF_TUNNEL_LOCAL_PORT = "tunnel_local_port"

# --- the robot's local surfaces (see ROADMAP) ---
KALAY_FILESERVER_PORT = 9036      # SD recordings, reachable only through the Kalay tunnel
CONTROL_UDP_PORT = 32761          # MAVLink-like local control (gated on the flash device token)
DEFAULT_TUNNEL_HELPER = "ebo-kalay-fileserver-tunnel"
DEFAULT_TUNNEL_LOCAL_PORT = 9920

# --- local bridge appliance (ebo_bridge_air2 + bridge_host, runs on the LAN e.g. in the Proxmox CT) ---
# Full-local control/telemetry/video go through the bridge host's HTTP+RTSP API, not the cloud.
CONF_BRIDGE_URL = "bridge_url"          # e.g. http://192.168.30.9:8099  (bridge_host HTTP API)
CONF_BRIDGE_RTSP = "bridge_rtsp"        # e.g. rtsp://192.168.30.9:8554/ebo  (video from mediamtx)
DEFAULT_BRIDGE_PORT = 8099
TELEMETRY_INTERVAL_S = 5                 # bridge telemetry poll cadence
