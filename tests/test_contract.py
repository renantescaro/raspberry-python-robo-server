"""Testes de contrato do protocolo cliente <-> servidor.

Este arquivo e `tests/contract/protocol_vectors.json` são IDÊNTICOS nos dois
repositórios (raspberry-python-robo-server e raspberry-python-robo-client).

- Sempre valida o protocol.py local contra os vetores do contrato.
- Se o repositório par estiver disponível (variável PEER_REPO_DIR ou pasta
  irmã com o nome do outro repositório), também valida o protocol.py dele,
  testa a compatibilidade cruzada (um codifica, o outro decodifica) e confere
  que os arquivos do contrato não divergiram.
- Com REQUIRE_PEER=1 (usado no CI) a ausência do par é falha, não skip.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
VECTORS_FILE = TESTS_DIR / "contract" / "protocol_vectors.json"
VECTORS = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))

# pacote local -> nome do repositório par
PEER_REPO_NAMES = {
    "robot_server": "raspberry-python-robo-client",
    "robot_client": "raspberry-python-robo-server",
}
REQUIRE_PEER = os.getenv("REQUIRE_PEER") == "1"


def _package_dir(repo_root: Path) -> Path | None:
    for name in PEER_REPO_NAMES:
        if (repo_root / name / "protocol.py").is_file():
            return repo_root / name
    return None


def _load_protocol(repo_root: Path, alias: str) -> ModuleType | None:
    package = _package_dir(repo_root)
    if package is None:
        return None
    spec = importlib.util.spec_from_file_location(alias, package / "protocol.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_peer_root() -> Path | None:
    env = os.getenv("PEER_REPO_DIR")
    if env:
        return Path(env).resolve()
    sibling = ROOT.parent / PEER_REPO_NAMES[_package_dir(ROOT).name]
    return sibling if sibling.is_dir() else None


LOCAL = _load_protocol(ROOT, "contract_local_protocol")
PEER_ROOT = _find_peer_root()
PEER = _load_protocol(PEER_ROOT, "contract_peer_protocol") if PEER_ROOT else None


def _require_peer() -> ModuleType:
    if PEER is None:
        message = f"protocol.py do repositório par não encontrado (PEER_REPO_DIR={PEER_ROOT})"
        if REQUIRE_PEER:
            pytest.fail(message)
        pytest.skip(message)
    return PEER


@pytest.fixture(params=["local", "peer"])
def protocol(request) -> ModuleType:
    return LOCAL if request.param == "local" else _require_peer()


def _ids(cases: list[dict]) -> list[str]:
    return [case["name"] for case in cases]


# ---------------------------------------------------------------- implementação


def test_constants(protocol):
    assert protocol.PACKET_SIZE == VECTORS["packet_size"]
    assert protocol.MAGIC == VECTORS["magic"]
    for name, value in VECTORS["flags"].items():
        assert getattr(protocol, name) == value, name


@pytest.mark.parametrize("case", VECTORS["roundtrip"], ids=_ids(VECTORS["roundtrip"]))
def test_encode(protocol, case):
    state = protocol.ControlState(*case["state"])
    assert protocol.encode(state).hex() == case["hex"]


@pytest.mark.parametrize("case", VECTORS["roundtrip"], ids=_ids(VECTORS["roundtrip"]))
def test_decode(protocol, case):
    assert tuple(protocol.decode(bytes.fromhex(case["hex"]))) == tuple(case["state"])


@pytest.mark.parametrize("case", VECTORS["decode"], ids=_ids(VECTORS["decode"]))
def test_decode_normalization(protocol, case):
    assert tuple(protocol.decode(bytes.fromhex(case["hex"]))) == tuple(case["state"])


@pytest.mark.parametrize("case", VECTORS["invalid"], ids=_ids(VECTORS["invalid"]))
def test_decode_rejects_invalid_packet(protocol, case):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode(bytes.fromhex(case["hex"]))


def test_decode_with_offset_in_stream(protocol):
    first, second = VECTORS["roundtrip"][1], VECTORS["roundtrip"][5]
    stream = bytes.fromhex(first["hex"] + second["hex"])
    assert tuple(protocol.decode(stream, VECTORS["packet_size"])) == tuple(second["state"])


# ---------------------------------------------------------------------- comandos


def test_command_constants(protocol):
    assert protocol.COMMAND_MAGIC == VECTORS["command_magic"]
    for name, value in VECTORS["commands"].items():
        assert getattr(protocol, name) == value, name


@pytest.mark.parametrize("case", VECTORS["command_packets"], ids=_ids(VECTORS["command_packets"]))
def test_encode_command(protocol, case):
    assert protocol.encode_command(case["code"]).hex() == case["hex"]


@pytest.mark.parametrize("case", VECTORS["command_packets"], ids=_ids(VECTORS["command_packets"]))
def test_decode_command(protocol, case):
    packet = protocol.decode_packet(bytes.fromhex(case["hex"]))
    assert type(packet).__name__ == "Command"
    assert tuple(packet) == (case["code"],)


@pytest.mark.parametrize("case", VECTORS["roundtrip"], ids=_ids(VECTORS["roundtrip"]))
def test_decode_packet_accepts_state(protocol, case):
    packet = protocol.decode_packet(bytes.fromhex(case["hex"]))
    assert type(packet).__name__ == "ControlState"
    assert tuple(packet) == tuple(case["state"])


def test_command_is_not_accepted_as_state(protocol):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode(bytes.fromhex(VECTORS["command_packets"][0]["hex"]))


def test_unknown_command_cannot_be_encoded(protocol):
    with pytest.raises(ValueError):
        protocol.encode_command(0xFF)


# -------------------------------------------------------------------- telemetria


def _telemetry(values: list) -> tuple:
    return tuple(values)  # null do JSON vira None


def test_telemetry_constants(protocol):
    assert protocol.TELEMETRY_MAGIC == VECTORS["telemetry_magic"]


@pytest.mark.parametrize("case", VECTORS["telemetry_packets"], ids=_ids(VECTORS["telemetry_packets"]))
def test_encode_telemetry(protocol, case):
    packet = protocol.encode_telemetry(protocol.Telemetry(*case["telemetry"]))
    assert packet.hex() == case["hex"]


@pytest.mark.parametrize("case", VECTORS["telemetry_encode"], ids=_ids(VECTORS["telemetry_encode"]))
def test_encode_telemetry_clamps(protocol, case):
    packet = protocol.encode_telemetry(protocol.Telemetry(*case["telemetry"]))
    assert packet.hex() == case["hex"]


@pytest.mark.parametrize(
    "case",
    VECTORS["telemetry_packets"] + VECTORS["telemetry_decode"],
    ids=_ids(VECTORS["telemetry_packets"] + VECTORS["telemetry_decode"]),
)
def test_decode_telemetry(protocol, case):
    packet = protocol.decode_packet(bytes.fromhex(case["hex"]))
    assert type(packet).__name__ == "Telemetry"
    assert tuple(packet) == _telemetry(case["telemetry"])


def test_telemetry_is_not_accepted_as_state(protocol):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode(bytes.fromhex(VECTORS["telemetry_packets"][0]["hex"]))


# --------------------------------------------------------- compatibilidade cruzada


@pytest.mark.parametrize("case", VECTORS["command_packets"], ids=_ids(VECTORS["command_packets"]))
def test_peer_and_local_agree_on_commands(case):
    peer = _require_peer()
    assert tuple(peer.decode_packet(LOCAL.encode_command(case["code"]))) == (case["code"],)
    assert tuple(LOCAL.decode_packet(peer.encode_command(case["code"]))) == (case["code"],)


@pytest.mark.parametrize("case", VECTORS["telemetry_packets"], ids=_ids(VECTORS["telemetry_packets"]))
def test_peer_and_local_agree_on_telemetry(case):
    peer = _require_peer()
    expected = _telemetry(case["telemetry"])
    assert tuple(peer.decode_packet(LOCAL.encode_telemetry(LOCAL.Telemetry(*expected)))) == expected
    assert tuple(LOCAL.decode_packet(peer.encode_telemetry(peer.Telemetry(*expected)))) == expected


@pytest.mark.parametrize("case", VECTORS["roundtrip"], ids=_ids(VECTORS["roundtrip"]))
def test_peer_decodes_what_local_encodes(case):
    peer = _require_peer()
    data = LOCAL.encode(LOCAL.ControlState(*case["state"]))
    assert tuple(peer.decode(data)) == tuple(case["state"])


@pytest.mark.parametrize("case", VECTORS["roundtrip"], ids=_ids(VECTORS["roundtrip"]))
def test_local_decodes_what_peer_encodes(case):
    peer = _require_peer()
    data = peer.encode(peer.ControlState(*case["state"]))
    assert tuple(LOCAL.decode(data)) == tuple(case["state"])


def test_contract_vectors_match_peer():
    _require_peer()
    peer_vectors = PEER_ROOT / "tests" / "contract" / "protocol_vectors.json"
    assert peer_vectors.is_file(), "vetores do contrato ausentes no repositório par"
    assert json.loads(peer_vectors.read_text(encoding="utf-8")) == VECTORS


def test_contract_test_file_matches_peer():
    _require_peer()
    peer_test = PEER_ROOT / "tests" / Path(__file__).name
    assert peer_test.is_file(), "test_contract.py ausente no repositório par"
    assert peer_test.read_text(encoding="utf-8") == Path(__file__).read_text(encoding="utf-8")
