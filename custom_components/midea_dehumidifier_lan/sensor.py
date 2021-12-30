"""Adds humidity sensors for each dehumidifer appliance."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import ApplianceEntity, Hub
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


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    """Crrent environment humidity sensor"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Humidity"

    @property
    def device_class(self) -> str:
        return "humidity"

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_humidity", None)

    @property
    def native_unit_of_measurement(self) -> str:
        return "%"

    @property
    def state_class(self) -> str:
        return "measurement"


class CurrentTemperatureSensor(ApplianceEntity, SensorEntity):
    """Crrent environment relative temperature sensor"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Temperature"

    @property
    def device_class(self) -> str:
        return "temperature"

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_temperature", None)

    @property
    def native_unit_of_measurement(self) -> str:
        return "°C"

    @property
    def state_class(self) -> str:
        return "measurement"
