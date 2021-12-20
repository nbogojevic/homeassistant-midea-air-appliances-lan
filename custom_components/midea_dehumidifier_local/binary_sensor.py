"""Adds tank full binary sensors for each dehumidifer appliance."""

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Sets up full tank binary sensors"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(TankFullSensor(coordinator) for coordinator in hub.coordinators)


class TankFullSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes full tank binary sensors (indicated as problem as it prevents
    dehumidifier from operating)
    """

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Tank Full"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_tank_full_"

    @property
    def device_class(self):
        return "problem"

    @property
    def is_on(self):
        return getattr(self.appliance.state, "tank_full", False)
