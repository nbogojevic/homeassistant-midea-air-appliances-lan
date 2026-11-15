"""Regression tests for config-entry migration."""

from copy import deepcopy
import logging
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.midea_dehumidifier_lan import async_migrate_entry
from custom_components.midea_dehumidifier_lan.const import (
    CONF_MOBILE_APP,
    CONF_TOKEN_KEY,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DISCOVERY_LAN,
    LOCAL_BROADCAST,
    NAME,
)


@pytest.mark.parametrize("version", [1, 2])
async def test_migrate_entry(hass, version, caplog):
    """Update version and data through HA's API, preserving device identity."""
    device = {
        CONF_ID: "123",
        CONF_UNIQUE_ID: "SERIAL123",
        CONF_NAME: "Dehumidifier",
        CONF_TYPE: "0xa1",
        CONF_IP_ADDRESS: "192.0.2.1",
        CONF_TOKEN: "TOKEN",
        CONF_TOKEN_KEY: "KEY",
        CONF_API_VERSION: 3,
    }
    entry = MockConfigEntry(
        domain="midea_dehumidifier_lan",
        version=version,
        title="Old title",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "migration-secret-password",
            CONF_DEVICES: [device],
        },
    )
    entry.add_to_hass(hass)

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.midea_dehumidifier_lan"
    ):
        assert await async_migrate_entry(hass, entry)
    assert "migration-secret-password" not in caplog.text
    assert "user@example.com" not in caplog.text
    assert entry.version == CURRENT_CONFIG_VERSION
    assert entry.title == NAME
    assert entry.data[CONF_USERNAME] == "user@example.com"
    assert entry.data[CONF_PASSWORD] == "migration-secret-password"
    assert entry.data[CONF_MOBILE_APP] == DEFAULT_APP
    assert entry.data[CONF_BROADCAST_ADDRESS] == [LOCAL_BROADCAST]
    migrated_device = entry.data[CONF_DEVICES][0]
    assert migrated_device.items() >= device.items()
    assert migrated_device[CONF_DISCOVERY] == DISCOVERY_LAN


async def test_failed_migration_leaves_entry_unchanged(hass):
    """An unresolved serial number must not persist partial migration data."""
    original = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_DEVICES: [
            {
                CONF_ID: "123",
                CONF_NAME: "Unresolved device",
                CONF_TYPE: "0xa1",
            }
        ],
    }
    entry = MockConfigEntry(
        domain="midea_dehumidifier_lan",
        version=2,
        title="Old title",
        data=deepcopy(original),
    )
    entry.add_to_hass(hass)
    resolver = Mock(
        success=False,
        async_get_unique_id_if_missing=AsyncMock(),
    )
    with patch(
        "custom_components.midea_dehumidifier_lan._ApplianceIdResolver",
        return_value=resolver,
    ):
        assert not await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.title == "Old title"
    assert entry.data == original


async def test_current_entry_needs_no_migration(hass):
    """Do not resolve devices or modify entries already at the current version."""
    entry = MockConfigEntry(
        domain="midea_dehumidifier_lan",
        version=CURRENT_CONFIG_VERSION,
        data={CONF_DEVICES: []},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.midea_dehumidifier_lan._ApplianceIdResolver"
    ) as resolver:
        assert await async_migrate_entry(hass, entry)
    resolver.assert_not_called()
