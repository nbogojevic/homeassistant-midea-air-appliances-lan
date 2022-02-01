"""Constants for Midea Air Appliance custom component"""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    SUPPORTED_APPS,
)

__version__ = "0.6.1"

# Base component constants
NAME: Final = "Midea Air Appliance (LAN)"
UNIQUE_ID_PRE_PREFIX: Final = "midea_"
UNIQUE_DEHUMIDIFIER_PREFIX: Final = "midea_dehumidifier_"
UNIQUE_CLIMATE_PREFIX: Final = "midea_climate_"
DOMAIN: Final = f"{UNIQUE_DEHUMIDIFIER_PREFIX}lan"
# pylint: disable=line-too-long
ISSUE_URL: Final = "https://github.com/nbogojevic/homeassistant-midea-air-appliances-lan/issues/new/choose"  # noqa: E501

CONF_ADVANCED_SETTINGS: Final = "advanced_settings"
CONF_APPID: Final = "appid"
CONF_APPKEY: Final = "appkey"
CONF_DEBUG: Final = "debug"
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
DEFAULT_SCAN_INTERVAL: Final = 15
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

ENTITY_DISABLED_BY_DEFAULT: Final = ":disabled:"
ENTITY_ENABLED_BY_DEFAULT: Final = ":enabled:"
_ALWAYS_CREATE: Final = [ENTITY_DISABLED_BY_DEFAULT, ENTITY_ENABLED_BY_DEFAULT]

UNKNOWN_IP: Final = "0.0.0.0"
LOCAL_BROADCAST: Final = "255.255.255.255"

# What to do with configured appliance
DISCOVERY_IGNORE = "IGNORE"
DISCOVERY_LAN = "LAN"
DISCOVERY_CLOUD = "CLOUD"
DISCOVERY_WAIT = "WAIT"
DEFAULT_DISCOVERY_MODE = DISCOVERY_LAN

DISCOVERY_BATCH_SIZE: Final = 64

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

DISCOVERY_MODE_LABELS = {
    DISCOVERY_IGNORE: "Exclude appliance",
    DISCOVERY_LAN: "Provide appliance's IPv4 address",
    DISCOVERY_WAIT: "Wait for appliance to come online",
    DISCOVERY_CLOUD: "Use cloud API to poll appliance",
}

DISCOVERY_MODE_EXPLANATION = {
    DISCOVERY_IGNORE: "excluded from polling",
    DISCOVERY_LAN: "assigned local network address",
    DISCOVERY_WAIT: "waiting to be disovered",
    DISCOVERY_CLOUD: "polled using cloud",
}

SUPPORTED_APPLIANCES = {
    APPLIANCE_TYPE_AIRCON: "Air conditioner (BETA)",
    APPLIANCE_TYPE_DEHUMIDIFIER: "Dehumidifier",
}

# Default period of failed updates before appliance is declared unavailable
# 5 minutes
DEFAULT_TTL: Final = 5
