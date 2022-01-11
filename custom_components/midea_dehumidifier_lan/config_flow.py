"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any, Final

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_USERNAME,
)
import voluptuous as vol

from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    MideaError,
    MideaNetworkError,
    ProtocolError,
    RetryLaterError,
)
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY, SUPPORTED_APPS

from custom_components.midea_dehumidifier_lan import MideaClient

from .const import (  # pylint: disable=unused-import
    CONF_ADVANCED_SETTINGS,
    CONF_APPID,
    CONF_APPKEY,
    CONF_DETECT_AC_APPLIANCES,
    CONF_IGNORE_APPLIANCE,
    CONF_MOBILE_APP,
    CONF_NETWORK_RANGE,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    IGNORED_IP_ADDRESS,
    TAG_CAUSE,
    TAG_ID,
    TAG_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _unreachable_appliance_schema(
    name: str,
    address: str = IGNORED_IP_ADDRESS,
    use_cloud: bool = False,
):
    return vol.Schema(
        {
            vol.Required(CONF_IGNORE_APPLIANCE, default=False): bool,
            vol.Optional(CONF_IP_ADDRESS, default=address): str,
            vol.Optional(CONF_NAME, default=name): str,
            vol.Optional(CONF_TOKEN): str,
            vol.Optional(CONF_TOKEN_KEY): str,
            vol.Required(CONF_USE_CLOUD, default=use_cloud): bool,
        }
    )


# pylint: disable=too-many-arguments
def _advanced_settings_schema(
    username: str,
    password: str,
    appkey: str,
    appid: int,
    network_range: str,
    use_cloud: bool,
):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_APPKEY, default=appkey): str,
            vol.Required(CONF_APPID, default=appid): int,
            vol.Optional(CONF_NETWORK_RANGE, default=network_range): str,
            vol.Required(CONF_USE_CLOUD, default=use_cloud): bool,
            vol.Required(CONF_DETECT_AC_APPLIANCES, default=False): bool,
        }
    )


def _reauth_schema(
    password: str,
    appkey: str,
    appid: int,
):
    return vol.Schema(
        {
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_APPKEY, default=appkey): str,
            vol.Required(CONF_APPID, default=appid): int,
        }
    )


def _user_schema(username: str, password: str, app: str):

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_MOBILE_APP, default=app): vol.In(
                app for app in SUPPORTED_APPS
            ),
            vol.Required(CONF_ADVANCED_SETTINGS, default=False): bool,
        }
    )


class _FlowException(Exception):
    def __init__(self, message, cause: str = None) -> None:
        super().__init__()
        self.message = message
        self.cause = cause


# pylint: disable=too-many-instance-attributes
class MideaLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Configuration flow for Midea dehumidifiers on local network uses discovery based on
    Midea cloud, so it first requires credentials for it.
    If some appliances are registered in the cloud, but not discovered, configuration
    flow will prompt for additional information.
    """

    VERSION = CURRENT_CONFIG_VERSION

    cloud: MideaCloud | None = None  # type: ignore
    appliance_idx = -1
    appliances: list[LanDevice] = []
    devices_conf: list[dict] = []
    conf = {}
    advanced_settings = False
    client: Final = MideaClient()
    error_cause: str = ""
    errors: dict = {}

    def _supported_appliance(self, appliance: LanDevice) -> bool:
        """Checks if appliance is supported by integration"""
        aircon = False
        if self.conf.get(CONF_DETECT_AC_APPLIANCES, False):
            aircon = AirConditionerAppliance.supported(appliance.type)
        return aircon or DehumidifierAppliance.supported(appliance.type)

    def _validate_appliance(self, appliance: LanDevice, conf: dict):
        """
        Validates that appliance configuration is correct and matches physical
        device
        """
        assert self.cloud
        use_cloud = conf.get(CONF_USE_CLOUD, False)
        if appliance.address == IGNORED_IP_ADDRESS or (
            appliance.address is None and not use_cloud
        ):
            _LOGGER.debug("Ignored appliance with id=%s", appliance.appliance_id)
            return
        try:
            if use_cloud:
                discovered = self.client.appliance_state(
                    cloud=self.cloud,
                    use_cloud=use_cloud,
                    appliance_id=appliance.appliance_id,
                )
            else:
                try:
                    ipaddress.IPv4Address(appliance.address)
                except Exception as ex:
                    raise _FlowException(
                        "invalid_ip_address", appliance.address
                    ) from ex
                discovered = self.client.appliance_state(
                    address=appliance.address,
                    cloud=self.cloud,
                )
        except ProtocolError as ex:
            raise _FlowException("connection_error", str(ex)) from ex
        except AuthenticationError as ex:
            raise _FlowException("invalid_auth", str(ex)) from ex
        except MideaNetworkError as ex:
            raise _FlowException("cannot_connect", str(ex)) from ex
        except MideaError as ex:
            raise _FlowException("not_discovered", str(ex)) from ex
        if discovered is None:
            raise _FlowException("not_discovered", appliance.address)
        appliance.update(discovered)

    def _connect_and_discover(self: MideaLocalConfigFlow):
        """Validates that cloud credentials are valid and discovers local appliances"""

        cloud = self.client.connect_to_cloud(
            account=self.conf[CONF_USERNAME],
            password=self.conf[CONF_PASSWORD],
            appkey=self.conf[CONF_APPKEY],
            appid=self.conf[CONF_APPID],
        )
        networks = self.conf.get(CONF_NETWORK_RANGE, [])
        if isinstance(networks, str):
            networks = [networks]
        if appliances := self.client.find_appliances(cloud, networks=networks):
            self.devices_conf = [{} for _ in appliances]
        else:
            self.devices_conf = []
        self.appliances = appliances
        self.cloud = cloud

    async def _validate_discovery_phase(self, user_input: dict[str, Any] | None):
        assert user_input is not None
        if self.advanced_settings:
            assert self.conf is not None
            self.conf[CONF_APPKEY] = user_input[CONF_APPKEY]
            self.conf[CONF_APPID] = user_input[CONF_APPID]
            if network_range := user_input.get(CONF_NETWORK_RANGE):
                try:
                    ipaddress.IPv4Network(network_range, strict=False)
                except Exception as ex:
                    raise _FlowException("invalid_ip_range", network_range) from ex
                self.conf[CONF_NETWORK_RANGE] = network_range
            self.conf[CONF_USE_CLOUD] = user_input[CONF_USE_CLOUD]
            self.conf[CONF_DETECT_AC_APPLIANCES] = user_input[CONF_DETECT_AC_APPLIANCES]
        else:
            self.conf = user_input
            self.conf[CONF_USE_CLOUD] = False
            self.conf[CONF_DETECT_AC_APPLIANCES] = False
            app = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            self.conf.update(SUPPORTED_APPS.get(app, SUPPORTED_APPS[DEFAULT_APP]))
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

        self.appliance_idx = -1

        await self.hass.async_add_executor_job(self._connect_and_discover)

        if self.conf[CONF_USE_CLOUD]:
            for i, appliance in enumerate(self.appliances):
                self.devices_conf[i][CONF_USE_CLOUD] = True
        else:
            for i, appliance in enumerate(self.appliances):
                if self._supported_appliance(appliance):
                    if not appliance.address:
                        self.appliance_idx = i
                        break
            if self.appliance_idx >= 0:
                return await self.async_step_unreachable_appliance()

        return await self._async_add_entry()

    def _process_exception(self, ex: Exception):
        if isinstance(ex, _FlowException):
            self.error_cause = str(ex.cause)
            self.errors["base"] = ex.message
        elif isinstance(ex, CloudAuthenticationError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "invalid_auth"
        elif isinstance(ex, CloudError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "midea_client"
        elif isinstance(ex, RetryLaterError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "retry_later"
        elif isinstance(ex, MideaError):
            self.error_cause = f"{ex.message}"
            self.errors["base"] = "midea_client"
        else:
            raise ex

    async def _do_validate(self, user_input: dict[str, Any]):
        try:
            return await self._validate_discovery_phase(user_input)
        except Exception as ex:  # pylint: disable=broad-except
            self._process_exception(ex)
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        self.advanced_settings = False
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.errors = {}
        self.error_cause = ""

        username = DEFAULT_USERNAME
        password = DEFAULT_PASSWORD
        app = DEFAULT_APP
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, username)
            password = user_input.get(CONF_PASSWORD, password)
            app = user_input.get(CONF_MOBILE_APP, app)
            res = await self._do_validate(user_input)
            if res:
                return res

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(username=username, password=password, app=app),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )

    async def async_step_advanced_settings(
        self, user_input: dict[str, Any] | None = None
    ):
        """Step for managing advanced settings"""
        self.errors = {}
        self.error_cause = ""
        self.advanced_settings = True
        if user_input is not None:

            res = await self._do_validate(user_input)
            if res:
                return res
        else:
            user_input = {}

        username = user_input.get(
            CONF_USERNAME, self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        )
        password = user_input.get(
            CONF_PASSWORD, self.conf.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        )
        appkey = user_input.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = user_input.get(CONF_APPID, DEFAULT_APP_ID)
        network_range = user_input.get(
            CONF_NETWORK_RANGE, self.conf.get(CONF_NETWORK_RANGE, "")
        )
        use_cloud = user_input.get(CONF_USE_CLOUD, self.conf.get(CONF_USE_CLOUD, False))

        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                appkey=appkey,
                appid=appid,
                network_range=network_range,
                use_cloud=use_cloud,
            ),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )

    async def async_step_unreachable_appliance(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage the appliances that were not discovered automatically on LAN."""
        errors: dict = {}
        self.error_cause = ""
        appliance = self.appliances[self.appliance_idx]
        device_conf = self.devices_conf[self.appliance_idx]

        if user_input is not None:

            appliance.address = user_input.get(CONF_IP_ADDRESS, IGNORED_IP_ADDRESS)
            appliance.name = user_input.get(CONF_NAME, appliance.name)
            appliance.token = user_input.get(CONF_TOKEN, "")
            appliance.key = user_input.get(CONF_TOKEN_KEY, "")

            device_conf[CONF_USE_CLOUD] = user_input.get(
                CONF_USE_CLOUD, self.conf.get(CONF_USE_CLOUD, False)
            )

            try:
                await self.hass.async_add_executor_job(
                    self._validate_appliance,
                    appliance,
                    device_conf,
                )
                # Find next unreachable appliance
                self.appliance_idx = self.appliance_idx + 1
                while self.appliance_idx < len(self.appliances):
                    if self._supported_appliance(appliance):
                        if self.appliances[self.appliance_idx].address is None:
                            return await self.async_step_unreachable_appliance()
                    self.appliance_idx = self.appliance_idx + 1

                # If no unreachable appliances, create entry
                if self.appliance_idx >= len(self.appliances):
                    return await self._async_add_entry()
                appliance = self.appliances[self.appliance_idx]

            except _FlowException as ex:
                self.error_cause = str(ex.cause)
                errors["base"] = ex.message

        name = appliance.name
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=_unreachable_appliance_schema(name),
            description_placeholders=self._placeholders(appliance=appliance),
            errors=errors,
        )

    def _placeholders(self, appliance: LanDevice = None):
        placeholders = {
            TAG_CAUSE: self.error_cause or "",
        }
        if appliance:
            placeholders[TAG_ID] = appliance.appliance_id
            placeholders[TAG_NAME] = appliance.name

        return placeholders

    async def _async_add_entry(self):
        assert self.conf is not None
        for i, appliance in enumerate(self.appliances):
            if not self._supported_appliance(appliance):
                continue
            if self.devices_conf[i].get(CONF_USE_CLOUD, False) or (
                appliance.address and appliance.address != IGNORED_IP_ADDRESS
            ):
                self.devices_conf[i].update(
                    {
                        CONF_IP_ADDRESS: appliance.address,
                        CONF_ID: appliance.appliance_id,
                        CONF_NAME: appliance.name,
                        CONF_TYPE: appliance.type,
                        CONF_TOKEN: appliance.token,
                        CONF_TOKEN_KEY: appliance.key,
                        CONF_API_VERSION: appliance.version,
                    }
                )
        self.conf[CONF_DEVICES] = self.devices_conf
        existing_entry = await self.async_set_unique_id(self.conf[CONF_USERNAME])

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data=self.conf,
            )
            # Reload the config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")
        if len(self.devices_conf) == 0:
            return self.async_abort(reason="no_configured_devices")
        return self.async_create_entry(
            title="Midea Dehumidifiers",
            data=self.conf,
        )

    async def async_step_reauth(self, config):
        """Handle reauthorization request from Abode."""
        self.conf = {**config}

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle reauthorization flow."""
        self.errors = {}
        username = self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = ""
        appkey = self.conf.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = self.conf.get(CONF_APPID, DEFAULT_APP_ID)
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            appkey = user_input.get(CONF_APPKEY, DEFAULT_APPKEY)
            appid = user_input.get(CONF_APPID, DEFAULT_APP_ID)
            try:
                self.client.connect_to_cloud(
                    account=username,
                    password=password,
                    appkey=appkey,
                    appid=appid,
                )
            except Exception as ex:  # pylint: disable=broad-except
                self._process_exception(ex)
            else:
                self.conf[CONF_USERNAME] = username
                self.conf[CONF_PASSWORD] = password
                self.conf[CONF_APPKEY] = appkey
                self.conf[CONF_APPID] = appid
                return await self._async_add_entry()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(
                password=password,
                appkey=appkey,
                appid=appid,
            ),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )
