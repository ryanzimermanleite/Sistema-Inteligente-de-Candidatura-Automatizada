"""
Testes para funções utilitárias (helpers).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (
    compute_text_hash,
    format_salary,
    format_datetime,
    sanitize_text,
    score_color,
    score_emoji,
    truncate_text,
)
from datetime import datetime


class TestSanitizeText:
    """Testes de sanitização de texto."""

    def test_removes_html_tags(self):
        assert "Hello" in sanitize_text("<p>Hello</p>")
        assert "<p>" not in sanitize_text("<p>Hello</p>")

    def test_removes_script_tags(self):
        text = "Before<script>alert('xss')</script>After"
        result = sanitize_text(text)
        assert "alert" not in result
        assert "Before" in result
        assert "After" in result

    def test_normalizes_whitespace(self):
        text = "Hello   World"
        assert "  " not in sanitize_text(text)

    def test_empty_string(self):
        assert sanitize_text("") == ""
        assert sanitize_text(None) == ""


class TestTruncateText:
    """Testes de truncamento."""

    def test_short_text_unchanged(self):
        assert truncate_text("Short", 100) == "Short"

    def test_long_text_truncated(self):
        result = truncate_text("A" * 500, 100)
        assert len(result) <= 100
        assert result.endswith("...")


class TestFormatSalary:
    """Testes de formatação de salário."""

    def test_range(self):
        result = format_salary(3000, 5000)
        assert "3" in result
        assert "5" in result

    def test_only_min(self):
        result = format_salary(3000, None)
        assert "A partir" in result

    def test_only_max(self):
        result = format_salary(None, 5000)
        assert "Até" in result

    def test_text_fallback(self):
        assert format_salary(None, None, "A combinar") == "A combinar"

    def test_none(self):
        assert format_salary(None, None) == "Não informado"


class TestScoreColor:
    """Testes de cor por score."""

    def test_green(self):
        assert score_color(80) == "#22c55e"
        assert score_color(100) == "#22c55e"

    def test_yellow(self):
        assert score_color(60) == "#eab308"
        assert score_color(79) == "#eab308"

    def test_red(self):
        assert score_color(0) == "#ef4444"
        assert score_color(59) == "#ef4444"


class TestScoreEmoji:
    """Testes de emoji por score."""

    def test_green(self):
        assert score_emoji(80) == "🟢"

    def test_yellow(self):
        assert score_emoji(70) == "🟡"

    def test_red(self):
        assert score_emoji(30) == "🔴"


class TestComputeTextHash:
    """Testes de hash de texto."""

    def test_consistent(self):
        h1 = compute_text_hash("test")
        h2 = compute_text_hash("test")
        assert h1 == h2

    def test_different_input(self):
        h1 = compute_text_hash("test1")
        h2 = compute_text_hash("test2")
        assert h1 != h2
