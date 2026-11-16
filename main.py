"""Ponto de entrada do servidor do robô (Raspberry Pi)."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from robot_server.gpio_backend import create_backend
from robot_server.server import RobotServer
from robot_server.settings import PROJECT_DIR, load_settings
from robot_server.updater import self_update

log = logging.getLogger("robot_server")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor de controle do robô")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="não acessa o GPIO; apenas registra os comandos (roda em qualquer PC)",
    )
    parser.add_argument("--no-update", action="store_true", help="não executa o git pull")
    parser.add_argument("-v", "--verbose", action="store_true", help="log detalhado")
    return parser.parse_args()


def _raise_keyboard_interrupt(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose or args.simulate else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()

    if settings.auto_update and not args.no_update and not args.simulate:
        if self_update(PROJECT_DIR, settings.auto_update_branch):
            # Reinicia o processo para já executar o código novo
            log.info("reiniciando com a versão atualizada")
            argv = [sys.executable, *sys.argv, "--no-update"]
            os.execv(sys.executable, argv)

    backend = create_backend("mock" if args.simulate else settings.gpio_backend)
    log.info("backend de GPIO: %s", backend.name)

    # systemd envia SIGTERM ao parar o serviço: trata como Ctrl+C para limpar o GPIO
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    server = RobotServer(settings, backend)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        server.close()
        backend.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
