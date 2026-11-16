"""Testes do streaming MJPEG com uma câmera falsa (roda fora do Pi)."""

from __future__ import annotations

import http.client
import threading
import time

import pytest

from robot_server.streaming import BOUNDARY, FrameBuffer, StreamHub, create_server


class FakeSource:
    """Gera quadros "JPEG" numerados enquanto está ligada."""

    def __init__(self, interval: float = 0.01, produce: bool = True) -> None:
        self.interval = interval
        self.produce = produce
        self.starts = 0
        self.stops = 0
        self.closed = False
        self._running = threading.Event()

    def start(self, output: FrameBuffer) -> None:
        self.starts += 1
        self._running.set()
        if self.produce:
            threading.Thread(target=self._run, args=(output,), daemon=True).start()

    def _run(self, output: FrameBuffer) -> None:
        n = 0
        while self._running.is_set():
            n += 1
            output.write(b"\xff\xd8quadro-%d\xff\xd9" % n)
            time.sleep(self.interval)

    def stop(self) -> None:
        self.stops += 1
        self._running.clear()

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def stream_server():
    servers = []

    def factory(source: FakeSource, frame_timeout: float = 2.0):
        hub = StreamHub(source)
        httpd = create_server("127.0.0.1", 0, hub, frame_timeout)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        servers.append(httpd)
        return hub, httpd.server_address[1]

    yield factory
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


def read_frames(response: http.client.HTTPResponse, count: int) -> list[bytes]:
    """Lê `count` partes do multipart/x-mixed-replace."""
    frames = []
    while len(frames) < count:
        line = response.fp.readline()
        if not line:
            break
        if line.strip() != b"--" + BOUNDARY:
            continue
        headers = {}
        while (header := response.fp.readline().strip()):
            name, _, value = header.decode().partition(":")
            headers[name.lower()] = value.strip()
        assert headers["content-type"] == "image/jpeg"
        frames.append(response.fp.read(int(headers["content-length"])))
    return frames


# ------------------------------------------------------------------ FrameBuffer


def test_frame_buffer_returns_newer_frame():
    buffer = FrameBuffer()
    buffer.write(b"a")
    frame_id, frame = buffer.wait_frame(0, timeout=0.1)
    assert frame == b"a"
    assert buffer.wait_frame(frame_id, timeout=0.05) is None  # nada novo
    buffer.write(memoryview(b"b"))
    assert buffer.wait_frame(frame_id, timeout=0.1)[1] == b"b"


def test_frame_buffer_wakes_waiting_reader():
    buffer = FrameBuffer()
    threading.Timer(0.05, buffer.write, args=(b"x",)).start()
    assert buffer.wait_frame(0, timeout=2)[1] == b"x"


# --------------------------------------------------------------------- StreamHub


def test_hub_starts_camera_on_first_viewer_and_stops_on_last():
    source = FakeSource(produce=False)
    hub = StreamHub(source)
    hub.acquire()
    hub.acquire()
    assert (source.starts, source.stops, hub.viewers) == (1, 0, 2)
    hub.release()
    assert source.stops == 0
    hub.release()
    assert (source.starts, source.stops, hub.viewers) == (1, 1, 0)
    hub.acquire()
    assert source.starts == 2


# ------------------------------------------------------------------ HTTP (integração)


@pytest.mark.parametrize("path", ["/?action=stream", "/stream", "/stream.mjpg", "/"])
def test_serves_mjpeg_stream(stream_server, path):
    source = FakeSource()
    hub, port = stream_server(source)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == "multipart/x-mixed-replace; boundary=FRAME"
    frames = read_frames(response, 3)
    assert len(frames) == 3
    assert all(f.startswith(b"\xff\xd8") and f.endswith(b"\xff\xd9") for f in frames)
    assert len(set(frames)) == 3  # quadros diferentes, sem repetir
    conn.close()


def test_unknown_path_is_404(stream_server):
    _, port = stream_server(FakeSource())
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/favicon.ico")
    assert conn.getresponse().status == 404
    conn.close()


def test_camera_turns_off_after_viewer_leaves(stream_server, wait):
    source = FakeSource()
    hub, port = stream_server(source)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/?action=stream")
    read_frames(conn.getresponse(), 1)
    assert hub.viewers == 1 and source.starts == 1
    conn.close()
    # O servidor percebe a desconexão na próxima escrita
    assert wait(lambda: hub.viewers == 0, timeout=3)
    assert source.stops == 1


def test_two_viewers_share_one_camera(stream_server, wait):
    source = FakeSource()
    hub, port = stream_server(source)
    viewers = []
    for _ in range(2):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/?action=stream")
        response = conn.getresponse()
        assert len(read_frames(response, 2)) == 2
        # A resposta é dona do socket: se for coletada, a conexão fecha
        viewers.append((conn, response))
    assert hub.viewers == 2
    assert source.starts == 1
    for conn, response in viewers:
        response.close()
        conn.close()
    assert wait(lambda: hub.viewers == 0, timeout=3)


def test_stream_ends_when_camera_produces_nothing(stream_server, wait):
    source = FakeSource(produce=False)
    hub, port = stream_server(source, frame_timeout=0.2)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/?action=stream")
    response = conn.getresponse()
    assert response.status == 200
    assert response.read() == b""  # servidor encerra a resposta
    assert wait(lambda: hub.viewers == 0)
    assert source.stops == 1
    conn.close()
