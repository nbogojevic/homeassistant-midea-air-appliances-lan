"""Adds humidity sensors for each dehumidifer appliance."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_local import ApplianceEntity, Hub
from custom_components.midea_dehumidifier_local.const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up current environment relative humidity sensors"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        CurrentHumiditySensor(coordinator) for coordinator in hub.coordinators
    )


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    """Crrent environment relative humidity sensor"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Humidity"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_humidity_"

    @property
    def device_class(self):
        return "humidity"

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_humidity", None)

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return "measurement"
