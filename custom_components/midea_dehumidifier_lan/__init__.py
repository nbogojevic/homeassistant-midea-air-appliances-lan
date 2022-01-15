"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
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
from homeassistant.helpers import config_validation as cv
import voluptuous as vol


from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

from custom_components.midea_dehumidifier_lan.const import (
    CONF_APPID,
    CONF_APPKEY,
    CONF_BROADCAST_ADDRESS,
    CONF_DETECT_AC_APPLIANCES,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD,
    CURRENT_CONFIG_VERSION,
    UNKNOWN_IP,
    DOMAIN,
    PLATFORMS,
)
from custom_components.midea_dehumidifier_lan.hub import Hub
from custom_components.midea_dehumidifier_lan.util import domain

_LOGGER = logging.getLogger(__name__)


APPLIANCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_IP_ADDRESS, default=UNKNOWN_IP): cv.string,
        vol.Required(CONF_API_VERSION, default=3): int,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TOKEN_KEY): cv.string,
        vol.Optional(CONF_EXCLUDE, default=False): bool,
        vol.Optional(CONF_USE_CLOUD, default=False): bool,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_APPKEY): cv.string,
                vol.Optional(CONF_APPID): cv.string,
                vol.Optional(CONF_USE_CLOUD): bool,
                vol.Optional(CONF_DETECT_AC_APPLIANCES, default=False): bool,
                vol.Optional(CONF_BROADCAST_ADDRESS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_DEVICES): vol.All(
                    cv.ensure_list, [APPLIANCES_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    if (hub := domain(hass).get(entry.entry_id)) is None:
        hub = Hub(hass, entry)
        domain(hass)[entry.entry_id] = hub

        await hub.async_startup()
    await hub.async_setup()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and domain(hass):
        domain(hass).pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < CURRENT_CONFIG_VERSION:

        conf = {**config_entry.data}
        dev_confs = []
        conf.setdefault(CONF_USE_CLOUD, False)

        for dev_data in config_entry.data[CONF_DEVICES]:
            dev_conf = {**dev_data}
            dev_conf.setdefault(CONF_USE_CLOUD, conf[CONF_USE_CLOUD])
            dev_conf.setdefault(CONF_EXCLUDE, False)
            dev_confs.append(dev_conf)

        conf[CONF_DEVICES] = dev_confs
        if not conf.get(CONF_APPID) or not conf.get(CONF_APPKEY):
            conf[CONF_APPKEY] = DEFAULT_APPKEY
            conf[CONF_APPID] = DEFAULT_APP_ID
        conf.setdefault(CONF_BROADCAST_ADDRESS, [])
        conf.setdefault(CONF_USE_CLOUD, False)

        config_entry.version = CURRENT_CONFIG_VERSION
        _LOGGER.debug("Migrating configuration from %s to %s", config_entry.data, conf)
        if hass.config_entries.async_update_entry(config_entry, data=conf):
            _LOGGER.info("Configuration migrated to version %s", config_entry.version)
        else:
            _LOGGER.debug(
                "Configuration didn't change during migration to version %s",
                config_entry.version,
            )
        return True

    return False
