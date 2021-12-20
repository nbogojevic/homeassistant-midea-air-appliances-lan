"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any, Tuple

from homeassistant import config_entries, data_entry_flow, exceptions
from homeassistant.const import (
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

from midea_beautiful_dehumidifier import connect_to_cloud, find_appliances
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.exceptions import CloudAuthenticationError
from midea_beautiful_dehumidifier.lan import LanDevice, get_appliance_state
from midea_beautiful_dehumidifier.midea import DEFAULT_APPKEY, DISCOVERY_PORT

from .const import (
    CONF_IGNORE_APPLIANCE,
    CONF_TOKEN_KEY,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    IGNORED_IP_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_cloud(conf: dict) -> Tuple[MideaCloud, list[LanDevice]]:
    """Validates that cloud credentials are valid and discovers local appliances"""
    cloud = connect_to_cloud(
        appkey=DEFAULT_APPKEY,
        account=conf[CONF_USERNAME],
        password=conf[CONF_PASSWORD],
    )
    if cloud is None:
        raise exceptions.IntegrationError("no_cloud")

    appliances = find_appliances(
        cloud=cloud,
        broadcast_retries=2,
        broadcast_timeout=3,
    )

    return cloud, appliances


def validate_appliance(cloud: MideaCloud, appliance: LanDevice):
    """
    Validates that appliance configuration is correct and matches physical
    device
    """
    if appliance.ip == IGNORED_IP_ADDRESS or appliance.ip is None:
        _LOGGER.debug("Ignored appliance with id=%s", appliance.id)
        return True
    try:
        ipaddress.IPv4Network(appliance.ip)
    except Exception as ex:
        raise exceptions.IntegrationError("invalid_ip_address") from ex
    discovered = get_appliance_state(ip=appliance.ip, cloud=cloud)
    if discovered is not None:
        appliance.update(discovered)
        return True
    raise exceptions.IntegrationError("not_discovered")


class MideaLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Configuration flow for Midea dehumidifiers on local network uses discovery based on
    Midea cloud, so it first requires credentials for it.
    If some appliances are registered in the cloud, but not discovered, configuration
    flow will prompt for additional information.
    """

    def __init__(self):
        self._cloud_credentials: dict | None = None
        self._cloud = None
        self._appliance_idx = -1
        self._appliances: list[LanDevice] = []
        self._appliance_conf = []
        self._conf = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict = {}

        if user_input is not None:
            try:
                (
                    self._cloud,
                    self._appliances,
                ) = await self.hass.async_add_executor_job(validate_cloud, user_input)
                self._appliance_idx = -1
                self._conf = user_input
                for i, appliance in enumerate(self._appliances):
                    if not appliance.ip:
                        self._appliance_idx = i
                        break
                if self._appliance_idx >= 0:
                    return await self.async_step_unreachable_appliance()

                return await self._async_add_entry()
            except CloudAuthenticationError as ex:
                _LOGGER.error("Unable to log in to Midea cloud %s", ex)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_unreachable_appliance(self, user_input=None):
        """Manage the appliances that were not found on LAN."""
        errors: dict = {}
        appliance = self._appliances[self._appliance_idx]

        if user_input is not None:
            appliance.ip = (
                user_input[CONF_IP_ADDRESS]
                if not user_input[CONF_IGNORE_APPLIANCE]
                else IGNORED_IP_ADDRESS
            )
            appliance.port = DISCOVERY_PORT
            appliance.name = user_input[CONF_NAME]
            appliance.token = user_input[CONF_TOKEN] if CONF_TOKEN in user_input else ""
            appliance.key = (
                user_input[CONF_TOKEN_KEY] if CONF_TOKEN_KEY in user_input else ""
            )
            try:
                await self.hass.async_add_executor_job(
                    validate_appliance,
                    self._cloud,
                    appliance,
                )
                # Find next unreachable appliance
                self._appliance_idx = self._appliance_idx + 1
                while self._appliance_idx < len(self._appliances):
                    if self._appliances[self._appliance_idx].ip is None:
                        return await self.async_step_unreachable_appliance()
                    self._appliance_idx = self._appliance_idx + 1

                # If no unreachable appliances, create entry
                if self._appliance_idx >= len(self._appliances):
                    return await self._async_add_entry()
                appliance = self._appliances[self._appliance_idx]

            except exceptions.IntegrationError as ex:
                errors["base"] = str(ex)

        name = appliance.name
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IGNORE_APPLIANCE, default=False): bool,
                    vol.Optional(CONF_IP_ADDRESS, default=IGNORED_IP_ADDRESS): str,
                    vol.Optional(CONF_NAME, default=name): str,
                    vol.Optional(CONF_TOKEN): str,
                    vol.Optional(CONF_TOKEN_KEY): str,
                }
            ),
            description_placeholders={
                CONF_ID: appliance.id,
                CONF_NAME: name,
            },
            errors=errors,
        )

    async def _async_add_entry(self):
        if self._conf is not None:
            self._appliance_conf = []
            for appliance in self._appliances:
                if appliance.ip != IGNORED_IP_ADDRESS:
                    self._appliance_conf.append(
                        {
                            CONF_IP_ADDRESS: appliance.ip,
                            CONF_ID: appliance.id,
                            CONF_NAME: appliance.name,
                            CONF_TYPE: appliance.type,
                            CONF_TOKEN: appliance.token,
                            CONF_TOKEN_KEY: appliance.key,
                        }
                    )
            existing_entry = await self.async_set_unique_id(self._conf[CONF_USERNAME])
            self._conf[CONF_DEVICES] = self._appliance_conf
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=self._conf,
                )
                # Reload the config entry otherwise devices will remain unavailable
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )

                return self.async_abort(reason="reauth_successful")
            else:
                return self.async_create_entry(
                    title="Midea Dehumidifiers",
                    data=self._conf,
                )
        else:
            raise exceptions.InvalidStateError("unexpected_state")
