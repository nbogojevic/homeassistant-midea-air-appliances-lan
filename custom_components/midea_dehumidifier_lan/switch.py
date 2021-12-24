"""Support for ION mode switch"""

from homeassistant.components.switch import SwitchEntity
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
    """Sets up ion mode switches for dehumidifiers"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(IonSwitch(c) for c in hub.coordinators if c.is_dehumidifier())


class IonSwitch(ApplianceEntity, SwitchEntity):
    """Ion mode switches"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Ion Mode"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_ion_mode_"

    @property
    def icon(self):
        return "mdi:air-purifier"

    @property
    def is_on(self):
        return getattr(self.appliance.state, "ion_mode", False)

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        setattr(self.appliance.state, "ion_mode", True)
        self.do_apply()

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        setattr(self.appliance.state, "ion_mode", False)
        self.do_apply()
