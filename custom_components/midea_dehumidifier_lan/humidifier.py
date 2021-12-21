"""Adds dehumidifer entity for each dehumidifer appliance."""

import logging

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import (
    MODE_AUTO,
    MODE_BOOST,
    MODE_COMFORT,
    MODE_NORMAL,
    SUPPORT_MODES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import ApplianceEntity, Hub
from custom_components.midea_dehumidifier_lan.const import DOMAIN

_LOGGER = logging.getLogger(__name__)
AVAILABLE_MODES = [MODE_AUTO, MODE_NORMAL, MODE_BOOST, MODE_COMFORT]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up dehumidifier entites"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidifierEntity(coordinator) for coordinator in hub.coordinators
    )


class DehumidifierEntity(ApplianceEntity, HumidifierEntity):
    """(de)Humidifer entity for Midea appliances """

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return ""

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_"

    @property
    def is_on(self):
        return getattr(self.appliance.state, "is_on", False)

    @property
    def device_class(self):
        return HumidifierDeviceClass.DEHUMIDIFIER

    @property
    def target_humidity(self):
        return getattr(self.appliance.state, "target_humidity", 0)

    @property
    def supported_features(self):
        return SUPPORT_MODES

    @property
    def available_modes(self):
        return AVAILABLE_MODES

    @property
    def mode(self):
        curr_mode = getattr(self.appliance.state, "mode", 1)
        if curr_mode == 1:
            return MODE_NORMAL
        if curr_mode == 2:
            return MODE_COMFORT
        if curr_mode == 3:
            return MODE_AUTO
        if curr_mode == 4:
            return MODE_BOOST
        _LOGGER.warning("Unknown mode %d", curr_mode)
        return MODE_NORMAL

    @property
    def min_humidity(self):
        """Return the min humidity set."""
        return 40

    @property
    def max_humidity(self):
        """Return the max humidity set."""
        return 85

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        setattr(self.appliance.state, "is_on", True)
        self.appliance.apply()

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        setattr(self.appliance.state, "is_on", False)
        self.appliance.apply()

    def set_mode(self, mode):
        """Set new target preset mode."""
        if mode == MODE_NORMAL:
            curr_mode = 1
        elif mode == MODE_COMFORT:
            curr_mode = 2
        elif mode == MODE_AUTO:
            curr_mode = 3
        elif mode == MODE_BOOST:
            curr_mode = 4
        else:
            _LOGGER.warning("Unsupported dehumidifer mode %s", mode)
            curr_mode = 1
        setattr(self.appliance.state, "mode", curr_mode)
        self.appliance.apply()

    def set_humidity(self, humidity):
        """Set new target humidity."""
        setattr(self.appliance.state, "target_humidity", humidity)
        self.appliance.apply()
