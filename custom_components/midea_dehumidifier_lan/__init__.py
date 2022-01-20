"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations

import logging
from typing import Any, Final

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
from homeassistant.helpers.entity_registry import async_get_registry
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import MideaError
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

from custom_components.midea_dehumidifier_lan.api import MideaClient

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
    LOCAL_BROADCAST,
    NAME,
    PLATFORMS,
    UNKNOWN_IP,
)
from custom_components.midea_dehumidifier_lan.hub import Hub


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    if (hub := hass.data[DOMAIN].get(config_entry.entry_id)) is None:
        hub = Hub(hass, config_entry)
        hass.data[DOMAIN][config_entry.entry_id] = hub
    await hub.async_setup()
    await _async_migrate_names(hass, config_entry)
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def _async_migrate_names(hass: HomeAssistant, config_entry: ConfigEntry):
    entity_registry = await async_get_registry(hass)

    conf = config_entry.data
    if devices := conf.get(CONF_DEVICES):
        old_entites = [
            entry
            for _, entry in entity_registry.entities.items()
            if entry.platform == DOMAIN
        ]
        for reg_entry in old_entites:
            for device in devices:
                old_suffix = f"_{device[CONF_ID]}"
                new_suffix = f"_{device[CONF_UNIQUE_ID]}"
                if reg_entry.unique_id.endswith(old_suffix):
                    prefix = reg_entry.unique_id[: -len(old_suffix)]
                    old_unique_id = reg_entry.unique_id
                    new_unique_id = f"{prefix}{new_suffix}"
                    try:
                        entity_registry.async_update_entity(
                            reg_entry.entity_id,
                            new_unique_id=new_unique_id,
                        )
                        _LOGGER.warning(
                            "Changed unique id of %s from %s to %s",
                            reg_entry.entity_id,
                            old_unique_id,
                            new_unique_id,
                        )
                    except ValueError as ex:
                        _LOGGER.error(
                            "Unable to change unique id of %s: %s",
                            reg_entry.entity_id,
                            ex,
                        )


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
        old_broadcast = old_conf.get(CONF_BROADCAST_ADDRESS, [])
        if not old_broadcast:
            old_broadcast = [LOCAL_BROADCAST]
        new_conf = {
            CONF_APPKEY: old_conf.get(CONF_APPKEY),
            CONF_APPID: old_conf.get(CONF_APPID),
            CONF_BROADCAST_ADDRESS: old_broadcast,
            CONF_USERNAME: old_conf.get(CONF_USERNAME),
            CONF_PASSWORD: old_conf.get(CONF_PASSWORD),
        }
        if not new_conf.get(CONF_APPID) or not new_conf.get(CONF_APPKEY):
            new_conf[CONF_APPKEY] = DEFAULT_APPKEY
            new_conf[CONF_APPID] = DEFAULT_APP_ID

        new_devices = []
        new_conf[CONF_DEVICES] = new_devices

        id_resolver = _ApplianceIdResolver(hass)

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
            await id_resolver.async_get_unique_id_if_missing(new_conf, new)
            new_devices.append(new)

        config_entry.version = CURRENT_CONFIG_VERSION
        _LOGGER.debug(
            "Migrating configuration from %s to %s", config_entry.data, new_conf
        )
        if hass.config_entries.async_update_entry(
            config_entry, data=new_conf, title=NAME
        ):
            _LOGGER.info("Configuration migrated to version %s", config_entry.version)
        else:
            _LOGGER.debug(
                "Configuration didn't change during migration to version %s",
                config_entry.version,
            )
        return id_resolver.success

    return False


class _ApplianceIdResolver:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.client: Final = MideaClient()
        self.cloud: MideaCloud | None = None
        self.list_appliances: list[LanDevice] | None = None
        self.success = True

    async def _start(self, conf: dict[str, None]):
        try:
            self.cloud = await self.hass.async_add_executor_job(
                self.client.connect_to_cloud,
                conf[CONF_USERNAME],
                conf[CONF_PASSWORD],
                conf[CONF_APPKEY],
                conf[CONF_APPID],
            )
            self.list_appliances = self.cloud.list_appliances()
        except MideaError as ex:
            _LOGGER.error(
                "Unable to get list of appliances during configuration migration %s.",
                ex,
                exc_info=True,
            )

    async def async_get_unique_id_if_missing(
        self,
        conf: dict[str, Any],
        device_conf: dict[str, Any],
    ):
        """If there is no unique_id assigned, try to find serial number"""
        if device_conf[CONF_UNIQUE_ID] is None:
            if device_conf[CONF_DISCOVERY] == DISCOVERY_LAN:
                appliance = await self._get_appliance_state(device_conf)
                device_conf[CONF_UNIQUE_ID] = appliance and appliance.serial_number
            if device_conf[CONF_UNIQUE_ID] is None:
                if self.cloud is None:
                    await self._start(conf)
                if self.list_appliances is not None:
                    for app in self.list_appliances:
                        if app.appliance_id == device_conf[CONF_ID]:
                            device_conf[CONF_UNIQUE_ID] = app.serial_number
                            break
            if device_conf[CONF_UNIQUE_ID] is None:
                _LOGGER.error(
                    "Unable to find serial number for appliance %s."
                    "Please re-install %s integration.",
                    device_conf[CONF_NAME],
                    NAME,
                )
                self.success = False

    async def _get_appliance_state(
        self,
        device_conf: dict[str, None],
        cloud: MideaCloud = None,
        use_cloud: bool = False,
    ):
        try:
            return await self.hass.async_add_executor_job(
                self.client.appliance_state,
                device_conf[CONF_IP_ADDRESS],
                device_conf[CONF_TOKEN],
                device_conf[CONF_TOKEN_KEY],
                cloud,
                use_cloud,
                device_conf[CONF_ID],
            )
        except MideaError as ex:
            _LOGGER.error(
                "Unable to poll appliance during configuration migration %s.",
                ex,
                exc_info=True,
            )
