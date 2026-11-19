"""Diagnostics support for Midea Air Appliances (LAN)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.const import CONF_TOKEN_KEY, DOMAIN

TO_REDACT = {
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TOKEN_KEY,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    "address",
    "appliance_id",
    "key",
    "mac",
    "serial_number",
    "ssid",
}


def _hex(value: Any) -> str | None:
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return None


def _appliance_diagnostics(coordinator: ApplianceUpdateCoordinator) -> dict[str, Any]:
    appliance = coordinator.appliance
    state = appliance.state
    last_exception = coordinator.last_exception
    return {
        "appliance": {
            "address": appliance.address,
            "appliance_id": appliance.appliance_id,
            "firmware_version": appliance.firmware_version,
            "key": appliance.key,
            "mac": getattr(appliance, "mac", None),
            "model": appliance.model,
            "name": appliance.name,
            "online": appliance.online,
            "protocol_version": getattr(appliance, "protocol_version", None),
            "serial_number": appliance.serial_number,
            "ssid": getattr(appliance, "ssid", None),
            "token": appliance.token,
            "type": appliance.type,
            "version": appliance.version,
        },
        "coordinator": {
            "available": coordinator.available,
            "discovery_mode": coordinator.discovery_mode,
            "last_exception": str(last_exception) if last_exception else None,
            "last_update_success": coordinator.last_update_success,
        },
        "state": {
            "capabilities": getattr(state, "capabilities", None),
            "capabilities_data": _hex(getattr(state, "capabilities_data", None)),
            "error_code": getattr(state, "error_code", None),
            "latest_data": _hex(getattr(state, "latest_data", None)),
        },
    }


def _coordinators(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[ApplianceUpdateCoordinator]:
    if hub := hass.data.get(DOMAIN, {}).get(entry.entry_id):
        return hub.coordinators
    return []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "appliances": [
                _appliance_diagnostics(coordinator)
                for coordinator in _coordinators(hass, entry)
            ],
        },
        TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    identifiers = {
        identifier for domain, identifier in device.identifiers if domain == DOMAIN
    }
    coordinator = next(
        (
            coordinator
            for coordinator in _coordinators(hass, entry)
            if str(coordinator.appliance.serial_number) in identifiers
        ),
        None,
    )
    return async_redact_data(
        {
            "appliance": (_appliance_diagnostics(coordinator) if coordinator else None),
        },
        TO_REDACT,
    )
