"""Adds humidity sensors for each dehumidifer appliance."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)
from custom_components.midea_dehumidifier_lan.const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up current environment humidity and temperature sensors"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        CurrentHumiditySensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        CurrentTemperatureSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        TankLevelSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    """Crrent environment humidity sensor"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Humidity"

    @property
    def device_class(self) -> str:
        return DEVICE_CLASS_HUMIDITY

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_humidity", None)

    @property
    def native_unit_of_measurement(self) -> str:
        return PERCENTAGE

    @property
    def state_class(self) -> str:
        return "measurement"


class CurrentTemperatureSensor(ApplianceEntity, SensorEntity):
    """Current environment relative temperature sensor"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Temperature"

    @property
    def device_class(self) -> str:
        return DEVICE_CLASS_TEMPERATURE

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_temperature", None)

    @property
    def native_unit_of_measurement(self) -> str:
        return TEMP_CELSIUS

    @property
    def state_class(self) -> str:
        return "measurement"


class TankLevelSensor(ApplianceEntity, SensorEntity):
    """Current tank water level sensor"""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        level = getattr(coordinator.appliance.state, "tank_level", 0)
        self.enabled_by_default = level > 0 and level < 100

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Water Level"

    @property
    def native_value(self):
        return getattr(self.appliance.state, "tank_level", None)

    @property
    def native_unit_of_measurement(self) -> str:
        return PERCENTAGE

    @property
    def state_class(self) -> str:
        return "measurement"

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.enabled_by_default
