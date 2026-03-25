"""Tests for surface classification logic."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classify_surfaces import classify_surface, PAVED_VALUES, UNPAVED_VALUES


class TestClassifySurface:
    def test_tier1_asphalt(self):
        result = classify_surface({"surface": "asphalt", "highway": "residential"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "osm_tag"

    def test_tier1_concrete(self):
        result = classify_surface({"surface": "concrete", "highway": "tertiary"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "osm_tag"

    def test_tier1_gravel(self):
        result = classify_surface({"surface": "gravel", "highway": "unclassified"})
        assert result["surface_type"] == "unpaved"
        assert result["surface_source"] == "osm_tag"

    def test_tier1_dirt(self):
        result = classify_surface({"surface": "dirt", "highway": "service"})
        assert result["surface_type"] == "unpaved"
        assert result["surface_source"] == "osm_tag"

    def test_tier2_residential_default_paved(self):
        result = classify_surface({"surface": "", "highway": "residential"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "heuristic"

    def test_tier2_service_default_paved(self):
        result = classify_surface({"surface": "", "highway": "service"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "heuristic"

    def test_tier2_primary_default_paved(self):
        result = classify_surface({"surface": "", "highway": "primary"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "heuristic"

    def test_unknown_highway_no_surface(self):
        result = classify_surface({"surface": "", "highway": "unclassified"})
        assert result["surface_type"] == "unknown"

    def test_unknown_surface_value_known_road(self):
        """Unknown surface tag on a known road type should infer paved."""
        result = classify_surface({"surface": "some_weird_value", "highway": "residential"})
        assert result["surface_type"] == "paved"
        assert result["surface_source"] == "osm_tag_inferred"

    def test_paved_values_completeness(self):
        """Verify key paved values are in the set."""
        for val in ["asphalt", "concrete", "paving_stones", "brick", "sett"]:
            assert val in PAVED_VALUES

    def test_unpaved_values_completeness(self):
        """Verify key unpaved values are in the set."""
        for val in ["gravel", "dirt", "sand", "mud", "compacted"]:
            assert val in UNPAVED_VALUES

    def test_case_insensitive(self):
        result = classify_surface({"surface": "Asphalt", "highway": "residential"})
        assert result["surface_type"] == "paved"
