"""
The custom component for local network access to Midea Dehumidifier

"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_APP_KEY,
    CONF_TOKEN_KEY
)

from midea_beautiful_dehumidifier import appliance_state, connect_to_cloud

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Configuration entry: %s", entry.data)

    hub = await hass.async_add_executor_job(Hub, hass, entry.data)
    hass.data[DOMAIN][entry.entry_id] = hub

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class Hub:
    def __init__(self, hass: HomeAssistant, data):
        self.cloud = connect_to_cloud(
            appkey=data[CONF_APP_KEY],
            account=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        )
        self.appliances = []
        for aconf in data[CONF_DEVICES]:
            app = appliance_state(aconf[CONF_IP_ADDRESS], token=aconf[CONF_TOKEN], key=aconf[CONF_TOKEN_KEY], cloud=self.cloud)
            self.appliances.append(app)

            