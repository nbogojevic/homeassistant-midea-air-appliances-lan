"""Utility functions for Midea integration"""
from typing import cast

from homeassistant.core import HomeAssistant

from custom_components.midea_dehumidifier_lan.const import DOMAIN


def domain(hass: HomeAssistant) -> dict:
    """Returns current domain data as dictionary"""
    return cast(dict, hass.data[DOMAIN])
