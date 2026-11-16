"""Leitura da qualidade do Wi-Fi (/proc/net/wireless)."""

from __future__ import annotations

from robot_server.protocol import Telemetry
from robot_server.wifi import parse_wireless, read_wifi

HEADER = (
    "Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
    " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
)
PI = HEADER + " wlan0: 0000   64.  -46.  -256        0      0      0   1630      0        0\n"


def test_parses_raspberry_pi_output():
    # 64/70 = 91%
    assert parse_wireless(PI, "wlan0") == Telemetry(91, -46)


def test_other_interface_is_unknown():
    assert parse_wireless(PI, "wlan1") == Telemetry()


def test_disconnected_wifi_is_unknown():
    assert parse_wireless(HEADER, "wlan0") == Telemetry()


def test_unsigned_dbm_is_converted():
    text = HEADER + " wlan0: 0000   35.  210.  0        0      0      0   0      0        0\n"
    assert parse_wireless(text, "wlan0") == Telemetry(50, -46)


def test_quality_is_clamped():
    text = HEADER + " wlan0: 0000   90.  -30.  -256        0      0      0   0      0        0\n"
    assert parse_wireless(text, "wlan0").wifi_quality == 100


def test_garbage_is_unknown():
    assert parse_wireless(HEADER + " wlan0: 0000 xx yy\n", "wlan0") == Telemetry()


def test_read_wifi_from_file(tmp_path):
    path = tmp_path / "wireless"
    path.write_text(PI, encoding="ascii")
    assert read_wifi("wlan0", path) == Telemetry(91, -46)


def test_read_wifi_without_file_is_unknown(tmp_path):
    assert read_wifi("wlan0", tmp_path / "nao-existe") == Telemetry()
