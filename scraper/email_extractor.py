"""
Extrator e validador de e-mails a partir de descrições de vagas.
"""

from __future__ import annotations

import re
from typing import Optional

from loguru import logger

from config.settings import GENERIC_EMAIL_PREFIXES


EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Palavras próximas que indicam e-mail de contato para candidatura
CONTACT_KEYWORDS = [
    "envie", "enviar", "currículo", "curriculo", "cv",
    "interessados", "candidate-se", "candidatar", "encaminhar",
    "contato", "entrar em contato", "vagas", "seleção", "selecao",
    "rh", "recursos humanos", "recrutamento",
]


def extract_emails(text: str) -> list[str]:
    """
    Extrai todos os e-mails de um texto.

    Args:
        text: Texto para extrair e-mails.

    Returns:
        Lista de e-mails encontrados (sem duplicatas, em lowercase).
    """
    if not text:
        return []

    matches = EMAIL_REGEX.findall(text)
    # Remove duplicatas preservando ordem, normaliza para lowercase
    seen = set()
    unique = []
    for email in matches:
        email_lower = email.lower()
        if email_lower not in seen:
            seen.add(email_lower)
            unique.append(email_lower)

    return unique


def is_generic_email(email: str) -> bool:
    """
    Verifica se o e-mail é genérico (noreply, sac, etc.).

    Args:
        email: E-mail para verificar.

    Returns:
        True se for genérico.
    """
    email_lower = email.lower()
    for prefix in GENERIC_EMAIL_PREFIXES:
        if email_lower.startswith(prefix) or prefix in email_lower:
            return True
    return False


def validate_email_format(email: str) -> bool:
    """
    Valida o formato de um e-mail.

    Args:
        email: E-mail para validar.

    Returns:
        True se o formato é válido.
    """
    try:
        from email_validator import validate_email, EmailNotValidError
        validate_email(email, check_deliverability=False)
        return True
    except (EmailNotValidError, Exception):
        return False


def score_email_relevance(email: str, text: str) -> int:
    """
    Pontua a relevância de um e-mail baseado no contexto.

    E-mails próximos a palavras como "envie currículo" recebem pontuação maior.

    Args:
        email: E-mail encontrado.
        text: Texto completo onde o e-mail aparece.

    Returns:
        Score de relevância (0-100).
    """
    score = 50  # Score base
    text_lower = text.lower()
    email_lower = email.lower()

    # Encontra a posição do e-mail no texto
    pos = text_lower.find(email_lower)
    if pos == -1:
        return score

    # Janela de contexto (200 chars antes e depois do e-mail)
    window_start = max(0, pos - 200)
    window_end = min(len(text_lower), pos + len(email_lower) + 200)
    context = text_lower[window_start:window_end]

    # Conta palavras de contato na janela
    keyword_count = sum(1 for kw in CONTACT_KEYWORDS if kw in context)
    score += keyword_count * 10

    return min(100, score)


def filter_valid_emails(text: str) -> list[str]:
    """
    Extrai, valida e filtra e-mails de um texto.

    Retorna apenas e-mails válidos, não-genéricos, ordenados por relevância.

    Args:
        text: Texto da descrição da vaga.

    Returns:
        Lista de e-mails válidos para contato, ordenados por relevância.
    """
    raw_emails = extract_emails(text)

    if not raw_emails:
        return []

    valid_emails = []
    for email in raw_emails:
        # Pula genéricos
        if is_generic_email(email):
            logger.debug(f"E-mail genérico descartado: {email}")
            continue

        # Valida formato
        if not validate_email_format(email):
            logger.debug(f"E-mail com formato inválido: {email}")
            continue

        relevance = score_email_relevance(email, text)
        valid_emails.append((email, relevance))

    # Ordena por relevância (maior primeiro)
    valid_emails.sort(key=lambda x: x[1], reverse=True)

    result = [email for email, _ in valid_emails]

    if result:
        logger.debug(f"E-mails válidos encontrados: {result}")
    else:
        logger.debug(f"Nenhum e-mail válido (de {len(raw_emails)} encontrados)")

    return result
