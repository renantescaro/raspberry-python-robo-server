import sys

from robot_server.power import PowerControl


def test_runs_command(tmp_path):
    marker = tmp_path / "desligou"
    power = PowerControl([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
    assert power.shutdown() is True
    assert marker.exists()


def test_failing_command_returns_false():
    power = PowerControl([sys.executable, "-c", "import sys; sys.stderr.write('sem permissão'); sys.exit(1)"])
    assert power.shutdown() is False


def test_missing_executable_returns_false():
    assert PowerControl(["comando-que-nao-existe-123"]).shutdown() is False


def test_disabled_does_not_run(tmp_path):
    marker = tmp_path / "desligou"
    power = PowerControl([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], enabled=False)
    assert power.shutdown() is False
    assert not marker.exists()


def test_simulation_only_logs(caplog):
    assert PowerControl(None).shutdown() is True
    assert "simulação" in caplog.text
