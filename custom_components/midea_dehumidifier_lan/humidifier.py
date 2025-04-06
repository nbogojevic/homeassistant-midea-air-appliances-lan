"""Adds dehumidifer entity for each dehumidifer appliance."""

import logging
from typing import Final

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import HumidifierEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.const import (
    ATTR_RUNNING,
    DOMAIN,
    MAX_TARGET_HUMIDITY,
    MIN_TARGET_HUMIDITY,
)
from custom_components.midea_dehumidifier_lan.hub import Hub

_LOGGER = logging.getLogger(__name__)

MODE_SET: Final = "Set"
MODE_DRY: Final = "Dry"
MODE_SMART: Final = "Smart"
MODE_CONTINOUS: Final = "Continuous"
MODE_PURIFIER: Final = "Purifier"
MODE_ANTIMOULD: Final = "Antimould"
MODE_FAN: Final = "Fan"

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up dehumidifier entites"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidifierEntity(c) for c in hub.coordinators if c.is_dehumidifier()
    )


_MODES = [
    (1, MODE_SET),
    (2, MODE_CONTINOUS),
    (3, MODE_SMART),
    (4, MODE_DRY),
    (6, MODE_PURIFIER),
    (7, MODE_ANTIMOULD),
]

_MODES_FROM_CAPABILITY = {
    1: [MODE_PURIFIER],
    2: [MODE_ANTIMOULD],
    3: [MODE_PURIFIER, MODE_ANTIMOULD],
    4: [MODE_FAN],
}


# pylint: disable=too-many-ancestors,too-many-instance-attributes
class DehumidifierEntity(ApplianceEntity, HumidifierEntity):
    """(de)Humidifer entity for Midea dehumidifier"""

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _attr_max_humidity = MAX_TARGET_HUMIDITY
    _attr_min_humidity = MIN_TARGET_HUMIDITY
    _attr_supported_features = HumidifierEntityFeature.MODES
    _name_suffix = ""
    _add_extra_attrs = True

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

        self._attr_mode = None
        self._attr_available_modes = [MODE_SET]

    def on_online(self, update: bool) -> None:
        capabilities = self.coordinator.appliance.state.capabilities

        self._attr_available_modes = [MODE_SET]
        if capabilities.get("auto"):
            self._attr_available_modes.append(MODE_SMART)
        self._attr_available_modes.append(MODE_CONTINOUS)
        if capabilities.get("dry_clothes"):
            self._attr_available_modes.append(MODE_DRY)

        more_modes = capabilities.get("mode", 0)
        self._attr_available_modes += _MODES_FROM_CAPABILITY.get(more_modes, [])

        super().on_online(update)

    def on_update(self) -> None:
        dehumi = self.dehumidifier()
        self._attr_mode = next((i[1] for i in _MODES if i[0] == dehumi.mode), MODE_SET)
        self._attr_target_humidity = dehumi.target_humidity
        self._attr_current_humidity = (
            dehumi.current_humidity
        )  # add new attribute current_humidity
        self._attr_is_on = dehumi.running
        super().on_update()

    def turn_on(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_mode(self, mode) -> None:
        """Set new target preset mode."""
        midea_mode = next((i[0] for i in _MODES if i[1] == mode), None)
        if midea_mode is None:
            _LOGGER.debug("Unsupported dehumidifer mode %s", mode)
            midea_mode = 1
        self.apply("mode", midea_mode)

    def set_humidity(self, humidity) -> None:
        """Set new target humidity."""
        self.apply("target_humidity", humidity)
