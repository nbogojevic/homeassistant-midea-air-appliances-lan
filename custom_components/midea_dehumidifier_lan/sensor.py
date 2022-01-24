"""Adds sensors for each appliance."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import DOMAIN, UNIQUE_CLIMATE_PREFIX
from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.hub import Hub


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

    _attr_device_class = DEVICE_CLASS_HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Humidity"

    def process_update(self) -> None:
        self._attr_native_value = self.dehumidifier().current_humidity


class CurrentTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current environment temperature sensor"""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Temperature"

    def process_update(self) -> None:
        self._attr_native_value = self.dehumidifier().current_temperature


class TankLevelSensor(ApplianceEntity, SensorEntity):
    """Current tank water level sensor"""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Water Level"

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_entity_registry_enabled_default = self.appliance.state.supported.get(
            "water_level"
        )

    def process_update(self) -> None:
        self._attr_native_value = self.dehumidifier().tank_level


class OutsideTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current outside temperature sensor"""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unique_id_prefx = UNIQUE_CLIMATE_PREFIX
    _name_suffix = " Outdoor Temperature"

    def process_update(self) -> None:
        self._attr_native_value = self.airconditioner().outdoor_temperature
