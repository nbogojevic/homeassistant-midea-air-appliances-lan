"""
The custom component for local network access to Midea Dehumidifier
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from midea_beautiful_dehumidifier import appliance_state, connect_to_cloud
from midea_beautiful_dehumidifier.lan import LanDevice
from midea_beautiful_dehumidifier.midea import DEFAULT_APPKEY

from .const import CONF_TOKEN_KEY, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    hub = Hub()
    hass.data[DOMAIN][entry.entry_id] = hub
    await hub.start(hass, entry.data)

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
    """Central class for interacting with appliances"""

    def __init__(self) -> None:
        self.coordinators: list[ApplianceUpdateCoordinator] = []

    async def start(self, hass: HomeAssistant, data):
        """
        sets up appliances and creates an update coordinator for
        each appliance
        """
        cloud = None
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        for devconf in data[CONF_DEVICES]:
            if not devconf[CONF_TOKEN] or not devconf[CONF_TOKEN_KEY]:
                if cloud is None:
                    # TODO maybe if there is no username, we should skip this
                    # and log an error
                    cloud = await hass.async_add_executor_job(
                        connect_to_cloud,
                        data[CONF_USERNAME],
                        data[CONF_PASSWORD],
                        DEFAULT_APPKEY,
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
            "identifiers": {(DOMAIN, self.appliance.sn)},
            "name": self.appliance.name,
            "manufacturer": "Midea",
            "model": str(self.appliance.model),
            "sw_version": self.appliance.firmware_version,
        }
