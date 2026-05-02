"""
Testes para os templates de e-mail.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.models import JobListing, MatchResult, ResumeProfile
from email_sender.templates import render_email_template


class TestEmailTemplates:
    """Testes de renderização de templates de e-mail."""

    def _make_profile(self) -> ResumeProfile:
        return ResumeProfile(
            nome="João Silva",
            email="joao@email.com",
            telefone="(19) 99999-0000",
        )

    def _make_job(self) -> JobListing:
        return JobListing(
            external_id="1",
            title="Dev Java Pleno",
            company="TechCorp",
            city="Campinas",
            state="SP",
            modality="presencial",
            description="Vaga para dev",
            url="https://example.com",
            contact_emails=["rh@techcorp.com"],
        )

    def _make_match(self) -> MatchResult:
        return MatchResult(
            score=85,
            email_personalizado="Tenho experiência relevante para a posição.",
        )

    def test_subject_replacement(self):
        subject_tpl = "Candidatura — {vaga_titulo} — {meu_nome}"
        body_tpl = "Corpo"
        subject, body = render_email_template(
            subject_tpl, body_tpl,
            self._make_profile(), self._make_job(), self._make_match(), {},
        )
        assert "Dev Java Pleno" in subject
        assert "João Silva" in subject

    def test_body_replacement(self):
        subject_tpl = "Test"
        body_tpl = "Olá,\n\n{ai_paragrafo}\n\n{meu_nome}\n{meu_email}"
        subject, body = render_email_template(
            subject_tpl, body_tpl,
            self._make_profile(), self._make_job(), self._make_match(), {},
        )
        assert "Tenho experiência relevante" in body
        assert "João Silva" in body
        assert "joao@email.com" in body

    def test_empty_variables(self):
        subject_tpl = "{vaga_titulo}"
        body_tpl = "{empresa} - {ai_paragrafo}"
        subject, body = render_email_template(
            subject_tpl, body_tpl,
            self._make_profile(), self._make_job(), self._make_match(), {},
        )
        assert subject == "Dev Java Pleno"
        assert "TechCorp" in body
