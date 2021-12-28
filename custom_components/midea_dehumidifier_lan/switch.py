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
    async_add_entities(PumpSwitch(c) for c in hub.coordinators if c.is_dehumidifier())
    async_add_entities(SleepSwitch(c) for c in hub.coordinators if c.is_dehumidifier())


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
    def icon(self) -> str:
        return "mdi:air-purifier"

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "ion_mode", False)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""

        self.apply("ion_mode", True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply("ion_mode", False)


class PumpSwitch(ApplianceEntity, SwitchEntity):
    """Pump switches"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Pump"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_pump_"

    @property
    def icon(self) -> str:
        return "mdi:pump"

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "pump", False)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply("pump", True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply("pump", False)


class SleepSwitch(ApplianceEntity, SwitchEntity):
    """Sleep mode switch"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Sleep"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_sleep_"

    @property
    def icon(self) -> str:
        return "mdi:weather-night"

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "sleep", False)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply("sleep", False)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply("sleep", False)
