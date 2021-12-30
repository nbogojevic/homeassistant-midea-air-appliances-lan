"""Support for ION mode switch"""

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Sets up ion mode switches for dehumidifiers"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        MideaSwitch(c, "ion_mode", "Ion Mode", "mdi:air-purifier", capability="ion")
        for c in hub.coordinators
        if c.is_dehumidifier()
    )
    async_add_entities(
        MideaSwitch(c, "pump", "Pump", "mdi:pump", capability="pump")
        for c in hub.coordinators
        if c.is_dehumidifier()
    )
    async_add_entities(
        MideaSwitch(c, "sleep", "Sleep", "mdi:weather-night")
        for c in hub.coordinators
        if c.is_dehumidifier()
    )
    async_add_entities(
        MideaSwitch(c, "beep_prompt", "Beep", "mdi:bell-check")
        for c in hub.coordinators
        if c.is_dehumidifier()
    )


class MideaSwitch(ApplianceEntity, SwitchEntity):
    """Generic attr based switch"""

    def __init__(
        self,
        coordinator: ApplianceUpdateCoordinator,
        attr: str,
        suffix: str,
        icon: str,
        capability: str = None,
    ) -> None:
        self.attr = attr
        self.suffix = " " + suffix
        self.icon_name = icon
        self.enabled_by_default = False
        if capability:
            supports = getattr(coordinator.appliance.state, "supports", {})
            if supports.get(capability, 0):
                self.enabled_by_default = True

        super().__init__(coordinator)

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return self.suffix

    @property
    def icon(self):
        return self.icon_name or super().icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.enabled_by_default

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, self.attr, False)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""

        self.apply(self.attr, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply(self.attr, False)
