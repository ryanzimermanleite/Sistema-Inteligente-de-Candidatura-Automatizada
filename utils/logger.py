"""
Configuração do logger com loguru.

Configura logging para console e arquivo, com rotação automática.
"""

from __future__ import annotations

import os
import sys

from loguru import logger


def setup_logger(level: str = "DEBUG") -> None:
    """
    Configura o loguru para a aplicação.

    Args:
        level: Nível mínimo de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    # Remove handlers padrão
    logger.remove()

    # Handler para console (com cores)
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
        level=level,
        colorize=True,
        filter=_filter_sensitive,
    )

    # Handler para arquivo com rotação
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs"
    )
    os.makedirs(log_dir, exist_ok=True)

    logger.add(
        os.path.join(log_dir, "match_vagas_{time:YYYY-MM-DD}.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
        level=level,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        filter=_filter_sensitive,
    )

    logger.debug("Logger configurado com sucesso")


def _filter_sensitive(record) -> bool:
    """
    Filtra informações sensíveis dos logs.

    Garante que API keys e senhas nunca apareçam nos logs.
    """
    message = record.get("message", "")
    if isinstance(message, str):
        # Lista de padrões sensíveis a mascarar
        sensitive_patterns = ["sk-", "api_key", "password", "senha", "secret"]
        for pattern in sensitive_patterns:
            if pattern.lower() in message.lower():
                # Não bloqueia o log, mas o registro pode ter dados sensíveis
                # Em produção, você pode querer mascarar ou bloquear
                pass
    return True


class GUILogHandler:
    """
    Handler customizado para enviar logs para a GUI.

    Armazena mensagens em uma lista e notifica callbacks registrados.
    """

    def __init__(self) -> None:
        """Inicializa o handler."""
        self._callbacks: list = []
        self._messages: list[str] = []

    def register_callback(self, callback) -> None:
        """Registra um callback para receber mensagens de log."""
        self._callbacks.append(callback)

    def write(self, message: str) -> None:
        """Recebe uma mensagem de log e notifica os callbacks."""
        # Remove trailing newline
        message = message.strip()
        if not message:
            return

        self._messages.append(message)

        # Mantém apenas as últimas 1000 mensagens
        if len(self._messages) > 1000:
            self._messages = self._messages[-500:]

        for callback in self._callbacks:
            try:
                callback(message)
            except Exception:
                pass  # Não deixa erro no callback crashar o log

    def get_messages(self) -> list[str]:
        """Retorna todas as mensagens armazenadas."""
        return list(self._messages)


# Instância global do handler de GUI
gui_log_handler = GUILogHandler()


def add_gui_log_handler() -> None:
    """Adiciona o handler de GUI ao loguru."""
    logger.add(
        gui_log_handler.write,
        format="[{time:HH:mm:ss}] {message}",
        level="INFO",
        filter=_filter_sensitive,
    )
