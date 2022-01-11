# pylint: disable=protected-access,redefined-outer-name
"""Global fixtures for integration."""

from unittest.mock import Mock, patch

import pytest

from custom_components.midea_dehumidifier_lan import MideaClient
from midea_beautiful.exceptions import CloudAuthenticationError, MideaError

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
        connect_to_cloud=Mock(side_effect=CloudAuthenticationError(34, "45")),
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
def midea_single_appliances():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[Mock()]),
    ):
        yield


@pytest.fixture(name="midea_two_appliances")
def midea_two_appliances():
    """Skip calls to get data from API."""
    with patch.multiple(
        MideaClient,
        connect_to_cloud=Mock(),
        appliance_state=Mock(),
        find_appliances=Mock(return_value=[Mock(), Mock()]),
    ):
        yield


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
