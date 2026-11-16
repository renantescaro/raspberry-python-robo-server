import itertools

import pytest

from robot_server import protocol
from robot_server.motors import Drive, DriveState, resolve_drive_state

RF, RB, LF, LB = 27, 17, 4, 3


@pytest.fixture
def drive(backend):
    return Drive(backend, right_forward=RF, right_backward=RB, left_forward=LF, left_backward=LB)


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (0, DriveState.STOP),
        (protocol.FORWARD, DriveState.FORWARD),
        (protocol.BACKWARD, DriveState.BACKWARD),
        (protocol.LEFT, DriveState.LEFT),
        (protocol.RIGHT, DriveState.RIGHT),
        # curvas têm prioridade sobre frente/ré
        (protocol.FORWARD | protocol.LEFT, DriveState.LEFT),
        (protocol.BACKWARD | protocol.RIGHT, DriveState.RIGHT),
        # esquerda vence direita; frente vence ré
        (protocol.LEFT | protocol.RIGHT, DriveState.LEFT),
        (protocol.FORWARD | protocol.BACKWARD, DriveState.FORWARD),
    ],
)
def test_resolve_drive_state(flags, expected):
    assert resolve_drive_state(flags) is expected


def test_pins_start_low(drive, backend):
    assert backend.pins == {RF: False, RB: False, LF: False, LB: False}
    assert drive.state is DriveState.STOP


@pytest.mark.parametrize(
    ("flags", "high_pins"),
    [
        (protocol.FORWARD, {RF, LF}),
        (protocol.BACKWARD, {RB, LB}),
        (protocol.LEFT, {RB, LF}),
        (protocol.RIGHT, {RF, LB}),
    ],
)
def test_apply_sets_expected_pins(drive, backend, flags, high_pins):
    drive.apply(flags)
    assert {pin for pin, value in backend.pins.items() if value} == high_pins


def test_same_state_does_not_write_again(drive, backend):
    drive.apply(protocol.FORWARD)
    writes = len(backend.writes)
    drive.apply(protocol.FORWARD)
    drive.apply(protocol.FORWARD | protocol.BACKWARD)  # também resolve para FORWARD
    assert len(backend.writes) == writes


def test_stop_turns_everything_off(drive, backend):
    drive.apply(protocol.LEFT)
    drive.stop()
    assert not any(backend.pins.values())
    assert drive.state is DriveState.STOP


@pytest.mark.parametrize(("start", "end"), list(itertools.permutations(DriveState, 2)))
def test_transition_never_drives_both_directions_of_a_side(backend, start, end):
    drive = Drive(backend, right_forward=RF, right_backward=RB, left_forward=LF, left_backward=LB)
    drive.set_state(start)
    first_write = len(backend.writes)
    drive.set_state(end)

    pins = dict(zip((RF, RB, LF, LB), start.value))
    for pin, value in backend.writes[first_write:]:
        pins[pin] = value
        assert not (pins[RF] and pins[RB]), f"{start.name}->{end.name}: lado direito em curto"
        assert not (pins[LF] and pins[LB]), f"{start.name}->{end.name}: lado esquerdo em curto"
    assert tuple(pins[pin] for pin in (RF, RB, LF, LB)) == end.value


def test_transition_turns_off_before_turning_on(drive, backend):
    drive.set_state(DriveState.FORWARD)
    first_write = len(backend.writes)
    drive.set_state(DriveState.BACKWARD)
    values = [value for _, value in backend.writes[first_write:]]
    assert values == sorted(values)  # todos os False antes dos True
