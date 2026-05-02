"""
Cliente SMTP para envio de e-mails com currículo anexado.
"""

from __future__ import annotations

import os
import smtplib
import time
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from loguru import logger

from config.settings import get_smtp_config
from core.database import ApplicationRecord, get_session
from core.exceptions import EmailError, SmtpAuthError, SmtpConnectionError
from utils.crypto import get_smtp_password


_last_send_time: Optional[float] = None
MIN_SEND_INTERVAL = 30  # Segundos entre envios


def test_smtp_connection(config: dict) -> bool:
    """Testa a conexão SMTP. Retorna True se OK."""
    try:
        password = get_smtp_password() or config.get("password", "")
        server = _connect_smtp(config, password)
        server.quit()
        logger.info("Teste de conexão SMTP: OK")
        return True
    except Exception as e:
        logger.error(f"Teste SMTP falhou: {e}")
        raise SmtpConnectionError(f"Falha na conexão: {e}") from e


def _connect_smtp(config: dict, password: str) -> smtplib.SMTP:
    """Cria e autentica uma conexão SMTP."""
    try:
        server = smtplib.SMTP(config["host"], config["port"], timeout=30)
        if config.get("use_tls", True):
            server.starttls()
        if config.get("username") and password:
            server.login(config["username"], password)
        return server
    except smtplib.SMTPAuthenticationError as e:
        raise SmtpAuthError(f"Erro de autenticação: {e}") from e
    except Exception as e:
        raise SmtpConnectionError(f"Erro de conexão: {e}") from e


def check_duplicate(job_id: int, recipient_email: str, days: int = 30) -> bool:
    """Verifica se já enviou e-mail para este destinatário recentemente."""
    try:
        session = get_session()
        cutoff = datetime.utcnow() - timedelta(days=days)
        existing = (
            session.query(ApplicationRecord)
            .filter(
                ApplicationRecord.job_id == job_id,
                ApplicationRecord.recipient_email == recipient_email,
                ApplicationRecord.status == "sent",
                ApplicationRecord.sent_at >= cutoff,
            )
            .first()
        )
        session.close()
        return existing is not None
    except Exception:
        return False


def send_email(
    recipient: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    job_id: int = 0,
    dry_run: bool = False,
) -> dict:
    """
    Envia um e-mail com anexo opcional.

    Args:
        recipient: E-mail do destinatário.
        subject: Assunto.
        body: Corpo do e-mail.
        attachment_path: Caminho do arquivo a anexar.
        job_id: ID da vaga no banco.
        dry_run: Se True, não envia de verdade.

    Returns:
        Dict com {success, message_id, error}.
    """
    global _last_send_time

    # Rate limit
    if _last_send_time is not None:
        elapsed = time.time() - _last_send_time
        if elapsed < MIN_SEND_INTERVAL:
            wait = MIN_SEND_INTERVAL - elapsed
            logger.info(f"Rate limit: aguardando {wait:.0f}s")
            time.sleep(wait)

    config = get_smtp_config()
    if not config.get("host"):
        raise EmailError("SMTP não configurado")

    if dry_run:
        logger.info(f"[DRY RUN] E-mail para {recipient}: {subject}")
        _save_application(job_id, recipient, subject, body, "dry_run")
        return {"success": True, "message_id": "dry-run", "error": None}

    try:
        password = get_smtp_password() or ""
        sender = config.get("username", "")
        sender_name = config.get("sender_name", "")

        # Monta a mensagem
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{sender}>" if sender_name else sender
        msg["To"] = recipient
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Anexo
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(attachment_path)}",
            )
            msg.attach(part)

        # Envia
        server = _connect_smtp(config, password)
        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()

        _last_send_time = time.time()
        message_id = msg.get("Message-ID", "")

        logger.info(f"E-mail enviado para {recipient}: {subject}")
        _save_application(job_id, recipient, subject, body, "sent", message_id=message_id)

        return {"success": True, "message_id": message_id, "error": None}

    except (SmtpAuthError, SmtpConnectionError):
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao enviar e-mail: {error_msg}")
        _save_application(job_id, recipient, subject, body, "failed", error_message=error_msg)
        return {"success": False, "message_id": None, "error": error_msg}


def _save_application(
    job_id: int,
    recipient: str,
    subject: str,
    body: str,
    status: str,
    message_id: str = "",
    error_message: str = "",
) -> None:
    """Salva registro de candidatura no banco."""
    try:
        session = get_session()
        session.add(ApplicationRecord(
            job_id=job_id,
            recipient_email=recipient,
            subject=subject,
            body=body,
            status=status,
            message_id=message_id,
            error_message=error_message,
        ))
        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"Erro ao salvar candidatura: {e}")
