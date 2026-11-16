"""Streaming MJPEG da câmera por HTTP.

Executa como processo separado do controle (`python -m robot_server.streaming`):
uma falha na câmera não afeta os motores. A URL segue o formato do
mjpg-streamer (`http://<pi>:8080/?action=stream`), que o cliente lê com OpenCV.

Desempenho:
- JPEG gerado pelo codificador de hardware do Pi (MJPEGEncoder do picamera2).
- A câmera só fica ligada enquanto houver alguém assistindo (menos consumo
  e aquecimento; o Pi 3 é sensível à fonte).
- Cada quadro é codificado uma vez e compartilhado entre todos os clientes.
"""

from __future__ import annotations

import argparse
import io
import logging
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

BOUNDARY = b"FRAME"
STREAM_PATHS = {"/", "/stream", "/stream.mjpg"}
FRAME_TIMEOUT_S = 5.0


class FrameBuffer(io.BufferedIOBase):
    """Guarda só o quadro JPEG mais recente e acorda quem está esperando."""

    def __init__(self) -> None:
        super().__init__()
        self._condition = threading.Condition()
        self._frame: bytes | None = None
        self._frame_id = 0

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        frame = bytes(data)
        with self._condition:
            self._frame = frame
            self._frame_id += 1
            self._condition.notify_all()
        return len(frame)

    def wait_frame(self, last_id: int, timeout: float) -> tuple[int, bytes] | None:
        """Espera um quadro mais novo que `last_id`; None se nada chegar no prazo."""
        with self._condition:
            if not self._condition.wait_for(lambda: self._frame_id != last_id, timeout):
                return None
            return self._frame_id, self._frame


class CameraSource(Protocol):
    def start(self, output: FrameBuffer) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class Picamera2Source:
    def __init__(self, size: tuple[int, int], fps: float) -> None:
        from picamera2 import Picamera2  # import tardio: só existe no Raspberry Pi

        self._camera = Picamera2()
        config = self._camera.create_video_configuration(
            main={"size": size}, controls={"FrameRate": fps}
        )
        self._camera.configure(config)

    def start(self, output: FrameBuffer) -> None:
        from picamera2.encoders import MJPEGEncoder
        from picamera2.outputs import FileOutput

        self._camera.start_recording(MJPEGEncoder(), FileOutput(output))

    def stop(self) -> None:
        self._camera.stop_recording()

    def close(self) -> None:
        self._camera.close()


class StreamHub:
    """Liga a câmera no primeiro espectador e desliga quando o último sai."""

    def __init__(self, source: CameraSource) -> None:
        self.buffer = FrameBuffer()
        self._source = source
        self._lock = threading.Lock()
        self._viewers = 0

    @property
    def viewers(self) -> int:
        return self._viewers

    def acquire(self) -> None:
        with self._lock:
            if self._viewers == 0:
                log.info("câmera ligada")
                self._source.start(self.buffer)
            self._viewers += 1

    def release(self) -> None:
        with self._lock:
            self._viewers -= 1
            if self._viewers == 0:
                self._source.stop()
                log.info("câmera desligada (sem espectadores)")


def make_handler(hub: StreamHub, frame_timeout: float = FRAME_TIMEOUT_S):
    class StreamHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlsplit(self.path).path not in STREAM_PATHS:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
            self.end_headers()

            hub.acquire()
            log.info("espectador conectado: %s", self.client_address[0])
            try:
                last_id = 0
                while True:
                    received = hub.buffer.wait_frame(last_id, frame_timeout)
                    if received is None:
                        log.warning("nenhum quadro da câmera em %.1fs; encerrando", frame_timeout)
                        return
                    last_id, frame = received
                    self.wfile.write(
                        b"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n%s\r\n"
                        % (BOUNDARY, len(frame), frame)
                    )
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                hub.release()
                log.info("espectador desconectado: %s", self.client_address[0])

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - assinatura da base
            log.debug("%s - %s", self.client_address[0], format % args)

    return StreamHandler


def create_server(host: str, port: int, hub: StreamHub, frame_timeout: float = FRAME_TIMEOUT_S):
    httpd = ThreadingHTTPServer((host, port), make_handler(hub, frame_timeout))
    httpd.daemon_threads = True
    return httpd


def _raise_keyboard_interrupt(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main() -> int:
    from .settings import load_settings

    parser = argparse.ArgumentParser(description="Streaming MJPEG da câmera do robô")
    parser.add_argument("-v", "--verbose", action="store_true", help="log detalhado")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    source = Picamera2Source(settings.stream_size, settings.stream_fps)
    httpd = create_server(settings.stream_host, settings.stream_port, StreamHub(source))
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    width, height = settings.stream_size
    log.info(
        "streaming em http://%s:%d/?action=stream (%dx%d @ %g fps)",
        settings.stream_host, httpd.server_address[1], width, height, settings.stream_fps,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        httpd.server_close()
        source.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
