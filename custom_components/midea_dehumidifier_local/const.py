"""Constants for Midea dehumidifier custom component"""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

__version__ = "0.0.1"

# Base component constants
NAME: Final = "Midea Dehumidifier (LAN)"
DOMAIN: Final = "midea_dehumidifier_local"
ISSUE_URL: Final = "https://github.com/nbogojevic/midea-dehumidifier-lan/issues"

CONF_TOKEN_KEY: Final = "token_key"
CONF_IGNORE_APPLIANCE: Final = "ignore_appliance"

PLATFORMS: Final = [
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

IGNORED_IP_ADDRESS: Final = "0.0.0.0"

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
