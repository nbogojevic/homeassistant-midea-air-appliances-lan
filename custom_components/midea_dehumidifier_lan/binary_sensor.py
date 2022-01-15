"""Adds binary sensors for appliances."""

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_COLD,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import (
    DOMAIN,
    UNIQUE_DEHUMIDIFIER_PREFIX,
)
from custom_components.midea_dehumidifier_lan.hub import ApplianceEntity, Hub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up appliance binary sensors"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    # Dehumidifier sensors
    async_add_entities(
        TankFullSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        FilterReplacementSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    async_add_entities(
        DefrostingSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )


class TankFullSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes full tank binary sensors (indicated as problem as it prevents
    dehumidifier from operating)
    """

    _attr_device_class = DEVICE_CLASS_PROBLEM
    _name_suffix = " Tank Full"

    @property
    def is_on(self) -> bool:
        return self.dehumidifier().tank_full


class FilterReplacementSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes filter replacement binary sensors (indicated as problem)
    """

    _attr_device_class = DEVICE_CLASS_PROBLEM
    _attr_entity_registry_enabled_default = False
    _name_suffix = " Replace Filter"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return f"{UNIQUE_DEHUMIDIFIER_PREFIX}filter_"

    @property
    def is_on(self) -> bool:
        return self.dehumidifier().filter_indicator


class DefrostingSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes defrosting mode binary sensors (indicated as cold)
    """

    _attr_device_class = DEVICE_CLASS_COLD
    _attr_entity_registry_enabled_default = False
    _name_suffix = " Defrosting"

    @property
    def is_on(self) -> bool:
        return self.dehumidifier().defrosting
