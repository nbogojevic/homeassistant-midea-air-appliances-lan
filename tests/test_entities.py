"""Entity API compatibility and in-place rename regression tests."""

from datetime import UTC, datetime
import inspect
import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant import const as ha_const
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
import pytest

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
)
from custom_components.midea_dehumidifier_lan.climate import AirConditionerEntity
from custom_components.midea_dehumidifier_lan.const import ATTR_FAN_SPEED
from custom_components.midea_dehumidifier_lan.fan import MODE_HIGH, DehumidiferFan
from custom_components.midea_dehumidifier_lan.humidifier import DehumidifierEntity
from custom_components.midea_dehumidifier_lan.sensor import (
    CurrentHumiditySensor,
    TankLevelSensor,
)


@pytest.fixture
def coordinator():
    """An appliance/coordinator with no network or timers."""
    state = SimpleNamespace(
        indoor_temperature=22.5,
        target_temperature=24.0,
        current_humidity=50,
        target_humidity=55,
        tank_level=20,
        fan_speed=102,
        running=True,
        mode=2,
        turbo=False,
        eco_mode=False,
        comfort_sleep=False,
        frost_protect=False,
        comfort_mode=False,
        vertical_swing=False,
        horizontal_swing=False,
        error_code=0,
        capabilities={},
        capabilities_data=b"",
        latest_data=b"",
        online=True,
    )
    appliance = SimpleNamespace(
        name="Midea test appliance",
        serial_number="SERIAL123",
        model="Test model",
        firmware_version="1.0",
        online=True,
        state=state,
    )
    return Mock(
        appliance=appliance,
        available=True,
        last_update_success=True,
        async_add_listener=Mock(return_value=Mock()),
    )


def test_climate_temperature_attributes(coordinator):
    """Use only the native temperature API introduced in HA 2026.11."""
    entity = AirConditionerEntity(coordinator)
    entity.on_update()
    assert entity.native_temperature_unit == ha_const.UnitOfTemperature.CELSIUS
    assert entity.native_current_temperature == 22.5
    assert entity.native_target_temperature == 24.0
    assert entity.min_temp == 16
    assert entity.max_temp == 32
    assert "_attr_temperature_unit" not in AirConditionerEntity.__dict__
    assert "_attr_current_temperature" not in entity.__dict__
    assert "_attr_target_temperature" not in entity.__dict__


@pytest.mark.parametrize(
    ("unit_system", "current", "target"),
    [(METRIC_SYSTEM, 22.5, 25.0), (US_CUSTOMARY_SYSTEM, 72.5, 77.0)],
)
async def test_climate_state_temperature_conversion(
    hass, coordinator, unit_system, current, target
):
    """HA converts device-native Celsius values exactly once for the user's units."""
    hass.config.units = unit_system
    coordinator.appliance.state.target_temperature = 25.0
    component = EntityComponent(logging.getLogger(__name__), "climate", hass)
    entity = AirConditionerEntity(coordinator)
    with patch.object(AirConditionerEntity, "device_info", None):
        await component.async_add_entities([entity])

    state = hass.states.get(entity.entity_id)
    assert state.attributes["current_temperature"] == current
    assert state.attributes["temperature"] == target
    await entity.async_remove()


@pytest.mark.parametrize("sensor_class", [CurrentHumiditySensor, TankLevelSensor])
def test_percentage_units(coordinator, sensor_class):
    """Percentage sensors must use the ratio enum."""
    entity = sensor_class(coordinator)
    assert entity.native_unit_of_measurement is ha_const.UnitOfRatio.PERCENTAGE


def test_entity_id_changed_calls_parent(coordinator):
    """Forward rename notifications so HA's base classes can update bookkeeping."""
    entity = ApplianceEntity(coordinator)
    with patch.object(CoordinatorEntity, "async_entity_id_changed") as parent:
        entity.async_entity_id_changed("sensor.previous_name")
    parent.assert_called_once_with("sensor.previous_name")


async def test_in_place_entity_rename_preserves_subscription(hass, coordinator):
    """A registry rename keeps the same entity and its coordinator subscription."""
    component = EntityComponent(logging.getLogger(__name__), "sensor", hass)
    entity = CurrentHumiditySensor(coordinator)
    # This standalone platform has no config entry; device registration is unrelated.
    with patch.object(CurrentHumiditySensor, "device_info", None):
        await component.async_add_entities([entity])
    old_id = entity.entity_id
    new_id = "sensor.renamed_midea_humidity"
    registry = er.async_get(hass)
    assert registry.async_get(old_id) is not None
    assert hass.states.get(old_id).state == "50"
    coordinator.async_add_listener.assert_called_once()
    unsubscribe = coordinator.async_add_listener.return_value
    listener = coordinator.async_add_listener.call_args.args[0]

    registry.async_update_entity(old_id, new_entity_id=new_id)
    await hass.async_block_till_done()

    assert entity.entity_id == new_id
    assert component.get_entity(new_id) is entity
    assert hass.states.get(old_id) is None
    assert hass.states.get(new_id).state == "50"
    coordinator.async_add_listener.assert_called_once()
    unsubscribe.assert_not_called()

    coordinator.appliance.state.current_humidity = 55
    listener()
    assert hass.states.get(new_id).state == "55"

    await entity.async_remove()
    unsubscribe.assert_called_once_with()


@pytest.mark.parametrize(
    ("kwargs", "speed"),
    [({}, 60), ({"percentage": 70}, 70), ({"preset_mode": MODE_HIGH}, 80)],
)
def test_fan_turn_on(coordinator, kwargs, speed):
    """The modern percentage/preset signature never calls removed speed methods."""
    entity = DehumidiferFan(coordinator)
    assert "speed" not in inspect.signature(entity.turn_on).parameters
    with patch.object(entity, "apply") as apply:
        entity.turn_on(**kwargs)
    apply.assert_called_once_with(ATTR_FAN_SPEED, speed)


@pytest.mark.parametrize("entity_class", [AirConditionerEntity, DehumidifierEntity])
def test_raw_protocol_data_is_not_state(coordinator, entity_class):
    """Raw frames change every poll and belong in diagnostics, not attributes."""
    entity = entity_class(coordinator)
    coordinator.appliance.state.latest_data = bytes.fromhex("a001")
    coordinator.appliance.state.capabilities_data = bytes.fromhex("b001")
    entity.on_update()
    attributes = dict(entity.extra_state_attributes)

    coordinator.appliance.state.latest_data = bytes.fromhex("c801")
    coordinator.appliance.state.capabilities_data = bytes.fromhex("b002")
    entity.on_update()

    assert entity.extra_state_attributes == attributes
    assert "last_data" not in attributes
    assert "capabilities_data" not in attributes
    assert attributes["last_error_time"] is None


def test_error_time_changes_only_for_new_errors(coordinator):
    """A persistent error keeps its timestamp; a new error gets a new one."""
    entity = DehumidifierEntity(coordinator)
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = datetime(2026, 1, 2, tzinfo=UTC)
    third = datetime(2026, 1, 3, tzinfo=UTC)
    state = coordinator.appliance.state
    with patch(
        "custom_components.midea_dehumidifier_lan.appliance_coordinator.dt_util.utcnow",
        side_effect=[first, second, third],
    ):
        state.error_code = 1
        entity.on_update()
        entity.on_update()
        assert entity.extra_state_attributes["last_error_code"] == 1
        assert entity.extra_state_attributes["last_error_time"] == first

        state.error_code = 2
        entity.on_update()
        assert entity.extra_state_attributes["last_error_code"] == 2
        assert entity.extra_state_attributes["last_error_time"] == second

        state.error_code = 0
        entity.on_update()
        state.error_code = 2
        entity.on_update()
        assert entity.extra_state_attributes["error_code"] == 2
        assert entity.extra_state_attributes["last_error_time"] == third


async def test_unchanged_poll_does_not_change_state(hass, coordinator):
    """Only last_reported advances when a poll changes raw protocol data only."""
    component = EntityComponent(logging.getLogger(__name__), "humidifier", hass)
    entity = DehumidifierEntity(coordinator)
    with patch.object(DehumidifierEntity, "device_info", None):
        await component.async_add_entities([entity])
    listener = coordinator.async_add_listener.call_args.args[0]
    before = hass.states.get(entity.entity_id)

    coordinator.appliance.state.latest_data = bytes.fromhex("d00102")
    listener()
    after = hass.states.get(entity.entity_id)

    assert after.last_updated == before.last_updated
    assert after.attributes == before.attributes
    await entity.async_remove()
