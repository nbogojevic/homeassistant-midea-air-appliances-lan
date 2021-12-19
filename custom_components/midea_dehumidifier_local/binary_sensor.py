"""Adds tank full binary sensors for each dehumidifer appliance."""

from custom_components.midea_dehumidifier_local import (
    ApplianceUpdateCoordinator,
    Hub,
    ApplianceEntity,
)
from custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.binary_sensor import BinarySensorEntity
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
        TankFullSensor(coordinator) for coordinator in hub.coordinators
    )


class TankFullSensor(ApplianceEntity, BinarySensorEntity):
    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def name_suffix(self) -> str:
        return " Tank Full"

    @property
    def unique_id_prefix(self) -> str:
        return "midea_dehumidifier_tank_full_"

    @property
    def device_class(self):
        return "problem"

    @property
    def is_on(self):
        return getattr(self.appliance.state, "tank_full", False)
