"""Tests for Navirec data types and helper functions."""

from __future__ import annotations

from typing import Any

from custom_components.navirec.data import (
    extract_uuid_from_url,
    get_activity_from_state,
    get_coordinates_from_state,
    get_interpretation_choice_options,
    get_sensor_value_from_state,
    get_vehicle_id_from_action,
    get_vehicle_id_from_sensor,
    get_vehicle_id_from_state,
)
from custom_components.navirec.models import (
    Action,
    Interpretation,
    Sensor,
    Vehicle,
    VehicleState,
)


class TestExtractUuidFromUrl:
    """Test UUID extraction from URLs."""

    def test_extract_uuid_from_vehicle_url(self) -> None:
        """Test extracting UUID from a vehicle URL."""
        url = "https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/"
        assert extract_uuid_from_url(url) == "924da156-1a68-4fce-8da1-a196c9bf22be"

    def test_extract_uuid_from_account_url(self) -> None:
        """Test extracting UUID from an account URL."""
        url = "https://api.navirec.com/accounts/89ea89c8-bffb-444a-9876-c54a865e4d67/"
        assert extract_uuid_from_url(url) == "89ea89c8-bffb-444a-9876-c54a865e4d67"

    def test_extract_uuid_invalid_url(self) -> None:
        """Test extracting UUID from invalid URL returns None."""
        assert extract_uuid_from_url("https://api.navirec.com/invalid/") is None


class TestVehicleModel:
    """Test Vehicle Pydantic model."""

    def test_vehicle_from_api_response(
        self, vehicles_fixture: list[dict[str, Any]]
    ) -> None:
        """Test creating Vehicle from API response."""
        vehicle_dict = vehicles_fixture[0]
        vehicle = Vehicle.model_validate(vehicle_dict)

        assert str(vehicle.id) == vehicle_dict["id"]
        assert vehicle.name == vehicle_dict.get("name", "")
        assert vehicle.name_display == vehicle_dict.get("name_display", "")
        assert vehicle.registration == vehicle_dict.get("registration", "")


class TestSensorModel:
    """Test Sensor Pydantic model."""

    def test_sensor_from_api_response(
        self, sensors_fixture: list[dict[str, Any]]
    ) -> None:
        """Test creating Sensor from API response."""
        sensor_dict = sensors_fixture[0]
        sensor = Sensor.model_validate(sensor_dict)

        assert str(sensor.id) == sensor_dict["id"]
        assert sensor.name_display == sensor_dict.get("name_display", "")

    def test_get_vehicle_id_from_sensor(
        self, sensors_fixture: list[dict[str, Any]]
    ) -> None:
        """Test extracting vehicle ID from sensor."""
        sensor_dict = sensors_fixture[0]
        sensor = Sensor.model_validate(sensor_dict)
        vehicle_id = get_vehicle_id_from_sensor(sensor)

        # Vehicle URL should be in format: https://api.../vehicles/{uuid}/
        assert vehicle_id is not None
        assert len(vehicle_id) == 36  # UUID length


class TestVehicleStateModel:
    """Test VehicleState Pydantic model."""

    def test_vehicle_state_from_api_response(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test creating VehicleState from API response."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)

        assert str(state.id) == state_dict["id"]
        assert state.time is not None

    def test_get_vehicle_id_from_state(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test extracting vehicle ID from state."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)
        vehicle_id = get_vehicle_id_from_state(state)

        # Vehicle URL should be in format: https://api.../vehicles/{uuid}/
        assert vehicle_id is not None
        assert len(vehicle_id) == 36  # UUID length

    def test_get_coordinates_from_state(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test extracting coordinates from VehicleState."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)
        lat, lon = get_coordinates_from_state(state)

        # Location is in GeoJSON format: [longitude, latitude]
        location = state_dict.get("location", {})
        coords = location.get("coordinates", [])

        if len(coords) >= 2:
            assert lat == coords[1]  # latitude
            assert lon == coords[0]  # longitude

    def test_get_sensor_value_from_state(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test getting sensor values from VehicleState."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)

        # Test getting various sensor values
        assert get_sensor_value_from_state(state, "speed") == state_dict.get("speed")
        assert get_sensor_value_from_state(state, "ignition") == state_dict.get(
            "ignition"
        )
        assert get_sensor_value_from_state(state, "fuel_level") == state_dict.get(
            "fuel_level"
        )

    def test_get_sensor_value_missing(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test getting missing sensor value returns None."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)

        assert get_sensor_value_from_state(state, "nonexistent_sensor") is None

    def test_get_activity_from_state(
        self, vehicle_states_fixture: list[dict[str, Any]]
    ) -> None:
        """Test getting activity string from VehicleState."""
        state_dict = vehicle_states_fixture[0]
        state = VehicleState.model_validate(state_dict)
        activity = get_activity_from_state(state)

        # Activity should match the fixture value
        expected_activity = state_dict.get("activity")
        assert activity == expected_activity


class TestEdgeCases:
    """Test edge cases for data helper functions."""

    def test_get_vehicle_id_from_sensor_no_vehicle(self) -> None:
        """Test get_vehicle_id_from_sensor returns None when no vehicle."""
        # Create a sensor without vehicle URL
        sensor = Sensor.model_validate(
            {
                "id": "924da156-1a68-4fce-8da1-a196c9bf22be",
                "url": "https://api.navirec.com/sensors/924da156-1a68-4fce-8da1-a196c9bf22be/",
                "vehicle": None,
                "name_display": "Test Sensor",
                "interpretation": "speed",
                "show_in_map": False,
                "show_in_list": False,
                "show_in_icon": False,
                "show_in_chart": False,
                "show_in_report": False,
            }
        )
        assert get_vehicle_id_from_sensor(sensor) is None

    def test_get_vehicle_id_from_state_no_vehicle(self) -> None:
        """Test get_vehicle_id_from_state returns None when no vehicle."""
        # Create a state without vehicle URL
        state = VehicleState.model_validate(
            {
                "id": "924da156-1a68-4fce-8da1-a196c9bf22be",
                "url": "https://api.navirec.com/vehicle-states/924da156-1a68-4fce-8da1-a196c9bf22be/",
                "vehicle": None,
                "time": "2025-01-01T00:00:00Z",
            }
        )
        assert get_vehicle_id_from_state(state) is None

    def test_get_vehicle_id_from_action_with_vehicle(
        self, actions_fixture: list[dict[str, Any]]
    ) -> None:
        """Test get_vehicle_id_from_action extracts vehicle ID."""
        action_dict = actions_fixture[0]
        action = Action.model_validate(action_dict)
        vehicle_id = get_vehicle_id_from_action(action)

        assert vehicle_id is not None
        assert len(vehicle_id) == 36  # UUID length

    def test_get_vehicle_id_from_action_no_vehicle(self) -> None:
        """Test get_vehicle_id_from_action returns None when no vehicle."""
        action = Action.model_validate(
            {
                "id": "924da156-1a68-4fce-8da1-a196c9bf22be",
                "url": "https://api.navirec.com/actions/924da156-1a68-4fce-8da1-a196c9bf22be/",
                "vehicle": None,
                "name_display": "Test Action",
            }
        )
        assert get_vehicle_id_from_action(action) is None

    def test_get_coordinates_from_state_no_location(self) -> None:
        """Test get_coordinates_from_state returns None when no location."""
        state = VehicleState.model_validate(
            {
                "id": "924da156-1a68-4fce-8da1-a196c9bf22be",
                "url": "https://api.navirec.com/vehicle-states/924da156-1a68-4fce-8da1-a196c9bf22be/",
                "vehicle": "https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/",
                "time": "2025-01-01T00:00:00Z",
                "location": None,
            }
        )
        lat, lon = get_coordinates_from_state(state)
        assert lat is None
        assert lon is None

    def test_get_interpretation_choice_options_with_choices(
        self, interpretations_fixture: list[dict[str, Any]]
    ) -> None:
        """Test get_interpretation_choice_options returns choice values."""
        # Find interpretation with choices (like activity)
        interp_dict = next(
            (i for i in interpretations_fixture if i.get("choices")), None
        )
        if interp_dict:
            interpretation = Interpretation.model_validate(interp_dict)
            options = get_interpretation_choice_options(interpretation)
            assert isinstance(options, list)
            assert len(options) > 0

    def test_get_interpretation_choice_options_no_choices(self) -> None:
        """Test get_interpretation_choice_options returns empty list when no choices."""
        interpretation = Interpretation.model_validate(
            {
                "key": "speed",
                "name": "Speed",
                "unit": "km/h",
                "choices": None,
            }
        )
        options = get_interpretation_choice_options(interpretation)
        assert options == []
