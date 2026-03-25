"""Tests for speed classification logic."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classify_speeds import classify_segment, parse_speed, MAX_SPEED_MPH, SERVICE_ROAD_SPEED_MPH


class TestParseSpeed:
    def test_mph_with_unit(self):
        assert parse_speed("35 mph") == 35.0

    def test_mph_no_unit(self):
        assert parse_speed("25") == 25.0

    def test_kmh(self):
        result = parse_speed("50 km/h")
        assert result is not None
        assert 30 < result < 32  # ~31.07 MPH

    def test_empty(self):
        assert parse_speed("") is None

    def test_none_value(self):
        assert parse_speed("none") is None

    def test_signals(self):
        assert parse_speed("signals") is None

    def test_invalid(self):
        assert parse_speed("fast") is None


class TestClassifySegment:
    def test_tier1_osm_tag_legal(self):
        props = {"osm_id": "1", "highway": "residential", "maxspeed": "25 mph", "service": ""}
        result = classify_segment(props, {})
        assert result["speed_limit"] == 25.0
        assert result["speed_source"] == "osm_tag"
        assert result["cart_legal"] is True

    def test_tier1_osm_tag_illegal(self):
        props = {"osm_id": "2", "highway": "primary", "maxspeed": "45 mph", "service": ""}
        result = classify_segment(props, {})
        assert result["speed_limit"] == 45.0
        assert result["speed_source"] == "osm_tag"
        assert result["cart_legal"] is False

    def test_tier2_fdot(self):
        props = {"osm_id": "3", "highway": "secondary", "maxspeed": "", "service": ""}
        fdot = {"3": {"speed_limit": 40, "source": "fdot"}}
        result = classify_segment(props, fdot)
        assert result["speed_limit"] == 40
        assert result["speed_source"] == "fdot"
        assert result["cart_legal"] is False

    def test_tier3_inference_residential(self):
        props = {"osm_id": "4", "highway": "residential", "maxspeed": "", "service": ""}
        result = classify_segment(props, {})
        assert result["speed_limit"] == 25
        assert result["speed_source"] == "inferred"
        assert result["cart_legal"] is True

    def test_tier3_inference_primary(self):
        props = {"osm_id": "5", "highway": "primary", "maxspeed": "", "service": ""}
        result = classify_segment(props, {})
        assert result["speed_limit"] == 45
        assert result["speed_source"] == "inferred"
        assert result["cart_legal"] is False

    def test_tier4_unknown(self):
        props = {"osm_id": "6", "highway": "unclassified", "maxspeed": "", "service": ""}
        result = classify_segment(props, {})
        assert result["speed_source"] == "unknown"
        assert result["cart_legal"] == "unknown"

    def test_service_road_included(self):
        props = {"osm_id": "7", "highway": "service", "maxspeed": "", "service": ""}
        result = classify_segment(props, {})
        assert result["cart_legal"] is True
        assert result["routing_speed"] == SERVICE_ROAD_SPEED_MPH
        assert result["excluded"] is False

    def test_service_road_alley(self):
        props = {"osm_id": "8", "highway": "service", "maxspeed": "", "service": "alley"}
        result = classify_segment(props, {})
        assert result["cart_legal"] is True
        assert result["routing_speed"] == SERVICE_ROAD_SPEED_MPH

    def test_service_driveway_excluded(self):
        props = {"osm_id": "9", "highway": "service", "maxspeed": "", "service": "driveway"}
        result = classify_segment(props, {})
        assert result["excluded"] is True
        assert result["cart_legal"] is False

    def test_service_parking_aisle_excluded(self):
        props = {"osm_id": "10", "highway": "service", "maxspeed": "", "service": "parking_aisle"}
        result = classify_segment(props, {})
        assert result["excluded"] is True

    def test_35mph_is_legal(self):
        """The 35 MPH threshold is the most important number — verify boundary."""
        props = {"osm_id": "11", "highway": "tertiary", "maxspeed": "35 mph", "service": ""}
        result = classify_segment(props, {})
        assert result["cart_legal"] is True

    def test_36mph_is_illegal(self):
        props = {"osm_id": "12", "highway": "tertiary", "maxspeed": "36 mph", "service": ""}
        result = classify_segment(props, {})
        assert result["cart_legal"] is False
