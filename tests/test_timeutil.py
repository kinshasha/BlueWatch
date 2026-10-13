import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from bluewatch.db import Device
from bluewatch.timeutil import serialize_timestamp, serialize_utc_timestamp
from bluewatch.webapp.server import _device_to_json


def test_legacy_server_local_timestamp_is_emitted_as_utc(monkeypatch):
    # 12:00 at UTC+10 is 02:00 UTC, not 12:00 UTC.
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Etc/GMT-10")
    value = datetime(2026, 10, 13, 12, 0, 0)
    assert serialize_timestamp(value) == "2026-10-13T02:00:00.000000Z"


def test_explicit_timestamp_keeps_the_same_instant():
    value = datetime(2026, 10, 13, 13, 0, tzinfo=ZoneInfo("Etc/GMT-11"))
    assert serialize_timestamp(value) == "2026-10-13T02:00:00.000000Z"


def test_utc_timestamp_is_unchanged():
    value = datetime(2026, 10, 13, 2, 0, tzinfo=timezone.utc)
    assert serialize_timestamp(value) == "2026-10-13T02:00:00.000000Z"


def test_daylight_saving_timestamp_is_emitted_as_utc(monkeypatch):
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Europe/Berlin")
    value = datetime(2026, 7, 13, 13, 0)
    assert serialize_timestamp(value) == "2026-07-13T11:00:00.000000Z"


def test_legacy_timestamp_string_is_emitted_as_utc(monkeypatch):
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Etc/GMT-10")
    assert serialize_timestamp("2026-10-13T12:00:00") == "2026-10-13T02:00:00.000000Z"


def test_none_remains_none():
    assert serialize_timestamp(None) is None


def test_invalid_legacy_timezone_falls_back_to_utc(monkeypatch, caplog):
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Invalid/Timezone")
    with caplog.at_level(logging.WARNING):
        result = serialize_timestamp(datetime(2026, 10, 13, 2, 0))
    assert result == "2026-10-13T02:00:00.000000Z"
    assert "falling back to UTC" in caplog.text


def test_naive_sqlite_utc_timestamp_is_not_treated_as_legacy_local(monkeypatch):
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Etc/GMT-10")
    assert serialize_utc_timestamp("2026-10-13 02:00:00") == "2026-10-13T02:00:00.000000Z"


def test_device_api_json_uses_qualified_timestamps(monkeypatch):
    monkeypatch.setenv("BLUEWATCH_LEGACY_TIMEZONE", "Etc/GMT-10")
    device = Device(
        mac="00:11:22:33:44:55",
        first_seen=datetime(2026, 10, 13, 12, 0),
        last_seen=datetime(2026, 10, 13, 12, 1),
    )
    payload = json.loads(json.dumps(_device_to_json(device)))
    assert payload["first_seen"] == "2026-10-13T02:00:00.000000Z"
    assert payload["last_seen"] == "2026-10-13T02:01:00.000000Z"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_browser_parses_qualified_timestamp_as_the_correct_instant():
    script = """
const expected = Date.parse('2026-10-13T02:00:00.000000Z');
const now = Date.parse('2026-10-13T02:00:05.000000Z');
const qualified = Date.parse('2026-10-13T02:00:00.000000Z');
const naive = Date.parse('2026-10-13T02:00:00.000000');
console.log(JSON.stringify({ qualified, naive, age: (now - qualified) / 1000 }));
"""
    env = {**os.environ, "TZ": "Etc/GMT-11"}
    parsed = json.loads(subprocess.check_output(["node", "-e", script], text=True, env=env))
    assert parsed["qualified"] == 1791856800000
    assert parsed["naive"] != parsed["qualified"]
    assert parsed["age"] == 5
