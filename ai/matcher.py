"""
Matcher de vagas — faz o match entre perfil e vaga usando IA.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from loguru import logger

from ai.client import get_ai_client
from ai.schemas import MATCH_SCHEMA, CV_ANALYSIS_SCHEMA
from config.prompts import MATCHER_SYSTEM, MATCHER_USER, CV_ANALYSIS_SYSTEM, CV_ANALYSIS_USER, COVER_LETTER_SYSTEM, COVER_LETTER_USER
from core.models import JobListing, MatchResult, ResumeProfile
from utils.helpers import format_salary


async def match_job(
    profile: ResumeProfile,
    job: JobListing,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> MatchResult:
    """
    Faz o match entre um perfil e uma vaga usando IA.

    Args:
        profile: Perfil do candidato.
        job: Vaga a analisar.
        semaphore: Semáforo para controlar paralelismo.

    Returns:
        MatchResult com o resultado da análise.
    """
    async def _do_match() -> MatchResult:
        client = get_ai_client()

        perfil_dict = {
            "nome": profile.nome,
            "resumo_profissional": profile.resumo_profissional,
            "skills_tecnicas": profile.skills_tecnicas,
            "skills_comportamentais": profile.skills_comportamentais,
            "anos_experiencia": profile.anos_experiencia,
            "ultimo_cargo": profile.ultimo_cargo,
            "cidade": profile.cidade,
            "formacao": profile.formacao,
            "idiomas": profile.idiomas,
            "certificacoes": profile.certificacoes,
            "experiencias_resumidas": profile.experiencias_resumidas,
        }

        prompt = MATCHER_USER.format(
            perfil_json=json.dumps(perfil_dict, ensure_ascii=False, indent=2),
            vaga_titulo=job.title,
            empresa=job.company,
            cidade=job.city,
            estado=job.state,
            modalidade=job.modality,
            salario=format_salary(job.salary_min, job.salary_max, job.salary_text),
            descricao_vaga=job.description[:4000],
        )

        result = await client.chat_completion(
            system_prompt=MATCHER_SYSTEM,
            user_prompt=prompt,
            response_schema=MATCH_SCHEMA,
            call_type="match",
        )

        requisitos_raw = result.get("requisitos", [])

        # === DEBUG LOGGING COMPLETO PARA TODAS AS VAGAS ===
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 MATCH DEBUG: {job.title} @ {job.company}")
        logger.info(f"{'='*60}")
        logger.info(f"")
        logger.info(f"📄 SKILLS DO CURRÍCULO ({len(profile.skills_tecnicas)} itens):")
        for s in profile.skills_tecnicas:
            logger.info(f"  ● {s}")
        logger.info(f"")
        logger.info(f"📄 EXPERIÊNCIAS RESUMIDAS DO CURRÍCULO ({len(profile.experiencias_resumidas)} itens):")
        for e in profile.experiencias_resumidas:
            logger.info(f"  ● {e}")
        logger.info(f"")
        logger.info(f"📄 FORMAÇÃO DO CURRÍCULO: {profile.formacao}")
        logger.info(f"📄 CERTIFICAÇÕES: {profile.certificacoes}")
        logger.info(f"📄 ÚLTIMO CARGO: {profile.ultimo_cargo}")
        logger.info(f"📄 ANOS EXPERIÊNCIA: {profile.anos_experiencia}")
        logger.info(f"")
        logger.info(f"📋 REQUISITOS QUE A IA EXTRAIU DA VAGA ({len(requisitos_raw)} itens):")
        for r in requisitos_raw:
            status = "✅" if r.get("possui") else "❌"
            logger.info(f"  {status} {r.get('nome')} — possui: {r.get('possui')}")
        logger.info(f"")
        logger.info(f"📝 SCORE DA IA (antes do pós-processamento): {result.get('score')}")
        logger.info(f"📝 JUSTIFICATIVA DA IA: {result.get('justificativa', '')}")
        logger.info(f"")
        logger.info(f"📜 DESCRIÇÃO DA VAGA (primeiros 2000 chars):")
        logger.info(f"{job.description[:2000]}")
        logger.info(f"{'='*60}")

        # === POST-PROCESSING: Validate requisitos against job description ===
        desc_lower = job.description.lower().strip()

        # Se a descrição está vazia, confia no resultado da IA sem filtrar
        if not desc_lower or len(desc_lower) < 50:
            logger.info(f"\n⚠️ DESCRIÇÃO VAZIA/CURTA — Pulando pós-processamento, usando resultado direto da IA")
            requisitos = requisitos_raw
            if requisitos:
                matched = sum(1 for r in requisitos if r.get("possui", False))
                score = round((matched / len(requisitos)) * 100)
            else:
                score = 0
        else:
            requisitos = []
            removidos = []
            logger.info(f"\n🔎 PÓS-PROCESSAMENTO: Validando requisitos contra descrição da vaga...")
            for r in requisitos_raw:
                nome = r.get("nome", "")
                nome_lower = nome.lower()
                # Try exact match
                if nome_lower in desc_lower:
                    requisitos.append(r)
                    logger.info(f"  ✅ ACEITO '{nome}' (exact match) possui={r.get('possui')}")
                else:
                    # Try individual words for multi-word requirements
                    words = nome_lower.split()
                    if any(w in desc_lower for w in words if len(w) > 2):
                        requisitos.append(r)
                        logger.info(f"  ✅ ACEITO '{nome}' (partial match) possui={r.get('possui')}")
                    else:
                        removidos.append(nome)
                        logger.info(f"  🚫 REMOVIDO '{nome}' — NÃO encontrado na descrição da vaga")

            # Recalculate score based on validated requisitos
            if requisitos:
                matched = sum(1 for r in requisitos if r.get("possui", False))
                score = round((matched / len(requisitos)) * 100)
            else:
                score = 0

            logger.info(f"  Requisitos removidos: {len(removidos)} → {removidos}")

        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"📊 RESULTADO FINAL: {job.title}")
        logger.info(f"  Requisitos da IA (raw): {len(requisitos_raw)}")
        logger.info(f"  Requisitos finais: {len(requisitos)}")
        logger.info(f"  Possui: {sum(1 for r in requisitos if r.get('possui', False))} / {len(requisitos)}")
        logger.info(f"  ⭐ SCORE FINAL: {score}%")
        logger.info(f"{'='*60}\n")

        lacunas = [r["nome"] for r in requisitos if not r.get("possui", False)]

        return MatchResult(
            score=max(0, min(100, score)),
            requisitos=requisitos,
            lacunas=lacunas,
            pontos_fortes=[r["nome"] for r in requisitos if r.get("possui", False)],
            deve_aplicar=result.get("deve_aplicar", False),
            justificativa=result.get("justificativa", ""),
            email_personalizado=result.get("email_personalizado", ""),
        )

    if semaphore:
        async with semaphore:
            return await _do_match()
    return await _do_match()


async def match_jobs_batch(
    profile: ResumeProfile,
    jobs: list[JobListing],
    max_concurrent: int = 5,
    on_result=None,
    cancel_event: Optional[asyncio.Event] = None,
) -> list[tuple[JobListing, MatchResult]]:
    """
    Processa múltiplas vagas em paralelo.

    Args:
        profile: Perfil do candidato.
        jobs: Lista de vagas.
        max_concurrent: Máximo de chamadas simultâneas.
        on_result: Callback(job, match_result, index) chamado a cada resultado.
        cancel_event: Evento para cancelar o processamento.

    Returns:
        Lista de tuplas (job, match_result).
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[tuple[JobListing, MatchResult]] = []

    async def process_one(job: JobListing, index: int):
        if cancel_event and cancel_event.is_set():
            return
        try:
            logger.info(f"Analisando vaga {index + 1}/{len(jobs)}: \"{job.title}\" @ {job.company}")
            match = await match_job(profile, job, semaphore)
            results.append((job, match))
            if on_result:
                on_result(job, match, index)
            logger.info(f"Vaga {index + 1}: \"{job.title}\" — Score {match.score}%")
        except Exception as e:
            logger.error(f"Erro ao analisar vaga \"{job.title}\": {e}")

    tasks = [process_one(job, i) for i, job in enumerate(jobs)]
    await asyncio.gather(*tasks, return_exceptions=True)

    return results


async def generate_cover_letter(profile: ResumeProfile, job: JobListing) -> str:
    """Gera carta de apresentação personalizada."""
    client = get_ai_client()
    perfil_dict = {
        "nome": profile.nome,
        "resumo_profissional": profile.resumo_profissional,
        "skills_tecnicas": profile.skills_tecnicas,
        "anos_experiencia": profile.anos_experiencia,
        "ultimo_cargo": profile.ultimo_cargo,
        "formacao": profile.formacao,
    }
    prompt = COVER_LETTER_USER.format(
        perfil_json=json.dumps(perfil_dict, ensure_ascii=False, indent=2),
        vaga_titulo=job.title,
        empresa=job.company,
        descricao_vaga=job.description[:3000],
    )
    result = await client.chat_completion(
        system_prompt=COVER_LETTER_SYSTEM,
        user_prompt=prompt,
        call_type="cover_letter",
    )
    return result.get("carta", result.get("content", str(result)))


async def analyze_cv_gaps(
    profile: ResumeProfile,
    jobs_with_matches: list[tuple[JobListing, MatchResult]],
) -> dict:
    """Analisa lacunas do CV com base nas vagas analisadas."""
    from collections import Counter

    all_descriptions = " ".join(j.description for j, _ in jobs_with_matches)
    skills_counter = Counter()
    for job, _ in jobs_with_matches:
        desc_lower = job.description.lower()
        for word in desc_lower.split():
            if len(word) > 3:
                skills_counter[word] += 1

    sorted_matches = sorted(jobs_with_matches, key=lambda x: x[1].score, reverse=True)
    top_5 = [(j.title, j.company, m.score) for j, m in sorted_matches[:5]]
    bottom_5 = [(j.title, j.company, m.score) for j, m in sorted_matches[-5:]]

    client = get_ai_client()
    prompt = CV_ANALYSIS_USER.format(
        total_vagas=len(jobs_with_matches),
        perfil_json=json.dumps({"nome": profile.nome, "skills_tecnicas": profile.skills_tecnicas, "anos_experiencia": profile.anos_experiencia}, ensure_ascii=False),
        skills_demandadas=json.dumps(dict(skills_counter.most_common(30)), ensure_ascii=False),
        top_vagas=json.dumps(top_5, ensure_ascii=False),
        bottom_vagas=json.dumps(bottom_5, ensure_ascii=False),
    )
    return await client.chat_completion(
        system_prompt=CV_ANALYSIS_SYSTEM,
        user_prompt=prompt,
        response_schema=CV_ANALYSIS_SCHEMA,
        call_type="cv_analysis",
    )
