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


# --------------------------------------------------------- compatibilidade cruzada


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
