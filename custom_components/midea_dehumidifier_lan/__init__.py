"""
The custom component for local network access to Midea Dehumidifier
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_DEVICES,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from midea_beautiful_dehumidifier import appliance_state, connect_to_cloud
from midea_beautiful_dehumidifier import appliance
from midea_beautiful_dehumidifier.appliance import DehumidifierAppliance
from midea_beautiful_dehumidifier.exceptions import AuthenticationError
from midea_beautiful_dehumidifier.lan import LanDevice
from midea_beautiful_dehumidifier.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

from .const import (
    CONF_APPID,
    CONF_APPKEY,
    CONF_NETWORK_RANGE,
    CONF_TOKEN_KEY,
    CURRENT_CONFIG_VERSION,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    hub = Hub()
    hass.data[DOMAIN][entry.entry_id] = hub
    await hub.start(hass, entry)

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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < CURRENT_CONFIG_VERSION:

        new = {**config_entry.data}
        if not new.get(CONF_APPID) or not new.get(CONF_APPKEY):
            new[CONF_APPKEY] = DEFAULT_APPKEY
            new[CONF_APPID] = DEFAULT_APP_ID
        if new.get(CONF_NETWORK_RANGE) is None:
            new[CONF_NETWORK_RANGE] = []

        config_entry.version = CURRENT_CONFIG_VERSION
        _LOGGER.info("Migration from %s", config_entry.data)
        _LOGGER.info("Migration to %s", new)
        # hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


class Hub:
    """Central class for interacting with appliances"""

    def __init__(self) -> None:
        self.coordinators: list[ApplianceUpdateCoordinator] = []

    async def start(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """
        Sets up appliances and creates an update coordinator for
        each one
        """
        cloud = None
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        updated_conf = False
        data = {**config_entry.data}
        for devconf in data[CONF_DEVICES]:
            if not devconf[CONF_TOKEN] or not devconf[CONF_TOKEN_KEY]:
                _LOGGER.warn(
                    "Appliance %s has no token, trying to get it from Midea cloud API",
                    devconf[CONF_NAME],
                )
                if cloud is None:
                    # TODO maybe if there is no username, we should skip this
                    # and log an error
                    try:
                        cloud = await hass.async_add_executor_job(
                            connect_to_cloud,
                            data[CONF_USERNAME],
                            data[CONF_PASSWORD],
                            data[CONF_APPKEY],
                            data[CONF_APPID],
                        )
                    except AuthenticationError as ex:
                        raise ConfigEntryAuthFailed(
                            f"Unable to login to Midea cloud {ex}"
                        )
            appliance = await hass.async_add_executor_job(
                appliance_state,
                devconf[CONF_IP_ADDRESS],
                devconf[CONF_TOKEN],
                devconf[CONF_TOKEN_KEY],
                cloud,
            )
            # For each appliance create a coordinator
            if appliance is not None:
                if not devconf[CONF_TOKEN] or not devconf[CONF_TOKEN_KEY]:
                    devconf[CONF_TOKEN] = appliance.token
                    devconf[CONF_TOKEN_KEY] = appliance.key
                    updated_conf = True
                    _LOGGER.debug(
                        "Updating token for Midea dehumidifer %s",
                        devconf[CONF_NAME],
                    )
                appliance.name = devconf[CONF_NAME]
                coordinator = ApplianceUpdateCoordinator(hass, appliance)
                self.coordinators.append(coordinator)
            else:
                _LOGGER.error(
                    "Unable to get appliance %s at %s",
                    devconf[CONF_NAME],
                    devconf[CONF_IP_ADDRESS],
                )

        for coordinator in self.coordinators:
            await coordinator.async_config_entry_first_refresh()

        if updated_conf:
            _LOGGER.warn("Updated Midea dehumidifers with new tokens")
            hass.config_entries.async_update_entry(config_entry, data=data)


class ApplianceUpdateCoordinator(DataUpdateCoordinator):
    """Single class to retrieve data from an appliances"""

    def __init__(self, hass, appliance: LanDevice):
        super().__init__(
            hass,
            _LOGGER,
            name="Midea appliance",
            update_method=self._async_appliance_refresh,
            update_interval=timedelta(seconds=60),
        )
        self.appliance = appliance

    async def _async_appliance_refresh(self):
        """Called to refresh appliance state"""
        await self.hass.async_add_executor_job(self.appliance.refresh)
        return appliance

    def is_dehumidifier(self) -> bool:
        return DehumidifierAppliance.supported(self.appliance.type)


class ApplianceEntity(CoordinatorEntity):
    """Represents an appliance that gets data from a coordinator"""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.appliance = coordinator.appliance
        self._unique_id = f"{self.unique_id_prefix}{self.appliance.id}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._updated_data))

    @property
    @final
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    @final
    def name(self):
        """Return the unique id."""
        return (
            str(getattr(self.appliance.state, "name", self.unique_id))
            + self.name_suffix
        )

    @callback
    def _updated_data(self):
        self.appliance = self.coordinator.appliance

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return ""

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return ""

    @property
    def available(self) -> bool:
        return self.appliance.online

    @property
    def device_info(self):
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.appliance.sn)},
            ATTR_NAME: self.appliance.name,
            ATTR_MANUFACTURER: "Midea",
            ATTR_MODEL: str(self.appliance.model),
            ATTR_SW_VERSION: self.appliance.firmware_version,
        }

    def do_apply(self):
        self.appliance.apply()
        self.schedule_update_ha_state(force_refresh=True)
