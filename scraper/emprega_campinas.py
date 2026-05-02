"""
Scraper dedicado para o portal Emprega Campinas.

Usa Playwright para navegar e BeautifulSoup para parsear HTML.
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from core.database import JobRecord, PageCache, get_session
from core.exceptions import ScraperBlockedError, ScraperError, ScraperTimeoutError
from core.models import JobListing, SearchFilters
from scraper.email_extractor import filter_valid_emails
from utils.anti_detection import (
    apply_stealth_scripts,
    get_random_user_agent,
    get_stealth_browser_args,
    random_delay,
)

BASE_URL = "https://empregacampinas.com.br"


def build_search_url(query: str, page: int = 1) -> str:
    """Constrói a URL de busca no Emprega Campinas (WordPress)."""
    encoded = urllib.parse.quote_plus(query)
    if page <= 1:
        return f"{BASE_URL}/?s={encoded}"
    return f"{BASE_URL}/page/{page}/?s={encoded}"


def get_cached_page(url: str, max_age_hours: int = 6) -> Optional[str]:
    """Busca HTML em cache se não expirado."""
    try:
        session = get_session()
        record = session.query(PageCache).filter_by(url=url).first()
        session.close()
        if record and record.fetched_at:
            age = datetime.utcnow() - record.fetched_at
            if age < timedelta(hours=max_age_hours):
                logger.debug(f"Cache hit: {url}")
                return record.html
    except Exception as e:
        logger.warning(f"Erro ao buscar cache: {e}")
    return None


def save_page_cache(url: str, html: str) -> None:
    """Salva HTML no cache."""
    try:
        session = get_session()
        existing = session.query(PageCache).filter_by(url=url).first()
        if existing:
            existing.html = html
            existing.fetched_at = datetime.utcnow()
        else:
            session.add(PageCache(url=url, html=html, fetched_at=datetime.utcnow()))
        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"Erro ao salvar cache: {e}")


def parse_job_listing_page(html: str) -> list[dict]:
    """
    Parseia a página de listagem de vagas do Emprega Campinas (WordPress).

    Estrutura real do site:
    - Cada vaga é um <a class="thumbnail"> dentro de <div class="col-lg-12">
    - Título em <h2>, código em <span class="cod-vaga">
    - Descrição em <p class="descricao-vaga">
    - Data em <span class="time">

    Returns:
        Lista de dicts com {url, title, company, city, posted_text}.
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    # Busca o container principal do artigo
    article = soup.find("article", id="article") or soup

    # Seletor principal: links com classe "thumbnail" dentro do artigo
    job_links = article.select("a.thumbnail")

    if not job_links:
        # Fallback: busca links dentro de div.col-lg-12 que apontem para vagas
        job_links = article.select("div.col-lg-12 > a[href]")

    if not job_links:
        # Fallback final: qualquer link com href que pareça ser uma vaga
        job_links = [a for a in article.find_all("a", href=True)
                     if a.get("href", "").startswith(BASE_URL + "/")
                     and "vaga" in a.get("href", "").lower()
                     or a.find("h2")]

    for link_el in job_links:
        try:
            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href

            # Ignora links que não são de vagas (navegação, banners, etc.)
            if any(x in href for x in ["/categoria/", "/faq/", "/feed/", "/page/",
                                        "membros.", "facebook.", "twitter.",
                                        "linkedin.", "youtube."]):
                continue

            # Extrai título do <h2>
            title_el = link_el.find("h2")
            if not title_el:
                continue  # Sem h2 = provavelmente não é um card de vaga

            # Remove o código da vaga do título
            cod_el = title_el.find("span", class_="cod-vaga")
            cod_vaga = cod_el.get_text(strip=True) if cod_el else ""
            if cod_el:
                cod_el.decompose()
            title = title_el.get_text(strip=True)

            # Extrai descrição prévia
            desc_el = link_el.find("p", class_="descricao-vaga")
            description = desc_el.get_text(strip=True) if desc_el else ""

            # Extrai data/hora da publicação
            time_el = link_el.find("span", class_="time")
            posted_text = time_el.get_text(strip=True) if time_el else ""

            # Tenta extrair cidade do título (formato: CARGO / CIDADE / N VAGA(S))
            city = ""
            company = ""
            title_parts = title.split("/")
            if len(title_parts) >= 2:
                city = title_parts[-2].strip()

            # Tenta extrair empresa da descrição prévia
            if description:
                emp_match = re.match(r"^(.+?)\s+está com \d+ vaga", description)
                if emp_match:
                    company = emp_match.group(1).strip()

            jobs.append({
                "url": href,
                "title": title,
                "company": company,
                "city": city,
                "cod_vaga": cod_vaga,
                "posted_text": posted_text,
            })
        except Exception as e:
            logger.debug(f"Erro ao parsear item de vaga: {e}")
            continue

    logger.debug(f"parse_job_listing_page: {len(jobs)} vagas encontradas")
    return jobs


def has_next_page(html: str) -> bool:
    """Verifica se existe próxima página na paginação WordPress."""
    soup = BeautifulSoup(html, "lxml")
    pagenavi = soup.find("div", class_="wp-pagenavi")
    if pagenavi:
        next_link = pagenavi.find("a", class_="nextpostslink")
        return next_link is not None
    return False


def parse_job_detail_page(html: str, url: str) -> Optional[JobListing]:
    """Parseia a página de detalhe de uma vaga (WordPress Emprega Campinas)."""
    soup = BeautifulSoup(html, "lxml")

    try:
        # Container principal
        article = soup.find("article", id="article") or soup

        # Título — sempre no <h1> dentro de #article
        title_el = article.find("h1")
        title = title_el.get_text(strip=True) if title_el else "Sem título"
        # Remove prefixo comum do site
        title = re.sub(r"^(VAGA\s+DE\s+)", "", title, flags=re.I).strip()

        # Descrição — no WordPress desse tema, o conteúdo da vaga fica
        # dentro de .entry-content, .post-content, ou diretamente no article
        # após o h1 e os banners
        desc_el = (
            article.find("div", class_="postie-post")
            or article.find(class_=re.compile(r"entry-content|post-content|single-content", re.I))
            or article.find("div", class_="thumbnail")
        )
        if not desc_el:
            desc_el = article

        description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

        # Extrair seções do texto da descrição
        desc_text = description

        # Empresa — tenta extrair do texto (formato: "EMPRESA está com N vaga(s)")
        company = ""
        emp_match = re.search(r"^(.+?)\s+está com \d+ vaga", desc_text, re.MULTILINE)
        if emp_match:
            company = emp_match.group(1).strip()

        # Requisitos — busca no texto
        requirements = None
        req_match = re.search(r"Requisitos?:\s*(.+?)(?=Salário:|Benefícios?:|ATENÇÃO:|Observações?:|$)",
                              desc_text, re.DOTALL | re.I)
        if req_match:
            requirements = req_match.group(1).strip()

        # Benefícios — busca no texto
        benefits = None
        ben_match = re.search(r"Benefícios?:\s*(.+?)(?=ATENÇÃO:|Observações?:|$)",
                              desc_text, re.DOTALL | re.I)
        if ben_match:
            benefits = ben_match.group(1).strip()

        # Salário — busca no texto
        salary_text = None
        salary_min = None
        salary_max = None
        sal_match = re.search(r"Salário:\s*(.+?)(?=\n|Benefícios?:|ATENÇÃO:|$)",
                              desc_text, re.I)
        if sal_match:
            salary_text = sal_match.group(1).strip()

        # Tenta extrair valor numérico do salário
        if salary_text:
            val_match = re.search(
                r"R\$\s*([\d.,]+)(?:\s*(?:a|até|à|–|-)\s*R\$\s*([\d.,]+))?",
                salary_text,
            )
            if val_match:
                try:
                    salary_min = float(val_match.group(1).replace(".", "").replace(",", "."))
                    if val_match.group(2):
                        salary_max = float(val_match.group(2).replace(".", "").replace(",", "."))
                except ValueError:
                    pass

        # Localização — extrai do título (formato: CARGO / CIDADE / N VAGA(S))
        city = ""
        state = "SP"
        title_parts = title.split("/")
        if len(title_parts) >= 2:
            city_candidate = title_parts[-2].strip()
            # Verifica se não é número de vagas
            if not re.match(r"^\d+", city_candidate):
                city = city_candidate
                # Tenta separar estado se houver (ex: "SUMARÉ/SP")
                if "/" in city or "-" in city:
                    city_parts = re.split(r"[/-]", city)
                    city = city_parts[0].strip()
                    if len(city_parts) > 1 and len(city_parts[-1].strip()) == 2:
                        state = city_parts[-1].strip().upper()

        # Modalidade
        modality = "presencial"
        desc_lower = desc_text.lower()
        if "home office" in desc_lower or "remoto" in desc_lower or "remote" in desc_lower:
            modality = "remoto"
        elif "híbrido" in desc_lower or "hibrido" in desc_lower or "hybrid" in desc_lower:
            modality = "hibrido"

        # Data de publicação
        posted_at = None
        date_el = article.find("span", class_="time")
        if date_el:
            date_text = date_el.get_text(strip=True)
            date_match = re.search(r"(\d{2})\s*/\s*(\d{2})", date_text)
            if date_match:
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = datetime.utcnow().year
                try:
                    posted_at = datetime(year, month, day)
                except ValueError:
                    pass

        # External ID — slug da URL
        external_id = url.rstrip("/").split("/")[-1]

        # E-mails — busca no HTML completo do artigo
        full_text = article.get_text(separator=" ", strip=True)
        # Também busca em href="mailto:..."
        mailto_links = article.find_all("a", href=re.compile(r"mailto:", re.I))
        email_text = full_text
        for ml in mailto_links:
            email_text += " " + ml.get("href", "").replace("mailto:", "")

        contact_emails = filter_valid_emails(email_text)

        return JobListing(
            external_id=external_id,
            title=title,
            company=company,
            city=city,
            state=state,
            modality=modality,
            salary_text=salary_text,
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            requirements=requirements,
            benefits=benefits,
            contact_emails=contact_emails,
            posted_at=posted_at,
            url=url,
        )
    except Exception as e:
        logger.error(f"Erro ao parsear detalhe da vaga: {e}")
        return None


async def scrape_jobs(
    filters: SearchFilters,
    on_progress=None,
    cancel_event: Optional[asyncio.Event] = None,
    headless: bool = True,
) -> list[JobListing]:
    """
    Executa o scraping completo no Emprega Campinas.

    Args:
        filters: Filtros de busca.
        on_progress: Callback(message, current, total).
        cancel_event: Evento para cancelar.
        headless: Se True, roda o browser sem interface.

    Returns:
        Lista de JobListing com e-mail válido.
    """
    from playwright.async_api import async_playwright

    all_jobs: list[JobListing] = []
    total_raw = 0
    discarded_no_email = 0

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
            )
            page = await context.new_page()
            await apply_stealth_scripts(page)

            page_num = 1
            job_urls_seen = set()

            while True:
                if cancel_event and cancel_event.is_set():
                    logger.info("Scraping cancelado pelo usuário")
                    break

                url = build_search_url(filters.query, page_num)
                if on_progress:
                    on_progress(f"Buscando página {page_num}... ({len(all_jobs)} vagas com e-mail)", len(all_jobs), 0)

                # Tenta cache primeiro
                html = get_cached_page(url)
                if not html:
                    for attempt in range(3):
                        try:
                            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                            await random_delay(1.5, 3.0)
                            html = await page.content()
                            save_page_cache(url, html)
                            break
                        except Exception as e:
                            wait = 2 ** (attempt + 1)
                            logger.warning(f"Erro na página {page_num} (tentativa {attempt+1}): {e}. Retry em {wait}s")
                            await asyncio.sleep(wait)
                    else:
                        logger.error(f"Falha ao carregar página {page_num} após 3 tentativas")
                        break

                if not html:
                    break

                # Parseia listagem
                listings = parse_job_listing_page(html)
                if not listings:
                    logger.info(f"Nenhuma vaga na página {page_num} — fim da paginação")
                    break

                logger.info(f"Página {page_num}: {len(listings)} vagas encontradas")

                # Verifica se existe próxima página (paginação WordPress)
                next_page_exists = has_next_page(html)

                for listing in listings:
                    if cancel_event and cancel_event.is_set():
                        break
                    if listing["url"] in job_urls_seen:
                        continue
                    job_urls_seen.add(listing["url"])
                    total_raw += 1

                    # Carrega detalhe da vaga
                    detail_html = get_cached_page(listing["url"])
                    if not detail_html:
                        for attempt in range(3):
                            try:
                                await page.goto(listing["url"], timeout=30000, wait_until="domcontentloaded")
                                await random_delay(1.5, 3.5)
                                detail_html = await page.content()
                                save_page_cache(listing["url"], detail_html)
                                break
                            except Exception as e:
                                if attempt < 2:
                                    await asyncio.sleep(2 ** (attempt + 1))
                                else:
                                    logger.warning(f"Falha ao carregar detalhe: {listing['url']}")

                    if not detail_html:
                        continue

                    job = parse_job_detail_page(detail_html, listing["url"])
                    if not job:
                        continue

                    # Usa dados da listagem se faltantes no detalhe
                    if not job.company and listing.get("company"):
                        job.company = listing["company"]
                    if not job.city and listing.get("city"):
                        job.city = listing["city"]

                    # FILTRO CRÍTICO: sem e-mail = descartada
                    if not job.contact_emails:
                        discarded_no_email += 1
                        logger.debug(f"Descartada (sem e-mail): {job.title}")
                        continue

                    # Filtro de palavras obrigatórias
                    if filters.required_keywords:
                        desc_lower = job.description.lower()
                        if not all(kw.lower() in desc_lower for kw in filters.required_keywords):
                            logger.debug(f"Descartada (palavra obrigatória ausente): {job.title}")
                            continue

                    all_jobs.append(job)
                    if on_progress:
                        on_progress(
                            f"Vagas com e-mail: {len(all_jobs)} (descartadas: {discarded_no_email})",
                            len(all_jobs),
                            0,
                        )

                if not next_page_exists:
                    logger.info("Última página atingida — fim da paginação")
                    break
                page_num += 1

            await browser.close()

    except Exception as e:
        logger.error(f"Erro fatal no scraping: {e}")
        raise ScraperError(f"Erro no scraping: {e}") from e

    logger.info(
        f"Scraping concluído: {total_raw} brutas, {len(all_jobs)} com e-mail, "
        f"{discarded_no_email} descartadas (sem e-mail)"
    )
    return all_jobs
