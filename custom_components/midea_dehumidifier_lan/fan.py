"""Adds fan entity for each dehumidifer appliance."""

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
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
    """Sets up fan entity for managing dehumidifer fan"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(DehumidiferFan(coordinator) for coordinator in hub.coordinators)


class DehumidiferFan(ApplianceEntity, FanEntity):
    """Entity for managing dehumidifer fan"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Fan"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_fan_"

    @property
    def percentage(self):
        return getattr(self.appliance.state, "fan_speed", 0)

    @property
    def supported_features(self):
        return SUPPORT_SET_SPEED

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        setattr(self.appliance.state, "fan_speed", percentage)
        self.appliance.apply()
