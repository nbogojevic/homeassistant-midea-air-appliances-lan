"""Diagnostics tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant.common import MockConfigEntry

from custom_components.midea_dehumidifier_lan.const import CONF_TOKEN_KEY, DOMAIN
from custom_components.midea_dehumidifier_lan.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


def _coordinator():
    state = SimpleNamespace(
        capabilities={"auto": True},
        capabilities_data=bytes.fromhex("b5010203"),
        error_code=0,
        latest_data=bytes.fromhex("a00102507f7f"),
    )
    appliance = SimpleNamespace(
        address="192.0.2.1",
        appliance_id="123456",
        firmware_version="1.2.3",
        key="KEY",
        mac="00:11:22:33:44:55",
        model="Model",
        name="Dehumidifier",
        online=True,
        protocol_version=3,
        serial_number="SERIAL123",
        ssid="midea_a1",
        state=state,
        token="TOKEN",
        type="0xa1",
        version=3,
    )
    return SimpleNamespace(
        appliance=appliance,
        available=True,
        discovery_mode="LAN",
        last_exception=None,
        last_update_success=True,
    )


def _entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
            CONF_DEVICES: [
                {
                    CONF_ID: "123456",
                    CONF_UNIQUE_ID: "SERIAL123",
                    CONF_IP_ADDRESS: "192.0.2.1",
                    CONF_TOKEN: "TOKEN",
                    CONF_TOKEN_KEY: "KEY",
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {entry.entry_id: Mock(coordinators=[_coordinator()])}
    return entry


async def test_config_entry_diagnostics(hass):
    """Raw protocol data is in diagnostics and secrets are redacted."""
    entry = _entry(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    appliance = result["appliances"][0]
    assert appliance["state"]["latest_data"] == "a00102507f7f"
    assert appliance["state"]["capabilities_data"] == "b5010203"
    assert appliance["state"]["capabilities"] == {"auto": True}
    for key in (
        "address",
        "appliance_id",
        "key",
        "mac",
        "serial_number",
        "ssid",
        "token",
    ):
        assert appliance["appliance"][key] == REDACTED
    data = result["entry"]["data"]
    assert result["entry"]["unique_id"] == REDACTED
    assert data[CONF_USERNAME] == REDACTED
    assert data[CONF_PASSWORD] == REDACTED
    for key in (CONF_ID, CONF_UNIQUE_ID, CONF_IP_ADDRESS, CONF_TOKEN, CONF_TOKEN_KEY):
        assert data[CONF_DEVICES][0][key] == REDACTED


async def test_device_diagnostics(hass):
    """Device diagnostics return the matching appliance only."""
    entry = _entry(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SERIAL123")},
    )

    result = await async_get_device_diagnostics(hass, entry, device)

    assert result["appliance"]["state"]["latest_data"] == "a00102507f7f"
    assert result["appliance"]["appliance"]["token"] == REDACTED
