"""Tests for health check logic."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import health as health_module


class TestCheckDataStaleness:
    def test_missing_file(self):
        health_module.HEALTH_JSON = "/nonexistent/health.json"
        result = health_module.check_data_staleness()
        assert result["status"] == "missing"

    def test_fresh_data(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"timestamp": datetime.now(timezone.utc).isoformat()}, f)
            f.flush()
            health_module.HEALTH_JSON = f.name

        try:
            result = health_module.check_data_staleness()
            assert result["status"] == "fresh"
            assert result["age_days"] < 1
        finally:
            os.unlink(f.name)

    def test_stale_data(self):
        old_time = datetime.now(timezone.utc) - timedelta(days=15)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"timestamp": old_time.isoformat()}, f)
            f.flush()
            health_module.HEALTH_JSON = f.name

        try:
            result = health_module.check_data_staleness()
            assert result["status"] == "stale"
            assert result["age_days"] > 10
        finally:
            os.unlink(f.name)

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            f.flush()
            health_module.HEALTH_JSON = f.name

        try:
            result = health_module.check_data_staleness()
            assert result["status"] == "error"
        finally:
            os.unlink(f.name)

    def test_missing_timestamp(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"total_segments": 240000}, f)
            f.flush()
            health_module.HEALTH_JSON = f.name

        try:
            result = health_module.check_data_staleness()
            assert result["status"] == "error"
        finally:
            os.unlink(f.name)
