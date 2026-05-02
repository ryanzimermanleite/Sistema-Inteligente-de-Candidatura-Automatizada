"""
Funções utilitárias diversas.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import datetime
from typing import Optional


def compute_file_hash(file_path: str) -> str:
    """
    Calcula o hash SHA-256 de um arquivo.

    Args:
        file_path: Caminho do arquivo.

    Returns:
        Hash SHA-256 em hexadecimal.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_text_hash(text: str) -> str:
    """
    Calcula o hash SHA-256 de um texto.

    Args:
        text: Texto para calcular o hash.

    Returns:
        Hash SHA-256 em hexadecimal.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_text(text: str) -> str:
    """
    Sanitiza texto removendo caracteres invisíveis e potencialmente perigosos.

    Args:
        text: Texto bruto.

    Returns:
        Texto sanitizado.
    """
    if not text:
        return ""

    # Remove caracteres de controle (exceto newline, tab)
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t", "\r") or not unicodedata.category(ch).startswith("C")
    )

    # Remove tags de script e style
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove tags HTML restantes
    text = re.sub(r"<[^>]+>", " ", text)

    # Normaliza espaços
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def truncate_text(text: str, max_length: int = 300) -> str:
    """
    Trunca texto com reticências.

    Args:
        text: Texto a truncar.
        max_length: Comprimento máximo.

    Returns:
        Texto truncado.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rsplit(" ", 1)[0] + "..."


def format_salary(salary_min: Optional[float], salary_max: Optional[float], salary_text: Optional[str] = None) -> str:
    """
    Formata faixa salarial para exibição.

    Args:
        salary_min: Salário mínimo.
        salary_max: Salário máximo.
        salary_text: Texto de salário original.

    Returns:
        Texto formatado do salário.
    """
    if salary_min and salary_max:
        return f"R$ {salary_min:,.0f} – R$ {salary_max:,.0f}"
    elif salary_min:
        return f"A partir de R$ {salary_min:,.0f}"
    elif salary_max:
        return f"Até R$ {salary_max:,.0f}"
    elif salary_text:
        return salary_text
    return "Não informado"


def format_datetime(dt: Optional[datetime]) -> str:
    """
    Formata datetime para exibição brasileira.

    Args:
        dt: Data/hora.

    Returns:
        String formatada DD/MM/YYYY HH:MM.
    """
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


def format_date(dt: Optional[datetime]) -> str:
    """
    Formata data para exibição brasileira.

    Args:
        dt: Data.

    Returns:
        String formatada DD/MM/YYYY.
    """
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y")


def get_file_size_mb(file_path: str) -> float:
    """
    Retorna o tamanho do arquivo em MB.

    Args:
        file_path: Caminho do arquivo.

    Returns:
        Tamanho em MB.
    """
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


def score_color(score: int) -> str:
    """
    Retorna a cor para um score de match.

    Args:
        score: Score de 0 a 100.

    Returns:
        Cor em hex.
    """
    if score >= 80:
        return "#22c55e"  # Verde
    elif score >= 60:
        return "#eab308"  # Amarelo
    else:
        return "#ef4444"  # Vermelho


def score_emoji(score: int) -> str:
    """
    Retorna o emoji para um score de match.

    Args:
        score: Score de 0 a 100.

    Returns:
        Emoji correspondente.
    """
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    else:
        return "🔴"


def _normalize_title(title: str) -> str:
    """Normaliza título para comparação de duplicatas."""
    t = title.lower().strip()
    # Remove acentos
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    # Remove pontuação e espaços extras
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Remove sufixos de contagem "1 vagas", "2 vagas" etc.
    t = re.sub(r"\d+\s*vagas?$", "", t).strip()
    # Normaliza variantes comuns de palavras
    synonyms = {
        "estagiario": "estagio",
        "programador": "programacao",
        "desenvolvedor": "desenvolvimento",
        "analista": "analise",
        "instrutor": "instrucao",
        "professor": "ensino",
        "senior": "sr",
        "junior": "jr",
    }
    words = t.split()
    words = [synonyms.get(w, w) for w in words]
    return " ".join(words)


def deduplicate_jobs(jobs: list) -> list:
    """
    Remove vagas duplicadas usando múltiplos critérios:
    1. URL idêntica
    2. Título + Empresa + Email iguais (fingerprint)
    3. Título normalizado muito similar com mesmo email

    Args:
        jobs: Lista de JobListing.

    Returns:
        Lista sem duplicatas, preservando a primeira ocorrência.
    """
    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    seen_title_email: set[str] = set()
    unique: list = []

    for job in jobs:
        # Critério 1: URL idêntica
        if job.url and job.url in seen_urls:
            continue

        # Critério 2: Fingerprint título + empresa + email
        emails_str = ",".join(sorted(job.contact_emails)) if job.contact_emails else ""
        fingerprint = f"{job.title.lower().strip()}|{job.company.lower().strip()}|{emails_str}"
        if fingerprint in seen_fingerprints:
            continue

        # Critério 3: Título normalizado + mesmo email
        norm_title = _normalize_title(job.title)
        title_email_key = f"{norm_title}|{emails_str}"
        if title_email_key in seen_title_email:
            continue

        # Não é duplicata
        if job.url:
            seen_urls.add(job.url)
        seen_fingerprints.add(fingerprint)
        seen_title_email.add(title_email_key)
        unique.append(job)

    return unique
