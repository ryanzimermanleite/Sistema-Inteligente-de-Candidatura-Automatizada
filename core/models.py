"""
Modelos de dados da aplicação.

Define as dataclasses e modelos Pydantic usados em todo o sistema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ========== ENUMS ==========


class Modality(str, Enum):
    """Modalidade de trabalho."""

    PRESENCIAL = "presencial"
    REMOTO = "remoto"
    HIBRIDO = "hibrido"


class ExperienceLevel(str, Enum):
    """Nível de experiência."""

    ESTAGIO = "estagio"
    JUNIOR = "junior"
    PLENO = "pleno"
    SENIOR = "senior"
    ESPECIALISTA = "especialista"


class ContractType(str, Enum):
    """Tipo de contrato."""

    CLT = "clt"
    PJ = "pj"
    FREELANCE = "freelance"
    TEMPORARIO = "temporario"


class ApplicationStatus(str, Enum):
    """Status de uma candidatura."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class SearchStage(str, Enum):
    """Estágio da busca."""

    IDLE = "idle"
    SEARCHING = "searching"
    FILTERING_EMAILS = "filtering_emails"
    ANALYZING_AI = "analyzing_ai"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


# ========== DATACLASSES ==========


@dataclass
class JobListing:
    """Representa uma vaga de emprego extraída do portal."""

    external_id: str
    title: str
    company: str
    city: str
    state: str
    modality: str
    description: str
    url: str
    salary_text: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    contact_emails: list[str] = field(default_factory=list)
    posted_at: Optional[datetime] = None


@dataclass
class MatchResult:
    """Resultado do match entre candidato e vaga."""

    score: int
    requisitos: list[dict] = field(default_factory=list)  # [{nome, possui}]
    lacunas: list[str] = field(default_factory=list)
    pontos_fortes: list[str] = field(default_factory=list)
    deve_aplicar: bool = False
    justificativa: str = ""
    email_personalizado: str = ""


@dataclass
class ResumeProfile:
    """Perfil extraído de um currículo pela IA."""

    nome: str
    email: str = ""
    telefone: str = ""
    cidade: str = ""
    resumo_profissional: str = ""
    skills_tecnicas: list[str] = field(default_factory=list)
    skills_comportamentais: list[str] = field(default_factory=list)
    anos_experiencia: float = 0.0
    ultimo_cargo: str = ""
    idiomas: list[dict] = field(default_factory=list)
    formacao: list[str] = field(default_factory=list)
    experiencias_resumidas: list[str] = field(default_factory=list)
    certificacoes: list[str] = field(default_factory=list)


@dataclass
class SessionStats:
    """Estatísticas de uma sessão de busca."""

    total_raw: int = 0
    total_with_email: int = 0
    total_matched: int = 0
    total_above_threshold: int = 0
    emails_sent: int = 0
    tokens_used: int = 0
    estimated_cost: float = 0.0


# ========== PYDANTIC MODELS (Validação de Input) ==========


class SearchFilters(BaseModel):
    """Filtros de busca validados pelo Pydantic."""

    query: str = Field(..., min_length=1, max_length=200, description="Cargo ou palavras-chave")
    city: str = Field(default="", max_length=100)
    state: str = Field(default="SP", max_length=2)
    modalities: list[Modality] = Field(default_factory=list)
    salary_min: Optional[float] = Field(default=None, ge=0)
    salary_max: Optional[float] = Field(default=None, ge=0)
    experience_levels: list[ExperienceLevel] = Field(default_factory=list)
    contract_types: list[ContractType] = Field(default_factory=list)
    min_score: int = Field(default=70, ge=0, le=100)
    required_keywords: list[str] = Field(default_factory=list)

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: Optional[float], info) -> Optional[float]:
        """Valida que salário máximo >= mínimo."""
        if v is not None and info.data.get("salary_min") is not None:
            if v < info.data["salary_min"]:
                raise ValueError("Salário máximo deve ser maior que o mínimo")
        return v


class SmtpConfig(BaseModel):
    """Configuração SMTP validada."""

    host: str = Field(default="smtp.gmail.com", min_length=1)
    port: int = Field(default=587, ge=1, le=65535)
    use_tls: bool = Field(default=True)
    username: str = Field(default="")
    password: str = Field(default="")
    sender_name: str = Field(default="")
    signature: str = Field(default="")


class EmailTemplate(BaseModel):
    """Template de e-mail validado."""

    subject: str = Field(
        default="Candidatura — {vaga_titulo} — {meu_nome}",
        min_length=1,
    )
    body: str = Field(
        default=(
            "Olá,\n\n"
            "{ai_paragrafo}\n\n"
            "Segue meu currículo em anexo. Coloco-me à disposição para uma conversa.\n\n"
            "Atenciosamente,\n"
            "{meu_nome}\n"
            "{meu_telefone}\n"
            "{meu_email}\n"
            "{minha_assinatura}"
        ),
        min_length=1,
    )
