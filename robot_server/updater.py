"""Auto-atualização via `git pull` na inicialização."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _git(project_dir: Path, *args: str, timeout: float = 30) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_dir), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout.strip()


def self_update(project_dir: Path, branch: str) -> bool:
    """Executa `git pull` e retorna True se o código foi alterado."""
    if not (project_dir / ".git").exists():
        log.info("auto-update ignorado: %s não é um repositório git", project_dir)
        return False
    try:
        before = _git(project_dir, "rev-parse", "HEAD")
        _git(project_dir, "pull", "--ff-only", "origin", branch)
        after = _git(project_dir, "rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError) as exc:
        # Sem rede ou conflito: segue com a versão local
        log.warning("auto-update falhou: %s", exc)
        return False
    if before != after:
        log.info("código atualizado %s -> %s", before[:7], after[:7])
        return True
    return False
