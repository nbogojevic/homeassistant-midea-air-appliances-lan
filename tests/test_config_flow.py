"""Test integration configuration flow"""
# pylint: disable=unused-argument
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from midea_beautiful.midea import SUPPORTED_APPS

from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.midea_dehumidifier_lan.config_flow import MideaConfigFlow
from custom_components.midea_dehumidifier_lan.const import (
    CONF_ADVANCED_SETTINGS,
    CONF_APPID,
    CONF_APPKEY,
    CONF_DETECT_AC_APPLIANCES,
    CONF_MOBILE_APP,
    CONF_BROADCAST_ADDRESS,
    CONF_USE_CLOUD,
    DEFAULT_APP,
    DOMAIN,
)

MOCK_BASIC_CONFIG_PAGE = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
    CONF_MOBILE_APP: DEFAULT_APP,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = MideaConfigFlow()
    flow.hass = hass

    result: data_entry_flow.FlowResult = await flow.async_step_user(user_input=None)
    print(result)
    # pyright: reportTypedDictNotRequiredAccess=false

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_successful_config_flow(hass: HomeAssistant, midea_single_appliances):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_BASIC_CONFIG_PAGE
    )

    # Check that the config flow is complete and a new entry is created with
    # the input data
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Midea Dehumidifiers"
    assert result["data"][CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert len(result["data"]["devices"]) == 1
    assert result["result"]


async def test_successful_config_flow_midea_two_appliances(
    hass: HomeAssistant, midea_two_appliances
):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_BASIC_CONFIG_PAGE
    )

    # Check that the config flow is complete and a new entry is created with
    # the input data
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Midea Dehumidifiers"
    assert result["data"][CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert len(result["data"]["devices"]) == 2
    assert result["result"]


async def test_advanced_settings_config_flow(hass: HomeAssistant):
    """Test a advanced settings config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input: dict[str, Any] = {**MOCK_BASIC_CONFIG_PAGE}
    user_input[CONF_ADVANCED_SETTINGS] = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    # Check that the config flow is complete and a new entry is created with
    # the input data
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "advanced_settings"
    values = result["data_schema"]({})
    assert values[CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert values[CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert values[CONF_APPID] == SUPPORTED_APPS[DEFAULT_APP][CONF_APPID]
    assert values[CONF_APPKEY] == SUPPORTED_APPS[DEFAULT_APP][CONF_APPKEY]
    assert values[CONF_BROADCAST_ADDRESS] == ""
    assert not values[CONF_DETECT_AC_APPLIANCES]
    assert not values[CONF_USE_CLOUD]


async def test_advanced_settings_config_flow_success(
    hass: HomeAssistant, midea_single_appliances
):
    """Test a advanced settings config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input: dict[str, Any] = {**MOCK_BASIC_CONFIG_PAGE}
    user_input[CONF_ADVANCED_SETTINGS] = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    user_input = {
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_APPKEY: "test_appkey",
        CONF_APPID: 1000,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Midea Dehumidifiers"
    assert result["data"][CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert result["data"][CONF_APPKEY] == "test_appkey"
    assert result["data"][CONF_APPID] == 1000
    assert not result["data"][CONF_USE_CLOUD]
    assert len(result["data"]["devices"]) == 1
    assert result["result"]


async def test_advanced_settings_config_flow_success_network(
    hass: HomeAssistant, midea_single_appliances
):
    """Test a advanced settings config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input: dict[str, Any] = {**MOCK_BASIC_CONFIG_PAGE}
    user_input[CONF_ADVANCED_SETTINGS] = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    user_input = {
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_APPKEY: "test_appkey",
        CONF_BROADCAST_ADDRESS: "192.0.128.255",
        CONF_APPID: 1000,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Midea Dehumidifiers"
    assert result["data"]
    assert result["data"][CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert result["data"][CONF_APPKEY] == "test_appkey"
    assert result["data"][CONF_APPID] == 1000
    assert not result["data"][CONF_USE_CLOUD]
    assert result["data"][CONF_BROADCAST_ADDRESS] == "192.0.128.255"
    assert len(result["data"]["devices"]) == 1
    assert result["result"]


async def test_advanced_settings_config_invalid_network(hass: HomeAssistant):
    """Test a advanced settings with invalid network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input: dict[str, Any] = {**MOCK_BASIC_CONFIG_PAGE}
    user_input[CONF_ADVANCED_SETTINGS] = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    user_input = {
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_BROADCAST_ADDRESS: "655.123.123.333",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "advanced_settings"
    values = result["data_schema"]({})
    assert values[CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert values[CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert values[CONF_APPID] == SUPPORTED_APPS[DEFAULT_APP][CONF_APPID]
    assert values[CONF_APPKEY] == SUPPORTED_APPS[DEFAULT_APP][CONF_APPKEY]
    assert values[CONF_BROADCAST_ADDRESS] == "655.123.123.333"
    assert result["description_placeholders"]
    assert result["description_placeholders"].get("cause") == "655.123.123.333"
    assert not values[CONF_DETECT_AC_APPLIANCES]
    assert not values[CONF_USE_CLOUD]


async def test_advanced_settings_config_flow_success_use_cloud(
    hass: HomeAssistant, midea_single_appliances
):
    """Test a advanced settings config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input: dict[str, Any] = {**MOCK_BASIC_CONFIG_PAGE}
    user_input[CONF_ADVANCED_SETTINGS] = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    user_input = {
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_APPKEY: "test_appkey_cloud",
        CONF_APPID: 1001,
        CONF_USE_CLOUD: True,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Midea Dehumidifiers"
    assert result["data"][CONF_USERNAME] == MOCK_BASIC_CONFIG_PAGE[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == MOCK_BASIC_CONFIG_PAGE[CONF_PASSWORD]
    assert result["data"][CONF_APPKEY] == "test_appkey_cloud"
    assert result["data"][CONF_APPID] == 1001
    assert result["data"][CONF_USE_CLOUD]
    assert len(result["data"]["devices"]) == 1
    assert result["result"]


async def test_midea_invalid_auth_config_flow(hass: HomeAssistant, midea_invalid_auth):
    """Test a invalid username config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_BASIC_CONFIG_PAGE
    )

    # Check that the config flow is not complete
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"]
    assert result["description_placeholders"].get("cause") == "34 - 45"


async def test_midea_internal_exception(hass: HomeAssistant, midea_internal_exception):
    """Test an internal exception in midea communication config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_BASIC_CONFIG_PAGE
    )

    # Check that the config flow is not complete
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"]
    assert result["description_placeholders"].get("cause") == "midea_internal_exception"


async def test_config_flow_no_devices(hass: HomeAssistant, midea_no_appliances):
    """Test a successful config flow with no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_BASIC_CONFIG_PAGE
    )

    # Check that the config flow is aborted
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_configured_devices"


async def test_step_reauth(hass: HomeAssistant, midea_no_appliances):
    """Test the reauth flow."""
    conf = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=conf[CONF_USERNAME],
        data=conf,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=conf,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "password"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1


async def test_step_reauth_invalid_password(hass: HomeAssistant, midea_invalid_auth):
    """Test the reauth flow."""
    conf = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=conf[CONF_USERNAME],
        data=conf,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=conf,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "password"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"

    assert len(hass.config_entries.async_entries()) == 1
