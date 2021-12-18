"""Support for ION mode switch"""
from config.custom_components.midea_dehumidifier_local import (
    ApplianceUpdateCoordinator,
    Hub,
    ApplianceEntity,
)
from config.custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IonSwitch(coordinator) for coordinator in hub.coordinators
    )


class IonSwitch(ApplianceEntity, SwitchEntity):
    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def name_suffix(self) -> str:
        return " Ion Mode"

    @property
    def unique_id_prefix(self) -> str:
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
        self.appliance.apply()

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        setattr(self.appliance.state, "ion_mode", False)
        self.appliance.apply()
