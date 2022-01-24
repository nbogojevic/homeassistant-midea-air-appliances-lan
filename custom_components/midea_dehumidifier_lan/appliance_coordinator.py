"""Update coordinator for Midea devices"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from time import monotonic
from typing import Any, cast, final

from homeassistant.const import CONF_DISCOVERY, CONF_TOKEN, CONF_TTL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import slugify
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import MideaError
from midea_beautiful.lan import LanDevice

from custom_components.midea_dehumidifier_lan.api import is_climate, is_dehumidifier
from custom_components.midea_dehumidifier_lan.const import (
    APPLIANCE_REFRESH_COOLDOWN,
    APPLIANCE_REFRESH_INTERVAL,
    CONF_TOKEN_KEY,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DOMAIN,
    ENTITY_DISABLED_BY_DEFAULT,
    ENTITY_ENABLED_BY_DEFAULT,
    UNIQUE_DEHUMIDIFIER_PREFIX,
)
from custom_components.midea_dehumidifier_lan.util import (
    AbstractHub,
    ApplianceCoordinator,
    RedactedConf,
)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class ApplianceUpdateCoordinator(DataUpdateCoordinator, ApplianceCoordinator):
    """Single class to retrieve data from an appliance"""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        hass: HomeAssistant,
        hub: AbstractHub,
        appliance: LanDevice,
        device: dict[str, Any],
        available: bool,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=appliance.name,
            update_method=self._async_appliance_refresh,
            update_interval=timedelta(seconds=APPLIANCE_REFRESH_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=APPLIANCE_REFRESH_COOLDOWN,
                immediate=True,
                function=self.async_refresh,
            ),
        )
        self.hub = hub
        self.appliance = appliance
        self.updating = {}
        self.wait_for_update = False
        self.device = device
        self.discovery_mode = device.get(CONF_DISCOVERY, DISCOVERY_IGNORE)
        self.use_cloud: bool = self.discovery_mode == DISCOVERY_CLOUD
        self.available = available
        self.time_to_leave = device.get(CONF_TTL, 100)  # TTL is in seconds
        self.has_failure = False
        self.first_failure_time: float = 0

    def _cloud(self) -> MideaCloud | None:
        if self.use_cloud:
            if not self.hub.cloud:
                raise UpdateFailed(
                    f"Midea cloud API was not initialized, {self.appliance}"
                    f" configuration={RedactedConf(self.hub.config)}"
                )
            return self.hub.cloud
        return None

    async def _async_appliance_refresh(self) -> LanDevice:
        """Called to refresh appliance state"""

        if not self.available:
            await self._async_try_to_detect()

        if self.wait_for_update:
            return self.appliance

        try:
            if self.updating:
                await self._async_do_update()

            await self.hass.async_add_executor_job(
                self.appliance.refresh, self._cloud()
            )
            self.has_failure = False
        except MideaError as ex:
            if not self.has_failure:
                self.has_failure = True
                self.first_failure_time = monotonic()
            if (monotonic() - self.first_failure_time) >= self.time_to_leave:
                raise UpdateFailed(str(ex)) from ex
            _LOGGER.warning(
                "Error fetching %s data: %s, will be trying again.", self.name, ex
            )
        finally:
            self.wait_for_update = False
        return self.appliance

    async def _async_do_update(self):
        self.wait_for_update = True
        _LOGGER.debug("Updating attributes for %s: %s", self.appliance, self.updating)
        for attr in self.updating:
            setattr(self.appliance.state, attr, self.updating[attr])
        self.updating.clear()
        await self.hass.async_add_executor_job(self.appliance.apply, self._cloud())

    async def _async_try_to_detect(self):
        _LOGGER.debug("Trying to find appliance %s", self.appliance)
        need_token, appliance = await self.hub.async_discover_device(self.device)
        if not appliance:
            raise UpdateFailed(self.hub.errors.get(str(self.appliance.serial_number)))
        if need_token:
            self.device[CONF_TOKEN] = appliance.token
            self.device[CONF_TOKEN_KEY] = appliance.key

        self.appliance = appliance
        await self.hub.async_update_config()
        self.available = True

    def is_climate(self) -> bool:
        """True if appliance is air conditioner"""
        return is_climate(self.appliance)

    def is_dehumidifier(self) -> bool:
        """True if appliance is dehumidifier"""
        return is_dehumidifier(self.appliance)

    @final
    def dehumidifier(self) -> DehumidifierAppliance:
        """Returns state as dehumidifier"""
        return cast(DehumidifierAppliance, self.appliance.state)

    @final
    def airconditioner(self) -> AirConditionerAppliance:
        """Returns state as air conditioner"""
        return cast(AirConditionerAppliance, self.appliance.state)

    async def async_apply(self, args: dict) -> None:
        """Applies changes to device"""
        for key, value in args.items():
            self.updating[key] = value
        await self.async_request_refresh()


class ApplianceEntity(CoordinatorEntity):
    """Represents an appliance that gets data from a coordinator"""

    _unique_id_prefx = UNIQUE_DEHUMIDIFIER_PREFIX
    _name_suffix = ""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.appliance = coordinator.appliance
        self._attr_unique_id = f"{self.unique_id_prefix}{self.appliance.serial_number}"
        self._attr_name = str(self.appliance.name or self.unique_id) + self.name_suffix

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        # Override parent, we will handle state
        self.async_on_remove(self.coordinator.async_add_listener(self._updated_data))
        if self.coordinator.available:
            self.on_online(True)

    @callback
    def _updated_data(self) -> None:
        """Called when data has been updated by coordinator"""

        self.appliance = self.coordinator.appliance
        self._attr_available = self.appliance.online
        if not self.coordinator.available:
            self.on_online(False)
        self.on_update()
        self.async_write_ha_state()

    def _set_enabled_for_capability(self, capability: str) -> None:
        if capability == ENTITY_ENABLED_BY_DEFAULT:
            res = True
        elif capability == ENTITY_DISABLED_BY_DEFAULT:
            res = False
        elif (capabilities := self.appliance.state.capabilities) :
            res = getattr(capabilities, capability, False)
        else:
            res = False
        self._attr_entity_registry_enabled_default = res

    def on_update(self) -> None:
        """Allows additional processing after the coordinator updates data"""

    def on_online(self, update: bool) -> None:
        """To be called when appliance comes online for the first time"""
        if update:
            self.on_update()
        self.async_write_ha_state()

    @final
    def dehumidifier(self) -> DehumidifierAppliance:
        """Returns state as dehumidifier"""
        return cast(DehumidifierAppliance, self.appliance.state)

    @final
    def airconditioner(self) -> AirConditionerAppliance:
        """Returns state as air conditioner"""
        return cast(AirConditionerAppliance, self.appliance.state)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.available:
            return False
        return super().available

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return self._name_suffix

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        strip = self.name_suffix.strip()
        if len(strip) == 0:
            return self._unique_id_prefx
        slug = slugify(strip)
        return f"{self._unique_id_prefx}{slug}_"

    @property
    def device_info(self) -> DeviceInfo:
        identifier = str(self.appliance.serial_number or self.appliance.serial_number)
        return DeviceInfo(
            identifiers={(DOMAIN, str(identifier))},
            name=self.appliance.name,
            manufacturer="Midea",
            model=str(self.appliance.model),
            sw_version=self.appliance.firmware_version,
        )

    def apply(self, *args, **kwargs) -> None:
        """Applies changes to device"""
        if len(args) % 2 != 0:
            raise ValueError(f"Expecting attribute/value pairs, had {len(args)} items")
        aargs = {}
        for i in range(0, len(args), 2):
            aargs[args[i]] = args[i + 1]
        for key, value in kwargs.items():
            aargs[key] = value
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_apply(aargs), self.hass.loop
        ).result()
