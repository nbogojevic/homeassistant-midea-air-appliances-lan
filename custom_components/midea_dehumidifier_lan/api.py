"""Library facade"""

from homeassistant.const import CONF_INCLUDE

import midea_beautiful as midea_beautiful_api
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
)

_SUPPORTABLE_APPLIANCES = {
    APPLIANCE_TYPE_AIRCON: AirConditionerAppliance.supported,
    APPLIANCE_TYPE_DEHUMIDIFIER: DehumidifierAppliance.supported,
}


def supported_appliance(conf: dict, appliance: LanDevice) -> bool:
    """Checks if appliance is supported by integration"""
    included = conf.get(CONF_INCLUDE, [])
    for type_id, check in _SUPPORTABLE_APPLIANCES.items():
        if type_id in included and check(appliance.type):
            return True
    return False


class MideaClient:
    """Delegate to midea API"""

    def connect_to_cloud(  # pylint: disable=no-self-use
        self, account: str, password: str, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
    ):
        """Delegate to midea_beautiful_api.connect_to_cloud"""
        return midea_beautiful_api.connect_to_cloud(
            account=account, password=password, appkey=appkey, appid=appid
        )

    def appliance_state(  # pylint: disable=too-many-arguments,no-self-use
        self,
        address: str = None,
        token: str = None,
        key: str = None,
        cloud: MideaCloud = None,
        use_cloud: bool = False,
        appliance_id: str = None,
    ):
        """Delegate to midea_beautiful_api.appliance_state"""
        return midea_beautiful_api.appliance_state(
            address=address,
            token=token,
            key=key,
            cloud=cloud,
            use_cloud=use_cloud,
            appliance_id=appliance_id,
            retries=5,
            cloud_timeout=6,
        )

    def find_appliances(  # pylint: disable=too-many-arguments,no-self-use
        self,
        cloud: MideaCloud = None,
        appkey: str = None,
        account: str = None,
        password: str = None,
        appid: str = None,
        addresses: list[str] = None,
        retries: int = 3,
        timeout: int = 3,
    ) -> list[LanDevice]:
        """Delegate to midea_beautiful_api.find_appliances"""
        return midea_beautiful_api.find_appliances(
            cloud=cloud,
            appkey=appkey,
            account=account,
            password=password,
            appid=appid,
            addresses=addresses,
            retries=retries,
            timeout=timeout,
        )


def is_climate(appliance: LanDevice) -> bool:
    """True if appliance is air conditioner"""
    return AirConditionerAppliance.supported(appliance.type)


def is_dehumidifier(appliance: LanDevice) -> bool:
    """True if appliance is dehumidifier"""
    return DehumidifierAppliance.supported(appliance.type)
