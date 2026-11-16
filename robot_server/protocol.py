"""Protocolo binário entre cliente e servidor.

IMPORTANTE: mantenha este arquivo em sincronia com
raspberry-python-robo-client/robot_client/protocol.py.

Todos os pacotes têm tamanho fixo de 4 bytes (sem necessidade de delimitador).
O primeiro byte identifica o tipo:

Estado (MAGIC 0xA5) - enviado sempre que muda + repetido como heartbeat:
    byte 1  flags     bits de movimento (FORWARD, BACKWARD, LEFT, RIGHT)
    byte 2  camera_v  direção do eixo vertical da câmera  (-1, 0, +1)
    byte 3  camera_h  direção do eixo horizontal da câmera (-1, 0, +1)

Comando (COMMAND_MAGIC 0xA6) - ação única, nunca repetida:
    byte 1  código    SHUTDOWN = desligar o Raspberry Pi
    byte 2  reservado (0)
    byte 3  reservado (0)

O servidor pode descartar estados antigos (só o mais recente importa), mas
precisa processar todo comando recebido.
"""

from __future__ import annotations

import struct
from typing import NamedTuple, Union

MAGIC = 0xA5
COMMAND_MAGIC = 0xA6
PACKET = struct.Struct("<BBbb")
PACKET_SIZE = PACKET.size

FORWARD = 0x01
BACKWARD = 0x02
LEFT = 0x04
RIGHT = 0x08

SHUTDOWN = 0x01
COMMAND_CODES = frozenset({SHUTDOWN})


class ProtocolError(ValueError):
    """Pacote inválido (fluxo corrompido ou cliente incompatível)."""


class ControlState(NamedTuple):
    flags: int = 0
    camera_v: int = 0
    camera_h: int = 0


class Command(NamedTuple):
    code: int


Packet = Union[ControlState, Command]


def encode(state: ControlState) -> bytes:
    return PACKET.pack(MAGIC, state.flags, state.camera_v, state.camera_h)


def encode_command(code: int) -> bytes:
    if code not in COMMAND_CODES:
        raise ValueError(f"comando desconhecido: {code}")
    return PACKET.pack(COMMAND_MAGIC, code, 0, 0)


def decode(buffer: bytes | bytearray | memoryview, offset: int = 0) -> ControlState:
    """Decodifica um pacote de estado (erro se for de outro tipo)."""
    packet = decode_packet(buffer, offset)
    if not isinstance(packet, ControlState):
        raise ProtocolError("esperado pacote de estado")
    return packet


def decode_packet(buffer: bytes | bytearray | memoryview, offset: int = 0) -> Packet:
    magic, first, second, third = PACKET.unpack_from(buffer, offset)
    if magic == MAGIC:
        # Normaliza para -1/0/+1 mesmo que o cliente envie outros valores
        return ControlState(first & 0x0F, _sign(second), _sign(third))
    if magic == COMMAND_MAGIC:
        if first not in COMMAND_CODES:
            raise ProtocolError(f"comando desconhecido: 0x{first:02X}")
        return Command(first)
    raise ProtocolError(f"magic inválido: 0x{magic:02X}")


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
