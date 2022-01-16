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
from custom_components.midea_dehumidifier_lan.hub import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)


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
        if c.is_dehumidifier() and c.dehumidifier().supports.get("water_level")
    )
    # Climate sensors
    async_add_entities(
        OutsideTemperatureSensor(c) for c in hub.coordinators if c.is_climate()
    )
    async_add_entities(
        ErrorCodeSensor(c)
        for c in hub.coordinators
        if c.is_dehumidifier() or c.is_climate()
    )


class ErrorCodeSensor(ApplianceEntity, SensorEntity):
    """Returns current appliance error code"""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Error Code"
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float:
        """Return the value of the sensor property."""
        return self.dehumidifier().error_code


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    """Crrent environment humidity sensor"""

    _attr_device_class = DEVICE_CLASS_HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Humidity"

    @property
    def native_value(self):
        return self.dehumidifier().current_humidity


class CurrentTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current environment temperature sensor"""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _name_suffix = " Temperature"

    @property
    def native_value(self):
        return self.dehumidifier().current_temperature


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

    @property
    def native_value(self):
        return self.dehumidifier().tank_level


class OutsideTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current outside temperature sensor"""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unique_id_prefx = UNIQUE_CLIMATE_PREFIX
    _name_suffix = " Outdoor Temperature"

    @property
    def native_value(self):
        return self.airconditioner().outdoor_temperature
