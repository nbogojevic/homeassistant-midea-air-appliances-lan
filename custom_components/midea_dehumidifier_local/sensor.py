"""Adds humidity sensors for each dehumidifer appliance."""

from custom_components.midea_dehumidifier_local import (
    ApplianceUpdateCoordinator,
    Hub,
    ApplianceEntity,
)
from custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.sensor import SensorEntity
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
        CurrentHumiditySensor(coordinator) for coordinator in hub.coordinators
    )


class CurrentHumiditySensor(ApplianceEntity, SensorEntity):
    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def name_suffix(self) -> str:
        return " Humidity"

    @property
    def unique_id_prefix(self) -> str:
        return "midea_dehumidifier_humidity_"

    @property
    def device_class(self):
        return "humidity"

    @property
    def native_value(self):
        return getattr(self.appliance.state, "current_humidity", None)

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return "measurement"
