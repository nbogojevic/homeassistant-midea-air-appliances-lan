"""
The custom component for local network access to Midea Dehumidifier
"""

from __future__ import annotations
import asyncio

from datetime import timedelta
import logging
from typing import Any, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from midea_beautiful_dehumidifier import appliance_state, connect_to_cloud
from midea_beautiful_dehumidifier.appliance import DehumidifierAppliance
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.exceptions import AuthenticationError, MideaError
from midea_beautiful_dehumidifier.lan import LanDevice

from .const import (
    CONF_APPID,
    CONF_APPKEY,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD,
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


class Hub:
    """Central class for interacting with appliances"""

    def __init__(self) -> None:
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        self.use_cloud: bool = False
        self.cloud: MideaCloud | None = None

    async def start(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """
        Sets up appliances and creates an update coordinator for
        each one
        """
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        updated_conf = False
        data = {**config_entry.data}
        self.use_cloud = data.get(CONF_USE_CLOUD) or False
        self.cloud = None
        _LOGGER.debug("devconf: %s", data)
        for device in data[CONF_DEVICES]:
            _LOGGER.debug("devconf: %s", device)
            use_cloud = self.use_cloud or device.get(CONF_USE_CLOUD)
            need_cloud = use_cloud
            if not use_cloud and (not device[CONF_TOKEN] or not device[CONF_TOKEN_KEY]):
                _LOGGER.warn(
                    "Appliance %s has no token, trying to get it from Midea cloud API",
                    device[CONF_NAME],
                )
                need_cloud = True
            if need_cloud or use_cloud:
                if self.cloud is None:
                    try:
                        self.cloud = await hass.async_add_executor_job(
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
                device[CONF_IP_ADDRESS] if not need_cloud else None,  # ip
                device[CONF_TOKEN],  # token
                device[CONF_TOKEN_KEY],  # key
                self.cloud,  # cloud
                device[CONF_USE_CLOUD] or False,  # use_cloud
                device[CONF_ID],  # id
            )
            # For each appliance create a coordinator
            if appliance is not None:
                if (
                    (not device[CONF_TOKEN] or not device[CONF_TOKEN_KEY])
                    and appliance.token
                    and appliance.key
                ):
                    device[CONF_TOKEN] = appliance.token
                    device[CONF_TOKEN_KEY] = appliance.key
                    updated_conf = True
                    _LOGGER.debug(
                        "Updating token for Midea dehumidifer %s",
                        device[CONF_NAME],
                    )
                appliance.name = device[CONF_NAME]
                coordinator = ApplianceUpdateCoordinator(hass, self, appliance)
                self.coordinators.append(coordinator)
            else:
                _LOGGER.error(
                    "Unable to get appliance %s at %s",
                    device[CONF_NAME],
                    device[CONF_IP_ADDRESS],
                )

        for coordinator in self.coordinators:
            await coordinator.async_config_entry_first_refresh()

        if updated_conf:
            hass.config_entries.async_update_entry(config_entry, data=data)


class ApplianceUpdateCoordinator(DataUpdateCoordinator):
    """Single class to retrieve data from an appliance"""

    def __init__(self, hass, hub: Hub, appliance: LanDevice):
        super().__init__(
            hass,
            _LOGGER,
            name="Midea appliance",
            update_method=self._async_appliance_refresh,
            update_interval=timedelta(seconds=60),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=0.5,
                immediate=True,
                function=self.async_refresh,
            ),
        )
        self.hub = hub
        self.appliance = appliance
        self.updating = {}
        self.wait_for_update = False

    def _cloud(self) -> MideaCloud | None:
        if self.appliance._use_cloud or self.hub.use_cloud:
            if not self.hub.cloud:
                raise UpdateFailed("Midea cloud API was not initialized")
            return self.hub.cloud
        return None

    async def _async_appliance_refresh(self) -> LanDevice:
        """Called to refresh appliance state"""

        if self.wait_for_update:
            return self.appliance
        try:
            if self.updating:
                self.wait_for_update = True
                _LOGGER.debug(
                    "Updating attributes for %s: %s for", self.appliance, self.updating
                )
                for attr in self.updating:
                    setattr(self.appliance.state, attr, self.updating[attr])
                self.updating = {}
                await self.hass.async_add_executor_job(
                    self.appliance.apply, self._cloud()
                )

            _LOGGER.debug("Refreshing %s", self.appliance)

            await self.hass.async_add_executor_job(
                self.appliance.refresh, self._cloud()
            )
        except MideaError as ex:
            raise UpdateFailed(str(ex)) from ex
        finally:
            self.wait_for_update = False
        return self.appliance

    def is_dehumidifier(self) -> bool:
        return DehumidifierAppliance.supported(self.appliance.type)

    async def async_apply(self, attr, value) -> None:
        self.updating[attr] = value
        await self.async_request_refresh()


class ApplianceEntity(CoordinatorEntity):
    """Represents an appliance that gets data from a coordinator"""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.appliance = coordinator.appliance
        self._unique_id = f"{self.unique_id_prefix}{self.appliance.id}"
        self._applying = False

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
    def name(self) -> str:
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
    def device_info(self) -> DeviceInfo:
        identifier = str(self.appliance.sn or self.appliance.id)
        return DeviceInfo(
            identifiers={(DOMAIN, str(identifier))},
            name=self.appliance.name,
            manufacturer="Midea",
            model=str(self.appliance.model),
            sw_version=self.appliance.firmware_version,
        )

    def apply(self, attr: str, value: Any) -> None:
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_apply(attr, value), self.hass.loop
        ).result()
