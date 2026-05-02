"""
Testes para os modelos de dados e filtros.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.models import (
    JobListing,
    MatchResult,
    ResumeProfile,
    SearchFilters,
    SessionStats,
    SmtpConfig,
    EmailTemplate,
)


class TestSearchFilters:
    """Testes de validação de filtros de busca."""

    def test_valid_filters(self):
        f = SearchFilters(query="Programador Java")
        assert f.query == "Programador Java"
        assert f.state == "SP"
        assert f.min_score == 70

    def test_empty_query_fails(self):
        with pytest.raises(Exception):
            SearchFilters(query="")

    def test_salary_range_valid(self):
        f = SearchFilters(query="Dev", salary_min=3000, salary_max=5000)
        assert f.salary_min == 3000
        assert f.salary_max == 5000

    def test_salary_range_invalid(self):
        with pytest.raises(Exception):
            SearchFilters(query="Dev", salary_min=5000, salary_max=3000)

    def test_score_range(self):
        f = SearchFilters(query="Dev", min_score=0)
        assert f.min_score == 0

        f2 = SearchFilters(query="Dev", min_score=100)
        assert f2.min_score == 100

        with pytest.raises(Exception):
            SearchFilters(query="Dev", min_score=-1)

        with pytest.raises(Exception):
            SearchFilters(query="Dev", min_score=101)


class TestJobListing:
    """Testes do modelo de vaga."""

    def test_create_job(self):
        job = JobListing(
            external_id="123",
            title="Dev Java",
            company="TechCorp",
            city="Campinas",
            state="SP",
            modality="presencial",
            description="Vaga para dev java",
            url="https://example.com/vaga/123",
        )
        assert job.title == "Dev Java"
        assert job.contact_emails == []
        assert job.salary_min is None


class TestMatchResult:
    """Testes do resultado de match."""

    def test_create_match(self):
        m = MatchResult(score=85)
        assert m.score == 85
        assert m.pontos_fortes == []
        assert m.deve_aplicar is False


class TestSmtpConfig:
    """Testes da configuração SMTP."""

    def test_defaults(self):
        c = SmtpConfig()
        assert c.host == "smtp.gmail.com"
        assert c.port == 587
        assert c.use_tls is True


class TestSessionStats:
    """Testes das estatísticas de sessão."""

    def test_defaults(self):
        s = SessionStats()
        assert s.total_raw == 0
        assert s.estimated_cost == 0.0
