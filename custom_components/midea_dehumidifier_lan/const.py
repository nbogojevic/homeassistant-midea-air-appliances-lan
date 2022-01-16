"""Constants for Midea dehumidifier custom component"""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

from midea_beautiful.midea import SUPPORTED_APPS

__version__ = "0.5.0"

# Base component constants
NAME: Final = "Midea Dehumidifier (LAN)"
UNIQUE_ID_PRE_PREFIX: Final = "midea_"
UNIQUE_DEHUMIDIFIER_PREFIX: Final = "midea_dehumidifier_"
UNIQUE_CLIMATE_PREFIX: Final = "midea_climate_"
DOMAIN: Final = f"{UNIQUE_DEHUMIDIFIER_PREFIX}lan"
# pylint: disable=line-too-long
ISSUE_URL: Final = "https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan/issues/new/choose"  # noqa: E501

CONF_ADVANCED_SETTINGS: Final = "advanced_settings"
CONF_APPID: Final = "appid"
CONF_APPKEY: Final = "appkey"
CONF_MOBILE_APP: Final = "mobile_app"
CONF_TOKEN_KEY: Final = "token_key"
CONF_USE_CLOUD_OBSOLETE: Final = "use_cloud"

MAX_TARGET_HUMIDITY: Final = 85
MIN_TARGET_HUMIDITY: Final = 35

MAX_TARGET_TEMPERATURE: Final = 32
MIN_TARGET_TEMPERATURE: Final = 16

CURRENT_CONFIG_VERSION: Final = 2

# Wait half a second between successive refresh calls
APPLIANCE_REFRESH_COOLDOWN: Final = 0.5
APPLIANCE_REFRESH_INTERVAL: Final = 60
APPLIANCE_SCAN_INTERVAL: Final = 2
MIN_SCAN_INTERVAL: Final = 2

ATTR_FAN_SPEED: Final = "fan_speed"
ATTR_RUNNING: Final = "running"

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.SENSOR,
    Platform.SWITCH,
]

UNKNOWN_IP: Final = "0.0.0.0"

# What to do with configured appliance
DISCOVERY_IGNORE = "IGNORE"
DISCOVERY_LAN = "LAN"
DISCOVERY_CLOUD = "CLOUD"
DISCOVERY_WAIT = "WAIT"
DEFAULT_DISCOVERY_MODE = DISCOVERY_LAN

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
