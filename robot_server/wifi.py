"""Qualidade do Wi-Fi do robô, lida de /proc/net/wireless (Linux).

Exemplo do arquivo (o Pi 3 B+ informa qualidade em /70 e sinal em dBm):

    Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
     face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
     wlan0: 0000   64.  -46.  -256        0      0      0   1630      0        0
"""

from __future__ import annotations

from pathlib import Path

from .protocol import Telemetry

WIRELESS_FILE = Path("/proc/net/wireless")
LINK_QUALITY_MAX = 70  # escala usada pelos drivers Wi-Fi do Linux (inclusive o brcmfmac do Pi)


def parse_wireless(text: str, interface: str) -> Telemetry:
    for line in text.splitlines():
        name, sep, rest = line.partition(":")
        if not sep or name.strip() != interface:
            continue
        fields = rest.split()
        try:
            link = float(fields[1].rstrip("."))
            level = float(fields[2].rstrip("."))
        except (IndexError, ValueError):
            return Telemetry()
        if level > 0:
            level -= 256  # alguns drivers informam o dBm como byte sem sinal
        quality = round(min(100.0, max(0.0, link * 100 / LINK_QUALITY_MAX)))
        return Telemetry(quality, round(level))
    return Telemetry()  # interface ausente ou desconectada


def read_wifi(interface: str, path: Path = WIRELESS_FILE) -> Telemetry:
    """Qualidade (%) e sinal (dBm) da interface; desconhecidos se não der para ler."""
    try:
        return parse_wireless(path.read_text(encoding="ascii", errors="replace"), interface)
    except OSError:
        return Telemetry()  # fora do Linux (ex.: --simulate no Windows)
