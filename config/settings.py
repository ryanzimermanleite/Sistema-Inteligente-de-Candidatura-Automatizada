"""
Configurações da aplicação com Pydantic Settings.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from loguru import logger

from core.database import SettingsRecord, get_session


# ========== PATHS ==========

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CV_UPLOADS_DIR = os.path.join(DATA_DIR, "cv_uploads")
LOGS_DIR = os.path.join(DATA_DIR, "logs")


# ========== MODELOS DISPONÍVEIS ==========

AVAILABLE_MODELS = [
    ("gpt-4o-mini", "gpt-4o-mini (recomendado — mais barato)"),
    ("gpt-4o", "gpt-4o"),
    ("gpt-4-turbo", "gpt-4-turbo"),
    ("gpt-3.5-turbo", "gpt-3.5-turbo"),
]

# Custo por 1M tokens (input/output) em USD
MODEL_COSTS = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


# ========== E-MAILS GENÉRICOS A IGNORAR ==========

GENERIC_EMAIL_PREFIXES = [
    "naoresponda",
    "noreply",
    "no-reply",
    "donotreply",
    "atendimento",
    "sac",
    "suporte",
    "support",
    "contato@empregacampinas",
    "admin",
    "webmaster",
    "postmaster",
    "mailer-daemon",
    "info@empregacampinas",
]


# ========== CIDADES DA REGIÃO DE CAMPINAS ==========

CAMPINAS_REGION_CITIES = [
    "Campinas",
    "Americana",
    "Artur Nogueira",
    "Cosmópolis",
    "Engenheiro Coelho",
    "Holambra",
    "Hortolândia",
    "Indaiatuba",
    "Itatiba",
    "Jaguariúna",
    "Monte Mor",
    "Morungaba",
    "Nova Odessa",
    "Paulínia",
    "Pedreira",
    "Santa Bárbara d'Oeste",
    "Santo Antônio de Posse",
    "Sumaré",
    "Valinhos",
    "Vinhedo",
    "Limeira",
    "Piracicaba",
    "Rio Claro",
    "São José dos Campos",
    "Sorocaba",
    "Jundiaí",
    "São Paulo",
]


# ========== FUNÇÕES DE CONFIGURAÇÃO ==========


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Obtém uma configuração do banco de dados.

    Args:
        key: Chave da configuração.
        default: Valor padrão se não existir.

    Returns:
        Valor da configuração ou default.
    """
    try:
        session = get_session()
        record = session.query(SettingsRecord).filter_by(key=key).first()
        session.close()
        if record:
            return record.value
        return default
    except Exception as e:
        logger.warning(f"Erro ao ler configuração '{key}': {e}")
        return default


def set_setting(key: str, value: str) -> None:
    """
    Salva uma configuração no banco de dados.

    Args:
        key: Chave da configuração.
        value: Valor a salvar.
    """
    try:
        session = get_session()
        record = session.query(SettingsRecord).filter_by(key=key).first()
        if record:
            record.value = value
        else:
            record = SettingsRecord(key=key, value=value)
            session.add(record)
        session.commit()
        session.close()
    except Exception as e:
        logger.error(f"Erro ao salvar configuração '{key}': {e}")


def get_smtp_config() -> dict:
    """Retorna a configuração SMTP do banco."""
    config_json = get_setting("smtp_config", "{}")
    try:
        return json.loads(config_json)
    except json.JSONDecodeError:
        return {}


def save_smtp_config(config: dict) -> None:
    """Salva a configuração SMTP no banco."""
    set_setting("smtp_config", json.dumps(config, ensure_ascii=False))


def get_email_template() -> dict:
    """Retorna o template de e-mail do banco."""
    default_template = {
        "subject": "Candidatura — {vaga_titulo} — {meu_nome}",
        "body": (
            "Olá,\n\n"
            "{ai_paragrafo}\n\n"
            "Segue meu currículo em anexo. Coloco-me à disposição para uma conversa.\n\n"
            "Atenciosamente,\n"
            "{meu_nome}\n"
            "{meu_telefone}\n"
            "{meu_email}\n"
            "{minha_assinatura}"
        ),
    }
    template_json = get_setting("email_template")
    if template_json:
        try:
            return json.loads(template_json)
        except json.JSONDecodeError:
            pass
    return default_template


def save_email_template(template: dict) -> None:
    """Salva o template de e-mail no banco."""
    set_setting("email_template", json.dumps(template, ensure_ascii=False))


def get_appearance() -> dict:
    """Retorna configurações de aparência."""
    default = {"theme": "dark", "font_size": 14}
    appearance_json = get_setting("appearance")
    if appearance_json:
        try:
            return json.loads(appearance_json)
        except json.JSONDecodeError:
            pass
    return default


def save_appearance(config: dict) -> None:
    """Salva configurações de aparência."""
    set_setting("appearance", json.dumps(config))
