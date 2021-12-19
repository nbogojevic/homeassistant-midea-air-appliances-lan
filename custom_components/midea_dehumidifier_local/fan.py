"""Adds fan entity for each dehumidifer appliance."""
from custom_components.midea_dehumidifier_local import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)
from custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidiferFan(coordinator) for coordinator in hub.coordinators
    )


class DehumidiferFan(ApplianceEntity, FanEntity):
    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def name_suffix(self) -> str:
        return " Fan"

    @property
    def unique_id_prefix(self) -> str:
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
