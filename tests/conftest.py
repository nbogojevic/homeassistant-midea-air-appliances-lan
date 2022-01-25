# pylint: disable=protected-access,redefined-outer-name
# pylint: disable=unused-argument
"""Global fixtures for integration."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from midea_beautiful.exceptions import CloudAuthenticationError, MideaError
from midea_beautiful.midea import APPLIANCE_TYPE_DEHUMIDIFIER, APPLIANCE_TYPE_AIRCON

from custom_components.midea_dehumidifier_lan.util import MideaClient

pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss
# persistent notifications. These calls would fail without this fixture since the
# persistent_notification integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(name="midea_invalid_auth")
def midea_invalid_auth():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(
            side_effect=CloudAuthenticationError(34, "45", "some@example.com")
        ),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[]),
    ):
        yield


@pytest.fixture(name="midea_internal_exception")
def midea_internal_exception():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(side_effect=MideaError("midea_internal_exception")),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[]),
    ):
        yield


@pytest.fixture(name="midea_no_appliances")
def midea_no_appliances():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[]),
    ):
        yield


@pytest.fixture(name="midea_single_appliances")
def midea_single_appliances(dehumidifier_mock):
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[dehumidifier_mock]),
    ):
        yield


@pytest.fixture(name="midea_two_appliances")
def midea_two_appliances(dehumidifier_mock, airconditioner_mock):
    """Skip calls to get data from API."""
    dehumidifier_mock()
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[dehumidifier_mock, airconditioner_mock]),
    ):
        yield


@pytest.fixture(name="dehumidifier_mock")
def dehumidifier_mock():
    """Mock dehumidifier appliance"""
    dehumidifier_mock = MagicMock()
    dehumidifier_mock.type = APPLIANCE_TYPE_DEHUMIDIFIER
    dehumidifier_mock.version = 3
    dehumidifier_mock.name = "Test Name"
    dehumidifier_mock.address = "192.0.2.1"
    dehumidifier_mock.token = "TOKEN"
    dehumidifier_mock.key = "KEY"
    dehumidifier_mock.appliance_id = "654321"
    dehumidifier_mock.serial_number = "SN654321"
    return dehumidifier_mock


@pytest.fixture(name="airconditioner_mock")
def airconditioner_mock():
    """Mock air conditioner appliance"""
    airconditioner_mock = MagicMock()
    airconditioner_mock.type = APPLIANCE_TYPE_AIRCON
    airconditioner_mock.version = 3
    airconditioner_mock.name = "Test AC"
    airconditioner_mock.address = "192.0.2.2"
    airconditioner_mock.token = "TOKENAC"
    airconditioner_mock.key = "KEYAC"
    airconditioner_mock.appliance_id = "65432123456"
    airconditioner_mock.serial_number = "AC654321"
    return airconditioner_mock


@pytest.fixture(name="midea_two_appliances_one_supported")
def midea_two_appliances_one_supported():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[Mock(), Mock()]),
    ):
        yield
