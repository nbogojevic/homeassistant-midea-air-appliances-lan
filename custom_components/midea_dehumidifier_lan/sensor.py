"""Adds sensors for each appliance."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
)
from custom_components.midea_dehumidifier_lan.const import DOMAIN, UNIQUE_CLIMATE_PREFIX
from custom_components.midea_dehumidifier_lan.hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up current environment humidity and temperature sensors"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    # Dehumidifier sensors
    async_add_entities(
        CurrentHumiditySensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        CurrentTemperatureSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        TankLevelSensor(c)
        for c in hub.coordinators
        if c.is_dehumidifier() and c.dehumidifier().capabilities.get("water_level")
    )
    # Climate sensors
    async_add_entities(
        OutsideTemperatureSensor(c) for c in hub.coordinators if c.is_climate()
    )


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    """Crrent environment humidity sensor"""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Humidity"

    def on_update(self) -> None:
        """
        Set the current humidity only if device is online, otherwise set it to None.
        """

        if not self.dehumidifier().online:
            _LOGGER.debug(
                "%s is offline",
                self.entity_id,
            )
            self._attr_native_value = None
            return

        self._attr_native_value = self.dehumidifier().current_humidity


class CurrentTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current environment temperature sensor"""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Temperature"

    def on_update(self) -> None:
        """
        Set the current temprature only if device is online, otherwise set it to None.
        """

        if not self.dehumidifier().online:
            _LOGGER.debug(
                "%s is offline",
                self.entity_id,
            )
            self._attr_native_value = None
            return

        self._attr_native_value = self.dehumidifier().current_temperature


class TankLevelSensor(ApplianceEntity, SensorEntity):
    """Current tank water level sensor"""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Water Level"

    def on_online(self, update: bool) -> None:
        self._attr_entity_registry_enabled_default = (
            self.dehumidifier().capabilities.get("water_level", False)
        )
        return super().on_online(update)

    def on_update(self) -> None:
        """
        Set the tank level only if device is online, otherwise set it to None.
        """

        if not self.dehumidifier().online:
            _LOGGER.debug(
                "%s is offline",
                self.entity_id,
            )

            self._attr_native_value = None
            return

        self._attr_native_value = self.dehumidifier().tank_level


class OutsideTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current outside temperature sensor"""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unique_id_prefx = UNIQUE_CLIMATE_PREFIX
    _name_suffix = " Outdoor Temperature"

    def on_update(self) -> None:
        """
        Set the outdoor temprature only if device is online, otherwise set it to None.
        """

        if not self.airconditioner().online:
            _LOGGER.debug(
                "%s is offline",
                self.entity_id,
            )

            self._attr_native_value = None
            return

        self._attr_native_value = self.airconditioner().outdoor_temperature
