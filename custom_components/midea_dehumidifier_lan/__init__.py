"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_EXCLUDE,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

from custom_components.midea_dehumidifier_lan.const import (
    CONF_APPID,
    CONF_APPKEY,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD_OBSOLETE,
    CURRENT_CONFIG_VERSION,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_WAIT,
    DOMAIN,
    PLATFORMS,
    UNKNOWN_IP,
)
from custom_components.midea_dehumidifier_lan.hub import Hub


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    if (hub := hass.data[DOMAIN].get(entry.entry_id)) is None:
        hub = Hub(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = hub
    await hub.async_setup()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hub: Hub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_unload()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < CURRENT_CONFIG_VERSION:
        old_conf = config_entry.data
        new_conf = {
            CONF_APPKEY: old_conf.get(CONF_APPKEY),
            CONF_APPID: old_conf.get(CONF_APPID),
            CONF_BROADCAST_ADDRESS: old_conf.get(CONF_BROADCAST_ADDRESS),
            CONF_USERNAME: old_conf.get(CONF_USERNAME),
            CONF_PASSWORD: old_conf.get(CONF_PASSWORD),
        }
        if not new_conf.get(CONF_APPID) or not new_conf.get(CONF_APPKEY):
            new_conf[CONF_APPKEY] = DEFAULT_APPKEY
            new_conf[CONF_APPID] = DEFAULT_APP_ID
        new_conf.setdefault(CONF_BROADCAST_ADDRESS, [])

        new_devices = []
        new_conf[CONF_DEVICES] = new_devices

        old: dict
        for old in config_entry.data[CONF_DEVICES]:
            new = {
                CONF_API_VERSION: old.get(CONF_API_VERSION),
                CONF_DISCOVERY: old.get(CONF_DISCOVERY),
                CONF_ID: old.get(CONF_ID),
                CONF_IP_ADDRESS: old.get(CONF_IP_ADDRESS),
                CONF_NAME: old.get(CONF_NAME),
                CONF_TOKEN: old.get(CONF_TOKEN),
                CONF_TOKEN_KEY: old.get(CONF_TOKEN_KEY),
                CONF_TYPE: old.get(CONF_TYPE),
                CONF_UNIQUE_ID: old.get(CONF_UNIQUE_ID),
            }
            if not new.get(CONF_DISCOVERY):
                if old.get(CONF_USE_CLOUD_OBSOLETE):
                    new[CONF_DISCOVERY] = DISCOVERY_CLOUD
                elif old.get(CONF_EXCLUDE):
                    new[CONF_DISCOVERY] = DISCOVERY_IGNORE
                elif old.get(CONF_IP_ADDRESS) == UNKNOWN_IP:
                    new[CONF_DISCOVERY] = DISCOVERY_WAIT
                else:
                    new[CONF_DISCOVERY] = DISCOVERY_LAN
            if not new.get(CONF_IP_ADDRESS):
                new[CONF_IP_ADDRESS] = UNKNOWN_IP
            new_devices.append(new)

        config_entry.version = CURRENT_CONFIG_VERSION
        _LOGGER.debug(
            "Migrating configuration from %s to %s", config_entry.data, new_conf
        )
        if hass.config_entries.async_update_entry(config_entry, data=new_conf):
            _LOGGER.info("Configuration migrated to version %s", config_entry.version)
        else:
            _LOGGER.debug(
                "Configuration didn't change during migration to version %s",
                config_entry.version,
            )
        return True

    return False
