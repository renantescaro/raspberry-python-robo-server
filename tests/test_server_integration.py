"""Testes de integração: servidor real em TCP, com backend de GPIO em memória."""

from __future__ import annotations

import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from robot_server import protocol
from robot_server.motors import DriveState
from robot_server.server import RobotServer

RF, RB, LF, LB = 27, 17, 4, 3
ROOT = Path(__file__).resolve().parent.parent


class FakePower:
    def __init__(self) -> None:
        self.calls = 0
        self.result = True

    def shutdown(self) -> bool:
        self.calls += 1
        return self.result


@pytest.fixture
def power() -> FakePower:
    return FakePower()


@pytest.fixture
def server(backend, make_settings, power):
    robot = RobotServer(make_settings(), backend, power)
    host, port = robot.bind()
    thread = threading.Thread(target=robot.serve_forever, daemon=True)
    thread.start()
    robot.address = (host, port)
    yield robot
    robot.shutdown()
    thread.join(timeout=3)
    robot.close()


def connect(server) -> socket.socket:
    sock = socket.create_connection(server.address, timeout=2)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def send(sock, flags=0, camera_v=0, camera_h=0):
    sock.sendall(protocol.encode(protocol.ControlState(flags, camera_v, camera_h)))


def test_releases_servos_without_any_client(backend, make_settings, wait):
    robot = RobotServer(make_settings(servo_release_after_s=0.1), backend)
    robot.bind()
    # Posição inicial é escrita ao criar o servidor
    assert backend.servos[18] > 0 and backend.servos[23] > 0
    thread = threading.Thread(target=robot.serve_forever, daemon=True)
    thread.start()
    try:
        # Nenhum cliente conecta: o pulso precisa ser cortado mesmo assim
        assert wait(lambda: backend.servos == {18: 0, 23: 0}, timeout=2)
    finally:
        robot.shutdown()
        thread.join(timeout=3)
        robot.close()


def test_applies_received_state(server, wait):
    with connect(server) as sock:
        send(sock, protocol.FORWARD)
        assert wait(lambda: server.drive.state is DriveState.FORWARD)
        send(sock, protocol.FORWARD | protocol.LEFT)
        assert wait(lambda: server.drive.state is DriveState.LEFT)


def test_reassembles_fragmented_packet(server, wait):
    data = protocol.encode(protocol.ControlState(protocol.BACKWARD, 0, 0))
    with connect(server) as sock:
        for byte in data:
            sock.sendall(bytes([byte]))
            time.sleep(0.02)
        assert wait(lambda: server.drive.state is DriveState.BACKWARD)


def test_applies_only_latest_of_burst(server, backend, wait):
    burst = b"".join(
        protocol.encode(protocol.ControlState(flags, 0, 0))
        for flags in (protocol.FORWARD, protocol.BACKWARD, protocol.RIGHT)
    )
    with connect(server) as sock:
        sock.sendall(burst)
        assert wait(lambda: server.drive.state is DriveState.RIGHT)
        # BACKWARD (único estado que liga RB aqui) foi descartado por estar obsoleto
        assert (RB, True) not in backend.writes


def test_disconnect_stops_robot(server, wait):
    sock = connect(server)
    send(sock, protocol.FORWARD, camera_v=1)
    assert wait(lambda: server.drive.state is DriveState.FORWARD)
    sock.close()
    assert wait(lambda: server.drive.state is DriveState.STOP)


def test_watchdog_stops_and_recovers(server, wait):
    with connect(server) as sock:
        send(sock, protocol.FORWARD)
        assert wait(lambda: server.drive.state is DriveState.FORWARD)
        # Sem heartbeat: watchdog de 0.3 s precisa parar o robô
        assert wait(lambda: server.drive.state is DriveState.STOP, timeout=1.5)
        send(sock, protocol.FORWARD)  # mesmo estado de antes deve ser reaplicado
        assert wait(lambda: server.drive.state is DriveState.FORWARD)


def test_heartbeat_keeps_robot_running(server):
    with connect(server) as sock:
        for _ in range(8):  # 0.8 s, bem acima do watchdog de 0.3 s
            send(sock, protocol.FORWARD)
            time.sleep(0.1)
            assert server.drive.state is DriveState.FORWARD


def test_invalid_packet_closes_connection(server, wait):
    with connect(server) as sock:
        send(sock, protocol.FORWARD)
        assert wait(lambda: server.drive.state is DriveState.FORWARD)
        sock.sendall(b"\x00\x01\x00\x00")
        sock.settimeout(2)
        assert sock.recv(16) == b""  # servidor encerrou
    assert wait(lambda: server.drive.state is DriveState.STOP)


def test_camera_moves_while_held(server, wait):
    start = server.camera.vertical.angle
    with connect(server) as sock:
        send(sock, camera_v=1)
        time.sleep(0.15)
        send(sock)  # solta
        assert wait(lambda: server.camera.vertical.angle > start + 5)
        stopped_at = server.camera.vertical.angle
        time.sleep(0.1)
        assert server.camera.vertical.angle == stopped_at


def test_accepts_new_client_after_disconnect(server, wait):
    with connect(server) as sock:
        send(sock, protocol.LEFT)
        assert wait(lambda: server.drive.state is DriveState.LEFT)
    assert wait(lambda: server.drive.state is DriveState.STOP)
    with connect(server) as sock:
        send(sock, protocol.RIGHT)
        assert wait(lambda: server.drive.state is DriveState.RIGHT)


SHUTDOWN = protocol.encode_command(protocol.SHUTDOWN)


def assert_closed_by_server(sock) -> None:
    sock.settimeout(2)
    assert sock.recv(16) == b""


def test_shutdown_stops_robot_and_closes_connection(server, power, wait):
    with connect(server) as sock:
        send(sock, protocol.FORWARD, camera_v=1)
        assert wait(lambda: server.drive.state is DriveState.FORWARD)
        sock.sendall(SHUTDOWN)
        assert_closed_by_server(sock)
    assert power.calls == 1
    assert server.drive.state is DriveState.STOP


def test_shutdown_in_same_batch_as_states_is_not_dropped(server, power, wait):
    state = protocol.encode(protocol.ControlState(protocol.FORWARD, 0, 0))
    with connect(server) as sock:
        # Estados são descartados quando há um mais novo, comandos nunca
        sock.sendall(state + SHUTDOWN + state)
        assert_closed_by_server(sock)
    assert power.calls == 1
    assert server.drive.state is DriveState.STOP


def test_failed_shutdown_keeps_connection(server, power, wait):
    power.result = False
    with connect(server) as sock:
        sock.sendall(SHUTDOWN)
        assert wait(lambda: power.calls == 1)
        send(sock, protocol.LEFT)
        assert wait(lambda: server.drive.state is DriveState.LEFT)


def test_shutdown_without_power_control_is_ignored(backend, make_settings, wait):
    robot = RobotServer(make_settings(), backend)  # sem PowerControl
    host, port = robot.bind()
    thread = threading.Thread(target=robot.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(SHUTDOWN)
            send(sock, protocol.RIGHT)
            assert wait(lambda: robot.drive.state is DriveState.RIGHT)
    finally:
        robot.shutdown()
        thread.join(timeout=3)
        robot.close()


def test_unknown_command_closes_connection(server, power):
    with connect(server) as sock:
        sock.sendall(b"\xa6\xff\x00\x00")
        assert_closed_by_server(sock)
    assert power.calls == 0


def test_simulator_entrypoint_end_to_end():
    """Sobe `python main.py --simulate` de verdade e envia um comando."""
    env = {**os.environ, "SERVER_HOST": "127.0.0.1", "SERVER_PORT": "0", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(
        [sys.executable, "main.py", "--simulate"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True).start()

    def wait_for_line(pattern: str, timeout: float = 10.0) -> re.Match:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                match = re.search(pattern, lines.get(timeout=0.1))
            except queue.Empty:
                continue
            if match:
                return match
        raise AssertionError(f"log não encontrado: {pattern}")

    try:
        port = int(wait_for_line(r"aguardando cliente em [\d.]+:(\d+)").group(1))
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            send(sock, protocol.FORWARD)
            # O backend registra a escrita no pino antes do log de estado dos motores
            wait_for_line(rf"\[mock\] GPIO {LF} -> 1")
            wait_for_line(r"motores: FORWARD")
            # No simulador o desligamento nunca é executado de verdade
            sock.sendall(SHUTDOWN)
            wait_for_line(r"\[simulação\] o Raspberry Pi seria desligado")
    finally:
        process.terminate()
        process.wait(timeout=5)
