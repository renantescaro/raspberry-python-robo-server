import struct

import pytest

from robot_server import protocol


def test_packet_has_fixed_size():
    assert len(protocol.encode(protocol.ControlState(protocol.FORWARD, 1, -1))) == protocol.PACKET_SIZE


def test_default_state_is_stopped():
    assert protocol.ControlState() == (0, 0, 0)


@pytest.mark.parametrize(
    "state",
    [
        protocol.ControlState(),
        protocol.ControlState(protocol.FORWARD | protocol.LEFT, 1, 0),
        protocol.ControlState(protocol.BACKWARD | protocol.RIGHT, -1, 1),
    ],
)
def test_roundtrip(state):
    assert protocol.decode(protocol.encode(state)) == state


def test_decode_accepts_bytearray_and_memoryview():
    data = protocol.encode(protocol.ControlState(protocol.RIGHT, 0, 1))
    assert protocol.decode(bytearray(data)) == protocol.decode(memoryview(data))


def test_decode_short_buffer_raises():
    with pytest.raises(struct.error):
        protocol.decode(b"\xa5\x01")


def test_protocol_error_is_value_error():
    assert issubclass(protocol.ProtocolError, ValueError)
