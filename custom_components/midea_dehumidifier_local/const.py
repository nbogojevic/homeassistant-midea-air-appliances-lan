from __future__ import annotations

from typing import Final
from homeassistant.const import Platform

__version__ = "0.0.1"

# Base component constants
NAME = "Midea Dehumidifier (LAN)"
DOMAIN = "midea_dehumidifier_local"
DOMAIN_DATA = f"{DOMAIN}_data"
ISSUE_URL = "https://github.com/nbogojevic/midea_dehumidifier_local/issues"

CONF_APP_KEY = "app_key"
CONF_TOKEN_KEY = "token_key"
CONF_IGNORE_APPLIANCE = "ignore_appliance"

PLATFORMS: Final = [Platform.FAN, Platform.HUMIDIFIER, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

IGNORED_IP_ADDRESS = "0.0.0.0"
DEFAULT_ANNOUNCE_PORT = 6445

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {__version__}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""