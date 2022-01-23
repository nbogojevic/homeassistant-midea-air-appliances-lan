"""Test integration configuration flow"""
# pylint: disable=unused-argument

from homeassistant.const import (
    CONF_API_VERSION,
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

from custom_components.midea_dehumidifier_lan.const import (
    CONF_TOKEN_KEY,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_WAIT,
)
from custom_components.midea_dehumidifier_lan.hub import (
    assure_valid_device_configuration,
    redacted_conf,
)


def test_redact():
    """Tests if full conf structure is correctly redacted"""
    conf = {
        CONF_USERNAME: "tnasd@example.com",
        CONF_PASSWORD: "asadasd",
    }
    redacted = redacted_conf(conf)

    assert redacted[CONF_PASSWORD] != conf[CONF_PASSWORD]
    assert redacted[CONF_USERNAME] != conf[CONF_USERNAME]
    assert len(redacted[CONF_PASSWORD]) == len(conf[CONF_PASSWORD])
    assert redacted.get(CONF_DEVICES) is None

    conf = {
        CONF_USERNAME: "bbbrrrqqq@exa@mple.com",
        CONF_PASSWORD: "PasswordPassword",
        "test": "test2",
        CONF_DEVICES: [
            {CONF_TOKEN: "ABCDEF"},
            {CONF_TOKEN: "12345", CONF_TOKEN_KEY: "4444", CONF_ID: "9876543210"},
            {
                CONF_TOKEN_KEY: "2332",
                CONF_NAME: "Name",
                CONF_UNIQUE_ID: "ABCDEFGHIJKLMN",
            },
            {CONF_PASSWORD: "ABC"},
            {CONF_TOKEN_KEY: 9876},
            {},
            44,
            {CONF_TOKEN: False},
        ],
    }
    redacted = redacted_conf(conf)

    assert redacted[CONF_PASSWORD] != conf[CONF_PASSWORD]
    assert redacted[CONF_PASSWORD] != conf[CONF_PASSWORD]
    assert redacted["test"] == conf["test"]
    assert len(redacted[CONF_PASSWORD]) == len(conf[CONF_PASSWORD])

    assert len(redacted[CONF_DEVICES]) == len(conf[CONF_DEVICES])
    assert redacted[CONF_DEVICES][0][CONF_TOKEN] == "******"
    assert redacted[CONF_DEVICES][0].get(CONF_TOKEN_KEY) is None
    assert redacted[CONF_DEVICES][1][CONF_TOKEN_KEY] == "****"
    assert redacted[CONF_DEVICES][1][CONF_TOKEN] == "*****"
    assert redacted[CONF_DEVICES][1][CONF_ID] == "987654****"
    assert redacted[CONF_DEVICES][2][CONF_TOKEN_KEY] == "****"
    assert redacted[CONF_DEVICES][2].get(CONF_TOKEN) is None
    assert redacted[CONF_DEVICES][2][CONF_NAME] == "Name"
    assert redacted[CONF_DEVICES][2][CONF_UNIQUE_ID] == "ABCDEF********"
    assert redacted[CONF_DEVICES][3][CONF_PASSWORD] == "ABC"
    assert redacted[CONF_DEVICES][3].get(CONF_TOKEN) is None
    assert redacted[CONF_DEVICES][3].get(CONF_TOKEN_KEY) is None
    assert redacted[CONF_DEVICES][4][CONF_TOKEN_KEY] == "****"
    assert redacted[CONF_DEVICES][7][CONF_TOKEN] == "*****"


def test_redact_device_conf():
    """Tests if device conf structure is correctly redacted"""
    conf = {
        CONF_TOKEN: "20222301",
        CONF_TOKEN_KEY: "01232022",
        CONF_NAME: "SomeName",
        CONF_API_VERSION: 3,
        CONF_ID: "1234567890",
        CONF_UNIQUE_ID: "12345678ABCDEFGH",
        CONF_TYPE: "0xa1",
    }
    redacted = redacted_conf(conf)

    assert redacted[CONF_TOKEN] == "********"
    assert redacted[CONF_TOKEN_KEY] == "********"
    assert redacted[CONF_NAME] == "SomeName"
    assert redacted[CONF_ID] == "123456****"
    assert redacted[CONF_UNIQUE_ID] == "12345678********"


def test_assure_valid_device_configuration():
    """Test if invalid configurations are updated correctly"""
    conf = {
        CONF_USERNAME: "bbbrrrqqq@exa@mple.com",
        CONF_PASSWORD: "PasswordPassword",
        "test": "test2",
        CONF_DEVICES: [
            {CONF_TOKEN: "ABCDEF"},
            {CONF_TOKEN: "12345", CONF_TOKEN_KEY: "4444", CONF_ID: "9876543210"},
            {CONF_TOKEN: "12345", CONF_TOKEN_KEY: "4444", CONF_IP_ADDRESS: "192.0.2.3"},
            {CONF_PASSWORD: "ABC"},
            {
                CONF_TOKEN: "12345",
                CONF_TOKEN_KEY: "4444",
                CONF_IP_ADDRESS: "192.0.2.3",
                CONF_DISCOVERY: DISCOVERY_CLOUD,
            },
            {CONF_TOKEN: "ABCDEF"},
        ],
    }
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][0])
    assert not valid
    assert conf[CONF_DEVICES][0][CONF_DISCOVERY] == DISCOVERY_CLOUD
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][0])
    assert valid
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][1])
    assert not valid
    assert conf[CONF_DEVICES][1][CONF_DISCOVERY] == DISCOVERY_WAIT
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][1])
    assert valid
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][2])
    assert not valid
    assert conf[CONF_DEVICES][2][CONF_DISCOVERY] == DISCOVERY_LAN
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][3])
    assert not valid
    assert conf[CONF_DEVICES][3][CONF_DISCOVERY] == DISCOVERY_CLOUD
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][4])
    assert valid
    assert conf[CONF_DEVICES][4][CONF_DISCOVERY] == DISCOVERY_CLOUD
    conf.pop(CONF_PASSWORD)
    valid = assure_valid_device_configuration(conf, conf[CONF_DEVICES][5])
    assert not valid
    assert conf[CONF_DEVICES][5][CONF_DISCOVERY] == DISCOVERY_IGNORE
