"""Test integration configuration flow"""
# pylint: disable=unused-argument

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_DEVICES,
    CONF_NAME,
    CONF_TOKEN,
)


from custom_components.midea_dehumidifier_lan.hub import redacted_conf
from custom_components.midea_dehumidifier_lan.const import (
    CONF_TOKEN_KEY,
)


def test_redact():
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
            {CONF_TOKEN: "12345", CONF_TOKEN_KEY: "4444"},
            {CONF_TOKEN_KEY: "2332", CONF_NAME: "Name"},
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
    assert redacted[CONF_DEVICES][2][CONF_TOKEN_KEY] == "****"
    assert redacted[CONF_DEVICES][2].get(CONF_TOKEN) is None
    assert redacted[CONF_DEVICES][2][CONF_NAME] == "Name"
    assert redacted[CONF_DEVICES][3][CONF_PASSWORD] == "ABC"
    assert redacted[CONF_DEVICES][3].get(CONF_TOKEN) is None
    assert redacted[CONF_DEVICES][3].get(CONF_TOKEN_KEY) is None
    assert redacted[CONF_DEVICES][4][CONF_TOKEN_KEY] == "****"
    assert redacted[CONF_DEVICES][7][CONF_TOKEN] == "*****"
