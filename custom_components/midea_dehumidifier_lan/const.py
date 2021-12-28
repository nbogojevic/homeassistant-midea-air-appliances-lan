"""Constants for Midea dehumidifier custom component"""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform
from midea_beautiful_dehumidifier.midea import SUPPORTED_APPS

__version__ = "0.4.1"

# Base component constants
NAME: Final = "Midea Dehumidifier (LAN)"
DOMAIN: Final = "midea_dehumidifier_lan"
ISSUE_URL: Final = "https://github.com/nbogojevic/midea-dehumidifier-lan/issues"

CONF_ADVANCED_OPTIONS: Final = "advanced_options"
CONF_APPID: Final = "appid"
CONF_APPKEY: Final = "appkey"
CONF_IGNORE_APPLIANCE: Final = "ignore_appliance"
CONF_MOBILE_APP: Final = "mobile_app"
CONF_NETWORK_RANGE: Final = "network_range"
CONF_TOKEN_KEY: Final = "token_key"
CONF_USE_CLOUD: Final = "use_cloud"


TAG_CAUSE: Final = "cause"
TAG_ID: Final = "id"
TAG_NAME: Final = "name"

MAX_TARGET_HUMIDITY: Final = 85
MIN_TARGET_HUMIDITY: Final = 35

CURRENT_CONFIG_VERSION: Final = 2

PLATFORMS: Final = [
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

IGNORED_IP_ADDRESS: Final = "0.0.0.0"

DEFAULT_APP: Final = next(app for app in SUPPORTED_APPS)

DEFAULT_USERNAME: Final = ""
DEFAULT_PASSWORD: Final = ""

STARTUP_MESSAGE: Final = f"""
-------------------------------------------------------------------
{NAME}
Version: {__version__}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
