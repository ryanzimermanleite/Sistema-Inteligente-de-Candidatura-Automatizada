"""
Banco de dados SQLite com SQLAlchemy.

Define as tabelas e fornece funções para inicialização e acesso.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from loguru import logger


# ========== BASE ==========


class Base(DeclarativeBase):
    """Base declarativa para todos os modelos ORM."""

    pass


# ========== TABELAS ==========


class ResumeRecord(Base):
    """Registro de currículo analisado."""

    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False, default="")
    file_hash = Column(String(64), nullable=False, unique=True)
    parsed_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SearchRecord(Base):
    """Registro de uma busca realizada."""

    __tablename__ = "searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(200), nullable=False)
    filters_json = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_raw = Column(Integer, default=0)
    total_with_email = Column(Integer, default=0)
    total_matched = Column(Integer, default=0)


class JobRecord(Base):
    """Registro de uma vaga encontrada."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_id = Column(Integer, nullable=True)
    external_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False, default="")
    city = Column(String(100), nullable=False, default="")
    state = Column(String(2), nullable=False, default="")
    modality = Column(String(20), nullable=False, default="")
    salary_text = Column(String(200), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    description = Column(Text, nullable=False, default="")
    requirements = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    contact_emails = Column(Text, nullable=True)  # JSON array
    posted_at = Column(DateTime, nullable=True)
    url = Column(String(1000), nullable=False)
    match_score = Column(Integer, nullable=True)
    match_data_json = Column(Text, nullable=True)
    is_saved = Column(Boolean, default=False)
    is_discarded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("external_id", name="uq_job_external_id"),)


class ApplicationRecord(Base):
    """Registro de uma candidatura enviada."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False)
    recipient_email = Column(String(320), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="sent")
    error_message = Column(Text, nullable=True)
    message_id = Column(String(200), nullable=True)


class BlacklistCompany(Base):
    """Empresa na blacklist."""

    __tablename__ = "blacklist_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(300), nullable=False, unique=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class PageCache(Base):
    """Cache de páginas scrapeadas."""

    __tablename__ = "page_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1000), nullable=False, unique=True)
    html = Column(Text, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class SettingsRecord(Base):
    """Configurações gerais (não-sensíveis)."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)


class AILogRecord(Base):
    """Log de chamadas à OpenAI."""

    __tablename__ = "ai_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_type = Column(String(50), nullable=False)  # "resume_parse" | "match" | "cover_letter" | "cv_analysis"
    model = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    prompt_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ========== ENGINE E SESSION ==========

_engine = None
_SessionFactory = None


def _get_db_path() -> str:
    """Retorna o caminho do banco de dados."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "vagas.db")


def get_engine():
    """Retorna a engine do SQLAlchemy (singleton)."""
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        logger.debug(f"Engine SQLAlchemy criada: {db_path}")
    return _engine


def get_session() -> Session:
    """Cria uma nova sessão do banco de dados."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()


def init_database() -> None:
    """Cria todas as tabelas no banco se não existirem."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Tabelas do banco de dados criadas/verificadas")

    # Cria diretórios de dados necessários
    data_dir = os.path.dirname(_get_db_path())
    os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "cv_uploads"), exist_ok=True)
