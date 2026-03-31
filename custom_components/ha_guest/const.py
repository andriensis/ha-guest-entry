"""Constants for the Guest Entry integration."""

DOMAIN = "ha_guest"

CONF_ADDON_URL = "addon_url"
CONF_INTERNAL_SECRET = "internal_secret"

DEFAULT_ADDON_URL = "http://localhost:7979"
SECRET_FILE_PATH = "/config/.ha_guest_entry_secret"

SCAN_INTERVAL_SECONDS = 30

# Data store keys
DATA_COORDINATOR = "coordinator"
DATA_CLIENT = "client"
