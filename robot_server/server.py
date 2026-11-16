"""Servidor TCP e loop de controle do robô."""

from __future__ import annotations

import logging
import socket
import threading
import time

from . import protocol
from .camera import Camera
from .gpio_backend import GpioBackend
from .motors import Drive
from .settings import Settings
from .ultrasonic import UltrasonicSensor

log = logging.getLogger(__name__)

RECV_SIZE = protocol.PACKET_SIZE * 64
ACCEPT_TIMEOUT_S = 0.2


class RobotServer:
    def __init__(self, settings: Settings, backend: GpioBackend) -> None:
        self._settings = settings
        self._listener: socket.socket | None = None
        self._shutdown = threading.Event()
        self.drive = Drive(
            backend,
            right_forward=settings.motor_right_forward_pin,
            right_backward=settings.motor_right_backward_pin,
            left_forward=settings.motor_left_forward_pin,
            left_backward=settings.motor_left_backward_pin,
        )
        self.camera = Camera(
            backend,
            settings.camera_vertical,
            settings.camera_horizontal,
            settings.camera_speed_dps,
            settings.servo_release_after_s,
        )
        self.ultrasonic: UltrasonicSensor | None = None
        if settings.ultrasonic_enabled:
            self.ultrasonic = UltrasonicSensor(
                backend,
                settings.ultrasonic_trig_pin,
                settings.ultrasonic_echo_pin,
                settings.ultrasonic_rate_hz,
                settings.ultrasonic_max_distance_m,
                settings.speed_of_sound_mps,
            )
            self.ultrasonic.start()

    def bind(self) -> tuple[str, int]:
        """Abre a porta de escuta e retorna o endereço real (útil com porta 0)."""
        if self._listener is None:
            address = (self._settings.host, self._settings.port)
            # create_server já habilita SO_REUSEADDR no Linux (reinício rápido)
            self._listener = socket.create_server(address, backlog=1)
            # Timeout no accept para o Ctrl+C e o shutdown() funcionarem (inclusive no Windows)
            self._listener.settimeout(ACCEPT_TIMEOUT_S)
        return self._listener.getsockname()[:2]

    def shutdown(self) -> None:
        """Pede para serve_forever() terminar (após o cliente atual desconectar)."""
        self._shutdown.set()

    def serve_forever(self) -> None:
        log.info("aguardando cliente em %s:%d", *self.bind())
        listener = self._listener
        with listener:
            while not self._shutdown.is_set():
                try:
                    connection, client = listener.accept()
                except socket.timeout:
                    # Sem cliente a câmera está parada: só processa a liberação dos servos
                    # (sem isso o pulso ficava ativo até a primeira conexão e o servo tremia)
                    self.camera.update(time.monotonic(), 0.0)
                    continue
                # O socket aceito herdaria o timeout do listener; o loop define o seu
                connection.settimeout(None)
                log.info("cliente conectado: %s:%d", *client)
                try:
                    with connection:
                        self._handle_client(connection)
                except (OSError, protocol.ProtocolError) as exc:
                    log.warning("conexão encerrada com erro: %s", exc)
                finally:
                    self.halt()
                    log.info("cliente desconectado")

    def halt(self) -> None:
        """Para motores e câmera (desconexão, watchdog ou encerramento)."""
        self.drive.stop()
        self.camera.set_direction(0, 0, time.monotonic())
        self.camera.release()

    def close(self) -> None:
        self.halt()
        if self.ultrasonic is not None:
            self.ultrasonic.stop()

    def _handle_client(self, connection: socket.socket) -> None:
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tick = self._settings.control_tick_s
        watchdog = self._settings.watchdog_timeout_s
        buffer = bytearray()
        last_state: protocol.ControlState | None = None
        last_packet = last_update = time.monotonic()
        watchdog_tripped = False

        while True:
            # Acorda rápido apenas quando há movimento da câmera em andamento
            if self.camera.needs_update:
                connection.settimeout(tick)
            elif watchdog > 0 and not watchdog_tripped:
                connection.settimeout(max(tick, watchdog - (time.monotonic() - last_packet)))
            else:
                connection.settimeout(None)

            try:
                chunk = connection.recv(RECV_SIZE)
                if not chunk:
                    return
                buffer += chunk
                last_packet = time.monotonic()
            except socket.timeout:
                pass

            now = time.monotonic()
            complete = len(buffer) // protocol.PACKET_SIZE
            if complete:
                # Só o pacote mais recente importa; os anteriores já estão obsoletos
                state = protocol.decode(buffer, (complete - 1) * protocol.PACKET_SIZE)
                del buffer[: complete * protocol.PACKET_SIZE]
                if state != last_state or watchdog_tripped:
                    log.debug("estado recebido: %s", state)
                    self.drive.apply(state.flags)
                    self.camera.set_direction(state.camera_v, state.camera_h, now)
                    last_state = state
                    watchdog_tripped = False

            if watchdog > 0 and not watchdog_tripped and now - last_packet > watchdog:
                log.warning("watchdog: sem pacotes há %.1fs, parando o robô", now - last_packet)
                self.drive.stop()
                self.camera.set_direction(0, 0, now)
                watchdog_tripped = True

            self.camera.update(now, now - last_update)
            last_update = now
