"""
Template de e-mail com variáveis substituíveis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.models import JobListing, MatchResult, ResumeProfile


def render_email_template(
    template_subject: str,
    template_body: str,
    profile: ResumeProfile,
    job: JobListing,
    match: MatchResult,
    smtp_config: dict,
) -> tuple[str, str]:
    """
    Renderiza o template de e-mail substituindo variáveis.

    Args:
        template_subject: Template do assunto.
        template_body: Template do corpo.
        profile: Perfil do candidato.
        job: Vaga.
        match: Resultado do match.
        smtp_config: Config SMTP.

    Returns:
        Tupla (assunto, corpo) com variáveis substituídas.
    """
    variables = {
        "vaga_titulo": job.title,
        "empresa": job.company,
        "ai_paragrafo": match.email_personalizado,
        "meu_nome": profile.nome,
        "meu_email": profile.email,
        "meu_telefone": profile.telefone,
        "minha_assinatura": smtp_config.get("signature", ""),
        "data": datetime.now().strftime("%d/%m/%Y"),
        "cidade_vaga": job.city,
        "modalidade": job.modality,
    }

    subject = template_subject
    body = template_body

    for key, value in variables.items():
        subject = subject.replace(f"{{{key}}}", str(value))
        body = body.replace(f"{{{key}}}", str(value))

    return subject, body
