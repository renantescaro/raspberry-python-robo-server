"""Desligamento do Raspberry Pi a pedido do cliente.

O serviço roda como usuário comum; o comando padrão usa `sudo -n`, liberado
apenas para `systemctl poweroff` por deploy/sudoers-robot-shutdown.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Sequence

log = logging.getLogger(__name__)


class PowerControl:
    def __init__(self, command: Sequence[str] | None, enabled: bool = True) -> None:
        """`command=None` = modo simulação: só registra no log."""
        self._command = tuple(command) if command is not None else None
        self._enabled = enabled

    def shutdown(self) -> bool:
        """Desliga o sistema. Retorna True se o desligamento foi iniciado."""
        if not self._enabled:
            log.warning("desligamento pedido, mas SHUTDOWN_ENABLED=false")
            return False
        if self._command is None:
            log.warning("[simulação] o Raspberry Pi seria desligado agora")
            return True
        log.warning("desligando o Raspberry Pi: %s", " ".join(self._command))
        try:
            subprocess.run(self._command, check=True, capture_output=True, text=True, timeout=15)
        except subprocess.CalledProcessError as exc:
            log.error("falha ao desligar (código %s): %s", exc.returncode, exc.stderr.strip())
            return False
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.error("falha ao desligar: %s", exc)
            return False
        return True
