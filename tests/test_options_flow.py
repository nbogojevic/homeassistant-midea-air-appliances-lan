"""Regression tests for editing an existing integration's appliances."""

from copy import deepcopy
from unittest.mock import Mock, patch

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_INCLUDE,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TTL,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.midea_dehumidifier_lan.const import (
    CONF_MOBILE_APP,
    CONF_TOKEN_KEY,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DISCOVERY_LAN,
    DISCOVERY_WAIT,
    DOMAIN,
)


@pytest.fixture
def options_entry(hass):
    """An existing entry with one appliance not currently in the runtime hub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=CURRENT_CONFIG_VERSION,
        unique_id="user@example.com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
            CONF_MOBILE_APP: DEFAULT_APP,
            CONF_INCLUDE: ["0xa1"],
            CONF_DEVICES: [
                {
                    CONF_ID: "123",
                    CONF_UNIQUE_ID: "SERIAL123",
                    CONF_NAME: "Dehumidifier",
                    CONF_TYPE: "0xa1",
                    CONF_IP_ADDRESS: "192.0.2.1",
                    CONF_TOKEN: "TOKEN",
                    CONF_TOKEN_KEY: "KEY",
                    CONF_API_VERSION: 3,
                    CONF_DISCOVERY: DISCOVERY_WAIT,
                    CONF_TTL: 5,
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {entry.entry_id: Mock(coordinators=[])}
    return entry


async def test_options_updates_existing_entry(hass, options_entry, midea_no_appliances):
    """Save appliance settings without replacing the entry or copying into options."""
    entry = options_entry
    original = deepcopy(dict(entry.data))
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "appliance"

    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Renamed dehumidifier",
                CONF_DISCOVERY: DISCOVERY_WAIT,
                CONF_TTL: 10,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert entry.options == {}
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.unique_id == "user@example.com"
    assert entry.data[CONF_USERNAME] == original[CONF_USERNAME]
    assert entry.data[CONF_PASSWORD] == original[CONF_PASSWORD]
    assert entry.data[CONF_DEVICES][0][CONF_NAME] == "Renamed dehumidifier"
    assert entry.data[CONF_DEVICES][0][CONF_TTL] == 10
    assert entry.data[CONF_DEVICES][0][CONF_UNIQUE_ID] == "SERIAL123"
    reload.assert_awaited_once_with(entry.entry_id)


async def test_failed_options_does_not_mutate_entry(
    hass, options_entry, midea_no_appliances
):
    """Changes to the working copy must not leak into persisted config on errors."""
    entry = options_entry
    original = deepcopy(dict(entry.data))
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Unsaved name",
                CONF_DISCOVERY: DISCOVERY_LAN,
                CONF_IP_ADDRESS: "not-an-address",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_ip_address"}
    assert entry.data == original
    reload.assert_not_called()
