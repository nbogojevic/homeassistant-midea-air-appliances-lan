"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any

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

from midea_beautiful import appliance_state, connect_to_cloud, find_appliances
from midea_beautiful.appliance import DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    MideaError,
    MideaNetworkError,
    ProtocolError,
)
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY, SUPPORTED_APPS

from .const import (
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


def _supported_appliance(appliance: LanDevice) -> bool:
    """Checks if appliance is supported by integration"""
    return DehumidifierAppliance.supported(appliance.type)


def _unreachable_appliance_schema(
    name: str,
    ip: str = IGNORED_IP_ADDRESS,
    use_cloud: bool = False,
):
    return vol.Schema(
        {
            vol.Required(CONF_IGNORE_APPLIANCE, default=False): bool,
            vol.Optional(CONF_IP_ADDRESS, default=ip): str,
            vol.Optional(CONF_NAME, default=name): str,
            vol.Optional(CONF_TOKEN): str,
            vol.Optional(CONF_TOKEN_KEY): str,
            vol.Required(CONF_USE_CLOUD, default=use_cloud): bool,
        }
    )


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


def _user_schema(username: str, password: str, app: str):

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_MOBILE_APP, default=app): vol.In(
                [app for app in SUPPORTED_APPS.keys()]
            ),
            vol.Required(CONF_ADVANCED_SETTINGS, default=False): bool,
        }
    )


class FlowException(Exception):
    def __init__(self, message, cause=None) -> None:
        self.message = message
        self.cause = cause


def _validate_appliance(cloud: MideaCloud, appliance: LanDevice, conf: dict):
    """
    Validates that appliance configuration is correct and matches physical
    device
    """
    use_cloud = conf.get(CONF_USE_CLOUD, False)
    if appliance.ip == IGNORED_IP_ADDRESS or (appliance.ip is None and not use_cloud):
        _LOGGER.debug("Ignored appliance with id=%s", appliance.id)
        return
    try:
        if use_cloud:
            discovered = appliance_state(
                cloud=cloud,
                use_cloud=use_cloud,
                id=appliance.id,
            )
        else:
            try:
                ipaddress.IPv4Address(appliance.ip)
            except Exception as ex:
                raise FlowException("invalid_ip_address", appliance.ip) from ex
            discovered = appliance_state(
                ip=appliance.ip,
                cloud=cloud,
            )
    except ProtocolError as ex:
        raise FlowException("connection_error", str(ex))
    except AuthenticationError as ex:
        raise FlowException("invalid_auth", str(ex))
    except MideaNetworkError as ex:
        raise FlowException("cannot_connect", str(ex))
    except MideaError as ex:
        raise FlowException("not_discovered", str(ex))
    if discovered is None:
        raise FlowException("not_discovered", appliance.ip)
    appliance.update(discovered)


class MideaLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Configuration flow for Midea dehumidifiers on local network uses discovery based on
    Midea cloud, so it first requires credentials for it.
    If some appliances are registered in the cloud, but not discovered, configuration
    flow will prompt for additional information.
    """

    VERSION = CURRENT_CONFIG_VERSION

    def __init__(self):
        self.cloud_credentials: dict = None  # type: ignore
        self.cloud: MideaCloud = None  # type: ignore
        self.appliance_idx = -1
        self.appliances: list[LanDevice] = []
        self.devices_conf: list[dict] = []
        self.conf = {}
        self.advanced_settings = False

    def _connect_and_discover(self: MideaLocalConfigFlow):
        """Validates that cloud credentials are valid and discovers local appliances"""

        cloud = connect_to_cloud(
            account=self.conf[CONF_USERNAME],
            password=self.conf[CONF_PASSWORD],
            appkey=self.conf[CONF_APPKEY],
            appid=self.conf[CONF_APPID],
        )
        if cloud is None:
            raise FlowException("no_cloud")

        networks = self.conf.get(CONF_NETWORK_RANGE, [])
        if isinstance(networks, str):
            networks = [networks]
        if appliances := find_appliances(cloud, networks=networks):
            self.devices_conf = [{} for _ in appliances]
        else:
            self.devices_conf = []
        self.appliances = appliances
        self.cloud = cloud

    async def _validate_discovery_phase(self, user_input: dict[str, Any] | None):

        if self.advanced_settings:
            if self.conf is not None and user_input is not None:
                if CONF_APPKEY not in user_input or CONF_APPID not in user_input:
                    raise FlowException("invalid_appkey")
                self.conf[CONF_APPKEY] = user_input[CONF_APPKEY]
                self.conf[CONF_APPID] = user_input[CONF_APPID]
                if network_range := user_input.get(CONF_NETWORK_RANGE):
                    try:
                        ipaddress.IPv4Network(network_range, strict=False)
                    except Exception as ex:
                        raise FlowException("invalid_ip_range", network_range) from ex
                    self.conf[CONF_NETWORK_RANGE] = network_range
                self.conf[CONF_USE_CLOUD] = user_input[CONF_USE_CLOUD]
            else:
                _LOGGER.error("Expected previous configuration")
                raise FlowException("invalid_state")
        else:
            if user_input is None:
                _LOGGER.error("Expected user input")
                raise FlowException("invalid_state")
            self.conf = user_input
            self.conf[CONF_USE_CLOUD] = False
            if app := user_input.get(CONF_MOBILE_APP):
                if app_key_id := SUPPORTED_APPS.get(app):
                    self.conf.update(app_key_id)
                else:
                    raise FlowException("invalid_app_name", app)
            else:
                self.conf[CONF_APPKEY] = DEFAULT_APPKEY
                self.conf[CONF_APPID] = DEFAULT_APP_ID
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

        self.appliance_idx = -1

        await self.hass.async_add_executor_job(self._connect_and_discover)

        if self.conf[CONF_USE_CLOUD]:
            for i, appliance in enumerate(self.appliances):
                self.devices_conf[i][CONF_USE_CLOUD] = True
        else:
            for i, appliance in enumerate(self.appliances):
                if _supported_appliance(appliance):
                    if not appliance.ip:
                        self.appliance_idx = i
                        break
            if self.appliance_idx >= 0:
                return await self.async_step_unreachable_appliance()

        return await self._async_add_entry()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        self.advanced_settings = False
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict = {}
        self.error_cause = ""

        username = DEFAULT_USERNAME
        password = DEFAULT_PASSWORD
        app = DEFAULT_APP
        if user_input is not None:
            try:
                username = user_input.get(CONF_USERNAME, username)
                password = user_input.get(CONF_PASSWORD, password)
                app = user_input.get(CONF_MOBILE_APP, app)
                return await self._validate_discovery_phase(user_input)
            except FlowException as ex:
                self.error_cause = ex.cause
                errors["base"] = ex.message
            except CloudAuthenticationError as ex:
                self.error_cause = f"{ex.error_code} - {ex.message}"
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(username=username, password=password, app=app),
            description_placeholders=self.placeholders(),
            errors=errors,
        )

    async def async_step_advanced_settings(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict = {}
        self.error_cause = ""
        self.advanced_settings = True
        if user_input is None:
            user_input = {}
        else:
            try:
                return await self._validate_discovery_phase(user_input)
            except FlowException as ex:
                self.error_cause = ex.cause
                errors["base"] = ex.message
            except CloudAuthenticationError as ex:
                self.error_cause = f"{ex.error_code} - {ex.message}"
                errors["base"] = "invalid_auth"

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
            description_placeholders=self.placeholders(),
            errors=errors,
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

            appliance.ip = user_input.get(CONF_IP_ADDRESS, IGNORED_IP_ADDRESS)
            appliance.name = user_input.get(CONF_NAME, appliance.name)
            appliance.token = user_input.get(CONF_TOKEN, "")
            appliance.key = user_input.get(CONF_TOKEN_KEY, "")

            device_conf[CONF_USE_CLOUD] = user_input.get(
                CONF_USE_CLOUD, self.conf.get(CONF_USE_CLOUD, False)
            )

            try:
                await self.hass.async_add_executor_job(
                    _validate_appliance,
                    self.cloud,
                    appliance,
                    device_conf,
                )
                # Find next unreachable appliance
                self.appliance_idx = self.appliance_idx + 1
                while self.appliance_idx < len(self.appliances):
                    if _supported_appliance(appliance):
                        if self.appliances[self.appliance_idx].ip is None:
                            return await self.async_step_unreachable_appliance()
                    self.appliance_idx = self.appliance_idx + 1

                # If no unreachable appliances, create entry
                if self.appliance_idx >= len(self.appliances):
                    return await self._async_add_entry()
                appliance = self.appliances[self.appliance_idx]

            except FlowException as ex:
                self.error_cause = ex.cause
                errors["base"] = ex.message

        name = appliance.name
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=_unreachable_appliance_schema(name),
            description_placeholders=self.placeholders(appliance=appliance),
            errors=errors,
        )

    def placeholders(self, appliance: LanDevice = None):
        placeholders = {
            TAG_CAUSE: self.error_cause or "",
        }
        if appliance:
            placeholders[TAG_ID] = appliance.id
            placeholders[TAG_NAME] = appliance.name
        return placeholders

    async def _async_add_entry(self):
        if self.conf is not None:
            for i, appliance in enumerate(self.appliances):
                if not _supported_appliance(appliance):
                    continue
                if self.devices_conf[i].get(CONF_USE_CLOUD, False) or (
                    appliance.ip and appliance.ip != IGNORED_IP_ADDRESS
                ):
                    self.devices_conf[i].update(
                        {
                            CONF_IP_ADDRESS: appliance.ip,
                            CONF_ID: appliance.id,
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
            else:
                return self.async_create_entry(
                    title="Midea Dehumidifiers",
                    data=self.conf,
                )
        else:
            _LOGGER.error("Configuration should have been set before reaching this!")
            raise FlowException("unexpected_state")

    async def async_step_reauth(self, config):
        """Handle reauthorization request from Abode."""
        self.conf = {**config}

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle reauthorization flow."""
        errors = {}
        username = self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = ""
        appkey = self.conf.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = self.conf.get(CONF_APPID, DEFAULT_APP_ID)
        network_range = self.conf.get(CONF_NETWORK_RANGE, "")
        use_cloud = self.conf.get(CONF_USE_CLOUD, False)
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=_advanced_settings_schema(
                    username=username,
                    password="",
                    appkey=appkey,
                    appid=appid,
                    network_range="",
                    use_cloud=use_cloud,
                ),
                description_placeholders=self.placeholders(),
                errors=errors,
            )

        try:
            return await self._validate_discovery_phase(user_input)
        except FlowException as ex:
            self.error_cause = ex.cause
            errors["base"] = ex.message
        except CloudAuthenticationError as ex:
            self.error_cause = f"{ex.error_code} - {ex.message}"
            errors["base"] = "invalid_auth"

        username = user_input.get(CONF_USERNAME, username)
        password = user_input.get(CONF_PASSWORD, "")
        appkey = user_input.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = user_input.get(CONF_APPID, DEFAULT_APP_ID)
        network_range = user_input.get(CONF_NETWORK_RANGE, network_range)
        use_cloud = user_input.get(CONF_USE_CLOUD, use_cloud)
        self.advanced_settings = True

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                appkey=appkey,
                appid=appid,
                network_range=network_range,
                use_cloud=use_cloud,
            ),
            description_placeholders=self.placeholders(),
            errors=errors,
        )
