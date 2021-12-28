"""Adds tank full binary sensors for each dehumidifer appliance."""

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Sets up full tank binary sensors"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        TankFullSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(FilterSensor(c) for c in hub.coordinators if c.is_dehumidifier())
    async_add_entities(
        DefrostingSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )


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
    def device_class(self) -> str:
        return "problem"

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "tank_full", False)


class FilterSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes filter replacement binary sensors (indicated as problem)
    """

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Replace Filter"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_filter_"

    @property
    def device_class(self) -> str:
        return "problem"

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "filter_indicator", False)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


class DefrostingSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes filter defrosting mode binary sensors (indicated as cold)
    """

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Defrosting"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_defrosting_"

    @property
    def device_class(self) -> str:
        return "cold"

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "defrosting", False)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False
