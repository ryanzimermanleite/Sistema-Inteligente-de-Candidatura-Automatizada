"""
Testes para o extrator de e-mails.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.email_extractor import (
    extract_emails,
    filter_valid_emails,
    is_generic_email,
    score_email_relevance,
    validate_email_format,
)


class TestExtractEmails:
    """Testes de extração de e-mails."""

    def test_extract_single_email(self):
        assert extract_emails("contato: joao@empresa.com") == ["joao@empresa.com"]

    def test_extract_multiple_emails(self):
        text = "Envie para rh@corp.com.br ou dev@tech.io"
        result = extract_emails(text)
        assert len(result) == 2
        assert "rh@corp.com.br" in result
        assert "dev@tech.io" in result

    def test_extract_no_emails(self):
        assert extract_emails("Sem e-mail neste texto") == []

    def test_extract_empty_string(self):
        assert extract_emails("") == []

    def test_extract_deduplicates(self):
        text = "rh@empresa.com rh@empresa.com RH@empresa.com"
        assert len(extract_emails(text)) == 1

    def test_extract_complex_emails(self):
        text = "nome.sobrenome+tag@sub.domain.co.br"
        result = extract_emails(text)
        assert len(result) == 1


class TestIsGenericEmail:
    """Testes de detecção de e-mails genéricos."""

    def test_noreply_is_generic(self):
        assert is_generic_email("noreply@empresa.com")

    def test_naoresponda_is_generic(self):
        assert is_generic_email("naoresponda@site.com.br")

    def test_sac_is_generic(self):
        assert is_generic_email("sac@empresa.com.br")

    def test_normal_email_not_generic(self):
        assert not is_generic_email("joao.silva@empresa.com")

    def test_rh_not_generic(self):
        assert not is_generic_email("rh@empresa.com")


class TestValidateEmailFormat:
    """Testes de validação de formato de e-mail."""

    def test_valid_email(self):
        assert validate_email_format("user@domain.com")

    def test_invalid_email(self):
        assert not validate_email_format("not-an-email")

    def test_invalid_no_domain(self):
        assert not validate_email_format("user@")


class TestScoreEmailRelevance:
    """Testes de pontuação de relevância de e-mail."""

    def test_high_relevance_near_envie(self):
        text = "Interessados devem enviar currículo para rh@empresa.com"
        score = score_email_relevance("rh@empresa.com", text)
        assert score > 50

    def test_no_context_keywords(self):
        text = "Informações gerais em info@empresa.com sobre o produto"
        score = score_email_relevance("info@empresa.com", text)
        assert score == 50


class TestFilterValidEmails:
    """Testes do filtro completo de e-mails."""

    def test_filters_generic_emails(self):
        text = "Envie para rh@empresa.com. Não responda noreply@empresa.com"
        result = filter_valid_emails(text)
        assert "rh@empresa.com" in result
        assert "noreply@empresa.com" not in result

    def test_no_valid_emails(self):
        text = "Sem e-mail aqui"
        assert filter_valid_emails(text) == []

    def test_all_generic(self):
        text = "noreply@site.com sac@site.com"
        assert filter_valid_emails(text) == []

    def test_multiple_valid(self):
        text = "Envie currículo para rh@corp.com ou selecao@corp.com"
        result = filter_valid_emails(text)
        assert len(result) == 2

    def test_prioritizes_by_relevance(self):
        text = "Produto info@corp.com. Envie seu currículo para vagas@corp.com aqui"
        result = filter_valid_emails(text)
        assert len(result) == 2
        # Both emails are valid — vagas@ is near "envie currículo" keywords
        assert "vagas@corp.com" in result
        assert "info@corp.com" in result
