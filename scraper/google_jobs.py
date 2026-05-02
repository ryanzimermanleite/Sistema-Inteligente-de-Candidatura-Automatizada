"""
Scraper dedicado para o Google Jobs (aba "Vagas de emprego" do Google).

Usa Playwright para navegar na interface JS do Google Jobs, scrollar para
carregar todas as vagas (infinite scroll), e extrair dados de cada card
usando os <template> tags que já contêm toda a informação.

FLUXO:
1. Navega para google.com/search?q=...&udm=8
2. Detecta CAPTCHA → espera resolução manual
3. Scrolla a lista para carregar todos os cards (infinite scroll)
4. Para cada card: clica → extrai dados do template → busca emails
5. Se não tem email → pula
6. Se tem email → extrai título, empresa, salário, descrição, emails
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from core.exceptions import ScraperBlockedError, ScraperError, ScraperTimeoutError
from core.models import JobListing, SearchFilters
from scraper.email_extractor import filter_valid_emails
from utils.anti_detection import (
    apply_stealth_scripts,
    get_random_user_agent,
    get_stealth_browser_args,
    random_delay,
)


# ============================================================
#  URL builder
# ============================================================

GOOGLE_JOBS_BASE = "https://www.google.com/search"


def build_google_jobs_url(query: str, location: str = "") -> str:
    """Constrói a URL do Google Jobs (udm=8)."""
    search_query = query
    if location:
        search_query += f" {location}"
    params = {"q": search_query, "udm": "8", "hl": "pt-BR"}
    return f"{GOOGLE_JOBS_BASE}?{urllib.parse.urlencode(params)}"


# ============================================================
#  Helpers de parsing
# ============================================================


def _parse_salary(text: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """Extrai salário de textos como 'R$ 3,5 mil a R$ 4,5 mil por mês'."""
    if not text:
        return None, None, None

    salary_text = text.strip()
    sal_min = sal_max = None

    # "R$ X,Y mil a R$ W,Z mil"
    m = re.search(r"R\$\s*([\d.,]+)\s*mil\s*(?:a|até|–|-)\s*R\$\s*([\d.,]+)\s*mil", salary_text, re.I)
    if m:
        try:
            sal_min = float(m.group(1).replace(".", "").replace(",", ".")) * 1000
            sal_max = float(m.group(2).replace(".", "").replace(",", ".")) * 1000
        except ValueError:
            pass
        return salary_text, sal_min, sal_max

    # "R$ X mil" único
    m = re.search(r"R\$\s*([\d.,]+)\s*mil", salary_text, re.I)
    if m:
        try:
            sal_min = float(m.group(1).replace(".", "").replace(",", ".")) * 1000
        except ValueError:
            pass
        return salary_text, sal_min, sal_max

    # "R$ X.XXX a R$ Y.YYY" ou "R$X.XXX,XX - R$Y.YYY,YY"
    m = re.search(r"R\$\s*([\d.,]+)\s*(?:a|até|–|-)\s*R\$\s*([\d.,]+)", salary_text, re.I)
    if m:
        try:
            sal_min = float(m.group(1).replace(".", "").replace(",", "."))
            sal_max = float(m.group(2).replace(".", "").replace(",", "."))
        except ValueError:
            pass
        return salary_text, sal_min, sal_max

    # "R$ X.XXX" único
    m = re.search(r"R\$\s*([\d.,]+)", salary_text, re.I)
    if m:
        try:
            sal_min = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
        return salary_text, sal_min, sal_max

    return salary_text, sal_min, sal_max


def _parse_posted_ago(text: str) -> Optional[datetime]:
    """Converte 'há 2 dias' → datetime."""
    if not text:
        return None
    t = text.lower().strip()
    for pattern, unit in [
        (r"há\s+(\d+)\s+dia", "days"),
        (r"há\s+(\d+)\s+hora", "hours"),
        (r"há\s+(\d+)\s+semana", "weeks"),
        (r"há\s+(\d+)\s+m[eê]s", "months"),
    ]:
        m = re.search(pattern, t)
        if m:
            val = int(m.group(1))
            if unit == "months":
                return datetime.utcnow() - timedelta(days=val * 30)
            return datetime.utcnow() - timedelta(**{unit: val})
    return None


def _extract_city_state(location: str) -> tuple[str, str]:
    """'Campinas, SP' → ('Campinas', 'SP')"""
    if not location:
        return "", ""
    m = re.match(r"^(.+?)[,\s-]+([A-Z]{2})\s*$", location.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return location.strip(), ""


def _detect_modality(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["remoto", "remote", "home office"]):
        return "remoto"
    if any(k in t for k in ["híbrido", "hibrido", "hybrid"]):
        return "hibrido"
    return "presencial"


# ============================================================
#  JavaScript — Seletores baseados no DOM real (Abril 2026)
# ============================================================

# Conta cards na lista (div.EimVGf é o container de cada vaga)
JS_COUNT_CARDS = """
() => {
    return document.querySelectorAll('div.EimVGf').length;
}
"""

# Clica no card pelo índice — usa o botão interno role="button"
JS_CLICK_CARD = """
(index) => {
    const cards = document.querySelectorAll('div.EimVGf');
    if (!cards[index]) return false;
    const card = cards[index];

    // Botão clicável principal dentro do card
    const btn = card.querySelector('div[role="button"][jscontroller="qodLAe"]');
    if (btn) {
        btn.scrollIntoView({behavior: 'instant', block: 'center'});
        btn.click();
        return true;
    }

    // Fallback: clica no card inteiro
    card.scrollIntoView({behavior: 'instant', block: 'center'});
    card.click();
    return true;
}
"""

# Clica em "Mostrar descrição completa" — seletor real: div[jsname="G7vtgf"].MmMIvd
JS_CLICK_SHOW_MORE = """
() => {
    const btns = document.querySelectorAll('div[jsname="G7vtgf"].MmMIvd');
    for (const btn of btns) {
        if (btn.offsetParent !== null && btn.offsetWidth > 0) {
            btn.click();
            return true;
        }
    }
    // Fallback: qualquer elemento com texto "Mostrar descrição completa"
    const all = document.querySelectorAll('[role="button"]');
    for (const el of all) {
        if (el.textContent.includes('Mostrar descrição completa') && el.offsetParent !== null) {
            el.click();
            return true;
        }
    }
    return false;
}
"""

# Scrolla a lista de cards para carregar mais (infinite scroll)
JS_SCROLL_CARD_LIST = """
() => {
    // Scrolla o container de cards para baixo
    const container = document.querySelector('div[data-id="jobs-detail-viewer"]');
    if (container) {
        const parent = container.parentElement;
        if (parent) {
            parent.scrollTop = parent.scrollHeight;
        }
    }

    // Também scrolla o scroll container da lista de vagas
    const scrollContainers = document.querySelectorAll('[jscontroller="cHmovd"]');
    for (const sc of scrollContainers) {
        sc.scrollTop = sc.scrollHeight;
        // Tenta scrollar o parent também
        if (sc.parentElement) sc.parentElement.scrollTop = sc.parentElement.scrollHeight;
    }

    // Fallback: scrolla qualquer container que contenha os cards
    const cards = document.querySelectorAll('div.EimVGf');
    if (cards.length > 0) {
        const lastCard = cards[cards.length - 1];
        lastCard.scrollIntoView({behavior: 'instant', block: 'end'});
    }

    // Verifica se chegou no fim
    const endMsg = document.querySelector('div[jsname="CLJY1d"]');
    const isEnd = endMsg && (endMsg.offsetParent !== null || endMsg.textContent.includes('Não há mais vagas'));

    return {
        count: cards.length,
        isEnd: !!isEnd
    };
}
"""

# Extrai dados de um card usando o <template> interno (contém TODOS os dados)
JS_EXTRACT_CARD_FROM_TEMPLATE = """
(index) => {
    const cards = document.querySelectorAll('div.EimVGf');
    if (!cards[index]) return null;
    const card = cards[index];

    // === DADOS DO CARD NA LISTA (preview) ===
    const titleEl = card.querySelector('.tNxQIb.PUpOsf');
    const title = titleEl ? titleEl.textContent.trim() : '';

    const companyEl = card.querySelector('.wHYlTd.MKCbgd.a3jPc');
    const company = companyEl ? companyEl.textContent.trim() : '';

    // Localização e fonte: "  Campinas, SP     •  via Indeed  "
    const locEl = card.querySelector('.wHYlTd.FqK3wc.MKCbgd');
    let locationText = '', source = '';
    if (locEl) {
        const fullText = locEl.textContent.trim();
        const parts = fullText.split('•').map(s => s.trim());
        if (parts[0]) locationText = parts[0];
        if (parts[1]) source = parts[1].replace(/^via\\s+/i, '').replace(/^no site\\s+/i, '').trim();
    }

    // Meta items: salário, tipo emprego, publicado (usam aria-label)
    let salary = '', employmentType = '', postedAgo = '';
    const metaItems = card.querySelectorAll('.Yf9oye');
    for (const item of metaItems) {
        const label = item.getAttribute('aria-label') || '';
        const text = item.textContent.trim();
        if (label.includes('Salário') || label.includes('salário')) {
            salary = text;
        } else if (label.includes('Tipo de emprego')) {
            employmentType = text;
        } else if (label.includes('Publicado')) {
            postedAgo = text;
        }
    }

    // === DADOS DO TEMPLATE (descrição completa + links) ===
    let description = '';
    const applyLinks = [];
    let docId = '';

    const template = card.querySelector('template');
    if (template && template.content) {
        const frag = template.content;

        // Descrição: parte visível + parte oculta (já está no HTML!)
        const visibleDesc = frag.querySelector('[jsname="QAWWu"]');
        const hiddenDesc = frag.querySelector('[jsname="ij8cu"]');
        const visibleText = visibleDesc ? visibleDesc.textContent.trim() : '';
        const hiddenText = hiddenDesc ? hiddenDesc.textContent.trim() : '';
        description = (visibleText + ' ' + hiddenText).trim();

        // Se não encontrou nos spans, tenta o container geral
        if (!description) {
            const descContainers = frag.querySelectorAll('.XFOJCe');
            for (const dc of descContainers) {
                const text = dc.textContent.trim();
                if (text.length > 50 && !text.includes('Escolha o elemento')) {
                    description = text.replace('Descrição do trabalho', '').trim();
                    break;
                }
            }
        }

        // Links de candidatura
        const links = frag.querySelectorAll('a.brKmxb');
        const seen = new Set();
        for (const link of links) {
            const href = link.getAttribute('href') || '';
            const linkTitle = link.getAttribute('title') || link.textContent.trim();
            if (href && href.startsWith('http') && !seen.has(href)) {
                seen.add(href);
                applyLinks.push({url: href, title: linkTitle.substring(0, 80)});
            }
        }

        // DocID
        const detailEl = frag.querySelector('[data-encoded-docid]');
        if (detailEl) {
            docId = detailEl.getAttribute('data-encoded-docid') || '';
        }

        // Salário do template (fallback)
        if (!salary) {
            const metaTags = frag.querySelectorAll('.fLsjxc');
            for (const tag of metaTags) {
                const t = tag.textContent.trim();
                if (t.includes('R$') || (t.includes('mil') && t.match(/\\d/))) {
                    salary = t;
                    break;
                }
            }
        }

        // Tipo emprego do template (fallback)
        if (!employmentType) {
            const metaTags = frag.querySelectorAll('.fLsjxc');
            for (const tag of metaTags) {
                const t = tag.textContent.trim();
                if (['Tempo integral', 'Meio período', 'Contrato', 'Estágio', 'CLT', 'PJ'].some(k => t.includes(k))) {
                    employmentType = t;
                    break;
                }
            }
        }

        // Posted do template (fallback)
        if (!postedAgo) {
            const metaTags = frag.querySelectorAll('.fLsjxc');
            for (const tag of metaTags) {
                const t = tag.textContent.trim();
                if (t.startsWith('há ') && t.length < 30) {
                    postedAgo = t;
                    break;
                }
            }
        }
    }

    return {
        title, company, location: locationText, source,
        salary, employmentType, postedAgo,
        description, applyLinks, docId,
    };
}
"""


# ============================================================
#  Função principal do scraper
# ============================================================


async def scrape_google_jobs(
    filters: SearchFilters,
    on_progress=None,
    cancel_event: Optional[asyncio.Event] = None,
    headless: bool = True,
    max_results: int = 50,
) -> list[JobListing]:
    """
    Scraping do Google Jobs com extração de emails.

    Fluxo:
    1. Navega para Google Jobs
    2. Detecta CAPTCHA → espera resolução manual
    3. Scrolla para carregar todos os cards (infinite scroll)
    4. Para cada card: clica → extrai dados do template → busca email
    5. Se tem email → coleta dados e adiciona à lista
    6. Se não tem → pula

    Returns:
        Lista de JobListing que possuem email de recrutador.
    """
    from playwright.async_api import async_playwright

    all_jobs: list[JobListing] = []
    discarded = 0

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=get_stealth_browser_args(),
            )
            context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            page = await context.new_page()
            await apply_stealth_scripts(page)

            # Monta URL
            location = ""
            if filters.city:
                location = filters.city
                if filters.state:
                    location += f", {filters.state}"
            elif filters.state:
                location = filters.state

            url = build_google_jobs_url(filters.query, location)
            logger.info(f"Google Jobs URL: {url}")

            if on_progress:
                on_progress("Abrindo Google Jobs...", 0, 0)

            # Navega
            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await random_delay(2.5, 4.0)
            except Exception as e:
                raise ScraperTimeoutError(f"Timeout ao carregar Google Jobs: {e}")

            # Verifica CAPTCHA
            content = await page.content()
            if "captcha" in content.lower() or "unusual traffic" in content.lower():
                if headless:
                    logger.error("CAPTCHA detectado e o navegador está oculto.")
                    raise ScraperBlockedError("Google bloqueou (CAPTCHA). Marque 'Exibir automação no navegador' e tente novamente para resolver manualmente.")

                logger.warning("Google solicitou CAPTCHA. Aguardando resolução manual...")
                if on_progress:
                    on_progress("🚨 CAPTCHA detectado! Resolva no navegador...", 0, 0)

                try:
                    # Espera até 5 minutos para o CAPTCHA sumir (usuário resolvendo manualmente)
                    # NÃO recarrega a página — apenas espera a página mudar sozinha
                    await page.wait_for_function(
                        """() => {
                            const body = document.body.innerHTML.toLowerCase();
                            return !body.includes('captcha') && !body.includes('unusual traffic');
                        }""",
                        timeout=300000,
                        polling=2000,
                    )
                    logger.info("CAPTCHA resolvido! Aguardando cards carregarem...")
                    if on_progress:
                        on_progress("✅ CAPTCHA resolvido! Aguardando vagas carregarem...", 0, 0)

                    # Espera generosa para os cards de vagas renderizarem após CAPTCHA
                    await asyncio.sleep(5)

                    # Agora espera os cards de vagas aparecerem (até 30s extras)
                    try:
                        await page.wait_for_selector(
                            'div.EimVGf',
                            timeout=30000,
                        )
                    except Exception:
                        # Se ainda não apareceu, espera mais um pouco
                        logger.warning("Cards não apareceram ainda, aguardando mais...")
                        await asyncio.sleep(5)

                    await random_delay(3.0, 5.0)
                    logger.info("Pronto para iniciar scraping dos cards.")
                except Exception:
                    raise ScraperBlockedError("Tempo esgotado para resolver o CAPTCHA (5 minutos).")

            # Espera os cards aparecerem
            try:
                await page.wait_for_selector('div.EimVGf', timeout=15000)
            except Exception:
                logger.warning("Seletor div.EimVGf não encontrado, aguardando...")
                await asyncio.sleep(3)

            # === INFINITE SCROLL: carrega todos os cards ===
            if on_progress:
                on_progress("Carregando todas as vagas (scroll)...", 0, 0)

            prev_count = 0
            stale_rounds = 0
            max_stale = 5  # Para de scrollar após 5 tentativas sem novos cards

            for scroll_round in range(30):  # Máximo 30 scrolls
                if cancel_event and cancel_event.is_set():
                    break

                result = await page.evaluate(JS_SCROLL_CARD_LIST)
                current_count = result.get("count", 0)
                is_end = result.get("isEnd", False)

                if on_progress:
                    on_progress(f"Carregando vagas... ({current_count} encontradas)", 0, 0)

                if is_end:
                    logger.info(f"Fim da lista alcançado: {current_count} cards")
                    break

                if current_count == prev_count:
                    stale_rounds += 1
                    if stale_rounds >= max_stale:
                        logger.info(f"Sem novos cards após {max_stale} tentativas: {current_count} cards")
                        break
                else:
                    stale_rounds = 0

                prev_count = current_count
                await asyncio.sleep(1.5)  # Espera cards carregarem

            # Conta cards finais
            card_count = await page.evaluate(JS_COUNT_CARDS)
            if not card_count:
                logger.warning("Nenhuma vaga encontrada no Google Jobs")
                if on_progress:
                    on_progress("Nenhuma vaga encontrada", 0, 0)
                await browser.close()
                return []

            logger.info(f"Google Jobs: {card_count} cards encontrados no total")
            if on_progress:
                on_progress(f"{card_count} vagas encontradas, analisando...", 0, card_count)

            # === PERCORRE CADA CARD ===
            for i in range(min(card_count, max_results)):
                if cancel_event and cancel_event.is_set():
                    break

                try:
                    # Clica no card (para UX — o usuário vê a seleção)
                    clicked = await page.evaluate(JS_CLICK_CARD, i)
                    if not clicked:
                        continue
                    await asyncio.sleep(0.5)  # Breve pausa para renderizar

                    # Extrai dados direto do template (rápido, sem esperar)
                    data = await page.evaluate(JS_EXTRACT_CARD_FROM_TEMPLATE, i)
                    if not data or not data.get("title"):
                        continue

                    title = data["title"]
                    description = data.get("description", "")
                    company = data.get("company", "")

                    # BUSCA EMAIL NA DESCRIÇÃO
                    emails = filter_valid_emails(description)

                    if not emails:
                        discarded += 1
                        logger.debug(f"Sem email — pulando: {title}")
                        if on_progress:
                            on_progress(
                                f"Card {i+1}/{card_count}: sem email ({len(all_jobs)} com email)",
                                i + 1, card_count,
                            )
                        continue

                    # TEM EMAIL! Extrai tudo
                    logger.info(f"✅ Email encontrado em: {title} → {emails}")

                    location_text = data.get("location", "")
                    city, state = _extract_city_state(location_text)

                    salary_text, sal_min, sal_max = _parse_salary(data.get("salary", ""))
                    posted_at = _parse_posted_ago(data.get("postedAgo", ""))
                    employment_type = data.get("employmentType", "")
                    modality = _detect_modality(description + " " + title)

                    # URL principal
                    apply_links = data.get("applyLinks", [])
                    job_url = apply_links[0]["url"] if apply_links else url

                    # Monta descrição enriquecida
                    desc_parts = [description]
                    if employment_type:
                        desc_parts.append(f"\nTipo: {employment_type}")
                    if apply_links:
                        desc_parts.append("\n📋 Links de candidatura:")
                        for link in apply_links:
                            desc_parts.append(f"  • {link.get('title', 'Candidatar')}: {link['url']}")

                    doc_id = data.get("docId", "")
                    ext_id = f"google_jobs_{doc_id}" if doc_id else f"google_jobs_{hash(title + company)}"

                    job = JobListing(
                        external_id=ext_id,
                        title=title,
                        company=company,
                        city=city,
                        state=state or filters.state,
                        modality=modality,
                        salary_text=salary_text,
                        salary_min=sal_min,
                        salary_max=sal_max,
                        description="\n".join(desc_parts),
                        contact_emails=emails,
                        posted_at=posted_at,
                        url=job_url,
                    )
                    all_jobs.append(job)

                    if on_progress:
                        on_progress(
                            f"Card {i+1}/{card_count}: ✅ {title[:40]}... ({len(all_jobs)} com email)",
                            i + 1, card_count,
                        )

                except Exception as e:
                    logger.debug(f"Erro no card {i}: {e}")
                    continue

            await browser.close()

    except (ScraperBlockedError, ScraperTimeoutError):
        raise
    except Exception as e:
        logger.error(f"Erro fatal no Google Jobs: {e}")
        raise ScraperError(f"Erro no Google Jobs: {e}") from e

    logger.info(
        f"Google Jobs concluído: {len(all_jobs)} com email, "
        f"{discarded} descartadas (sem email)"
    )
    return all_jobs
