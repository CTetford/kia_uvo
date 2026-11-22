"""kiaconnect.ca (Canada) account entities and services."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api import Vehicle
import pytest

from custom_components.kia_uvo.coordinator import HyundaiKiaConnectDataUpdateCoordinator


def _vehicle() -> Vehicle:
    vehicle = Vehicle(id="v1", name="EV9", model="EV9")
    vehicle.next_service_date = dt.date(2027, 3, 27)
    vehicle.last_service_date = dt.date(2026, 3, 27)
    vehicle.connect_subscription_end_date = dt.date(2029, 3, 21)
    vehicle.connect_plan_type = "Trial"
    vehicle.connect_plan_status = "Active"
    vehicle.preferred_dealer_name = "Dealer"
    vehicle.unread_message_count = 0
    vehicle.monthly_report_day = 27
    vehicle.digital_key_activated = False
    vehicle.data = {
        "preferred_dealer": {"dealerCode": "53069", "tel": "555", "lat": 1.0},
        "notifications": [{"n": i} for i in range(12)],
    }
    return vehicle


async def test_account_sensors_created(setup_sensors) -> None:
    sensors = await setup_sensors(_vehicle())
    assert sensors["next_service_date"].native_value == dt.date(2027, 3, 27)
    assert sensors["connect_subscription_end_date"].native_value == dt.date(2029, 3, 21)
    assert sensors["connect_plan_type"].native_value == "Trial"
    assert sensors["connect_plan_type"].extra_state_attributes == {"status": "Active"}
    assert sensors["monthly_report_day"].native_value == 27
    # Dealer attributes exclude coordinates
    assert sensors["preferred_dealer_name"].extra_state_attributes == {
        "dealerCode": "53069",
        "tel": "555",
    }
    assert (
        len(sensors["unread_message_count"].extra_state_attributes["notifications"])
        == 10
    )


async def test_account_sensors_absent_without_data(setup_sensors) -> None:
    sensors = await setup_sensors(Vehicle(id="v1", name="x", model="x"))
    for key in (
        "next_service_date",
        "connect_subscription_end_date",
        "preferred_dealer_name",
        "unread_message_count",
    ):
        assert key not in sensors


async def test_digital_key_binary_sensor(setup_binary_sensors) -> None:
    entities = await setup_binary_sensors(_vehicle())
    assert entities["digital_key_activated"].is_on is False


async def test_ca_account_call_runs_api_method() -> None:
    vehicle = _vehicle()
    api = MagicMock()
    coordinator = MagicMock()
    coordinator.vehicle_manager.api = api
    coordinator.vehicle_manager.token = "tok"
    coordinator.vehicle_manager.get_vehicle.return_value = vehicle
    coordinator.async_check_and_refresh_token = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    async def run(fn):
        return fn()

    coordinator.hass.async_add_executor_job = AsyncMock(side_effect=run)
    vehicle.data["_ca_extras_at"] = 1.0

    await HyundaiKiaConnectDataUpdateCoordinator.async_ca_account_call(
        coordinator, "v1", "set_monthly_report_day", 15
    )
    api.set_monthly_report_day.assert_called_once_with("tok", vehicle, 15)
    assert "_ca_extras_at" not in vehicle.data  # account data re-read next update
    coordinator.async_request_refresh.assert_awaited_once()


async def test_ca_account_call_other_regions() -> None:
    coordinator = MagicMock()
    coordinator.vehicle_manager.api = object()  # no CA methods
    with pytest.raises(HomeAssistantError):
        await HyundaiKiaConnectDataUpdateCoordinator.async_ca_account_call(
            coordinator, "v1", "set_monthly_report_day", 15
        )
