"""
Teste isolado do scraper Google Jobs — card por card.

Abre cada card, lê descrição do template, pula se não tem email.
Se tem email → retorna título, local, salário, modelo, resumo.
Suporta infinite scroll para carregar TODAS as vagas.
"""

import asyncio
import re
import sys
import os
import urllib.parse

# Fix encoding para Windows console (emojis)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
#  Helpers
# ============================================================

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

GENERIC_PREFIXES = [
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "abuse", "spam", "newsletter",
    "notifications", "notification", "alert", "alerts", "info@google",
    "support@google", "sac@", "suporte@", "atendimento@",
]


def extract_emails_simple(text: str) -> list[str]:
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    seen = set()
    result = []
    for email in matches:
        el = email.lower()
        if el in seen:
            continue
        seen.add(el)
        if any(p in el for p in GENERIC_PREFIXES):
            continue
        result.append(el)
    return result


def detect_modality(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["remoto", "remote", "home office"]):
        return "Remoto"
    if any(k in t for k in ["híbrido", "hibrido", "hybrid"]):
        return "Híbrido"
    return "Presencial"


def parse_salary(text: str) -> str:
    if not text or not text.strip():
        return "Não informado"
    return text.strip()


def summarize_description(text: str, max_chars: int = 300) -> str:
    if not text:
        return "Sem descrição"
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rsplit(" ", 1)[0] + "..."


# ============================================================
#  JavaScript — Seletores atualizados (Abril 2026)
#  Baseados no DOM real do Google Jobs
# ============================================================

# Conta cards na lista
JS_COUNT_CARDS = """
() => {
    return document.querySelectorAll('div.EimVGf').length;
}
"""

# Clica num card pelo índice
JS_CLICK_CARD = """
(index) => {
    const cards = document.querySelectorAll('div.EimVGf');
    if (!cards[index]) return false;
    const card = cards[index];

    // Botão clicável principal
    const btn = card.querySelector('div[role="button"][jscontroller="qodLAe"]');
    if (btn) {
        btn.scrollIntoView({behavior: 'instant', block: 'center'});
        btn.click();
        return true;
    }

    // Fallback
    card.scrollIntoView({behavior: 'instant', block: 'center'});
    card.click();
    return true;
}
"""

# Scrolla a lista para carregar mais cards (infinite scroll)
JS_SCROLL_CARD_LIST = """
() => {
    const cards = document.querySelectorAll('div.EimVGf');
    if (cards.length > 0) {
        cards[cards.length - 1].scrollIntoView({behavior: 'instant', block: 'end'});
    }

    // Também tenta scrollar containers de scroll
    const scrollContainers = document.querySelectorAll('[jscontroller="cHmovd"]');
    for (const sc of scrollContainers) {
        sc.scrollTop = sc.scrollHeight;
        if (sc.parentElement) sc.parentElement.scrollTop = sc.parentElement.scrollHeight;
    }

    // Verifica fim da lista
    const endMsg = document.querySelector('div[jsname="CLJY1d"]');
    const isEnd = endMsg && (endMsg.offsetParent !== null || endMsg.textContent.includes('Não há mais vagas'));

    return { count: cards.length, isEnd: !!isEnd };
}
"""

# Extrai dados de um card usando o <template> interno
JS_EXTRACT_CARD = """
(index) => {
    const cards = document.querySelectorAll('div.EimVGf');
    if (!cards[index]) return null;
    const card = cards[index];

    // === DADOS DO CARD NA LISTA ===
    const titleEl = card.querySelector('.tNxQIb.PUpOsf');
    const title = titleEl ? titleEl.textContent.trim() : '';

    const companyEl = card.querySelector('.wHYlTd.MKCbgd.a3jPc');
    const company = companyEl ? companyEl.textContent.trim() : '';

    const locEl = card.querySelector('.wHYlTd.FqK3wc.MKCbgd');
    let locationText = '', source = '';
    if (locEl) {
        const fullText = locEl.textContent.trim();
        const parts = fullText.split('•').map(s => s.trim());
        if (parts[0]) locationText = parts[0];
        if (parts[1]) source = parts[1].replace(/^via\\s+/i, '').replace(/^no site\\s+/i, '').trim();
    }

    // Meta: salário, tipo, publicado
    let salary = '', employmentType = '', postedAgo = '';
    const metaItems = card.querySelectorAll('.Yf9oye');
    for (const item of metaItems) {
        const label = item.getAttribute('aria-label') || '';
        const text = item.textContent.trim();
        if (label.includes('Salário') || label.includes('salário')) salary = text;
        else if (label.includes('Tipo de emprego')) employmentType = text;
        else if (label.includes('Publicado')) postedAgo = text;
    }

    // === DADOS DO TEMPLATE ===
    let description = '';
    const applyLinks = [];
    let docId = '';

    const template = card.querySelector('template');
    if (template && template.content) {
        const frag = template.content;

        // Descrição completa (visível + oculta)
        const visibleDesc = frag.querySelector('[jsname="QAWWu"]');
        const hiddenDesc = frag.querySelector('[jsname="ij8cu"]');
        const visibleText = visibleDesc ? visibleDesc.textContent.trim() : '';
        const hiddenText = hiddenDesc ? hiddenDesc.textContent.trim() : '';
        description = (visibleText + ' ' + hiddenText).trim();

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
        if (detailEl) docId = detailEl.getAttribute('data-encoded-docid') || '';

        // Fallbacks do template
        if (!salary) {
            const tags = frag.querySelectorAll('.fLsjxc');
            for (const t of tags) {
                const txt = t.textContent.trim();
                if (txt.includes('R$') || (txt.includes('mil') && txt.match(/\\d/))) { salary = txt; break; }
            }
        }
        if (!employmentType) {
            const tags = frag.querySelectorAll('.fLsjxc');
            for (const t of tags) {
                const txt = t.textContent.trim();
                if (['Tempo integral', 'Meio período', 'Contrato', 'Estágio'].some(k => txt.includes(k))) { employmentType = txt; break; }
            }
        }
        if (!postedAgo) {
            const tags = frag.querySelectorAll('.fLsjxc');
            for (const t of tags) {
                const txt = t.textContent.trim();
                if (txt.startsWith('há ') && txt.length < 30) { postedAgo = txt; break; }
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
#  Teste principal
# ============================================================


async def test_google_jobs():
    from playwright.async_api import async_playwright

    query = "programador"
    location = "Campinas, SP"
    search_query = f"{query} {location}"
    params = {"q": search_query, "udm": "8", "hl": "pt-BR"}
    url = f"https://www.google.com/search?{urllib.parse.urlencode(params)}"

    print(f"\n{'='*70}")
    print(f"  TESTE GOOGLE JOBS — Template-based extraction")
    print(f"  Query: {search_query}")
    print(f"  URL: {url}")
    print(f"{'='*70}\n")

    vagas_com_email = []
    vagas_sem_email = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        # ---- NAVEGAÇÃO + CAPTCHA ----
        print("[1] Navegando para Google Jobs...")
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        content = await page.content()
        if "captcha" in content.lower() or "unusual traffic" in content.lower():
            print("\n🚨 CAPTCHA detectado! Resolva manualmente no navegador...")
            print("   Aguardando até 5 minutos...\n")
            try:
                await page.wait_for_function(
                    """() => {
                        const body = document.body.innerHTML.toLowerCase();
                        return !body.includes('captcha') && !body.includes('unusual traffic');
                    }""",
                    timeout=300000,
                    polling=2000,
                )
                print("✅ CAPTCHA resolvido! Aguardando cards carregarem...\n")
                await asyncio.sleep(5)

                try:
                    await page.wait_for_selector('div.EimVGf', timeout=30000)
                except Exception:
                    print("   ⏳ Cards ainda não apareceram, aguardando mais 5s...")
                    await asyncio.sleep(5)

                await asyncio.sleep(3)

            except Exception:
                print("❌ Timeout no CAPTCHA (5 minutos)")
                await browser.close()
                return

        # ---- ESPERA CARDS INICIAIS ----
        print("[2] Aguardando cards de vagas...")
        try:
            await page.wait_for_selector('div.EimVGf', timeout=15000)
        except Exception:
            print("   ⚠️ Seletor não encontrado, aguardando...")
            await asyncio.sleep(3)

        # ---- INFINITE SCROLL ----
        print("[3] Carregando todas as vagas (infinite scroll)...")

        prev_count = 0
        stale_rounds = 0

        for scroll_round in range(30):
            result = await page.evaluate(JS_SCROLL_CARD_LIST)
            current_count = result.get("count", 0)
            is_end = result.get("isEnd", False)

            print(f"    Scroll #{scroll_round + 1}: {current_count} cards", end="")

            if is_end:
                print(" ← FIM DA LISTA")
                break

            if current_count == prev_count:
                stale_rounds += 1
                print(f" (sem novos: {stale_rounds}/5)")
                if stale_rounds >= 5:
                    break
            else:
                stale_rounds = 0
                print()

            prev_count = current_count
            await asyncio.sleep(1.5)

        # ---- CONTAGEM FINAL ----
        card_count = await page.evaluate(JS_COUNT_CARDS)
        print(f"\n    Total de cards carregados: {card_count}\n")

        if card_count == 0:
            print("❌ Nenhum card encontrado!")
            await page.screenshot(path="debug_no_cards.png")
            await browser.close()
            return

        # ---- LOOP DE CARDS ----
        print(f"[4] Analisando {card_count} cards...\n")

        for i in range(card_count):
            print(f"--- Card {i+1}/{card_count} ---")

            try:
                # Clica no card (visual feedback)
                clicked = await page.evaluate(JS_CLICK_CARD, i)
                if not clicked:
                    print(f"  ⚠️ Falha ao clicar card {i+1}")
                    continue

                await asyncio.sleep(0.5)

                # Extrai dados do template
                data = await page.evaluate(JS_EXTRACT_CARD, i)

                if not data or not data.get("title"):
                    print(f"  ⚠️ Sem título para card {i+1}")
                    print(f"     Data: {data}")
                    continue

                title = data["title"]
                description = data.get("description", "")
                company = data.get("company", "")

                # Busca email na descrição
                emails = extract_emails_simple(description)

                if not emails:
                    vagas_sem_email += 1
                    print(f"  ❌ SEM EMAIL — {title[:60]}")
                    print(f"     Empresa: {company}")
                    desc_preview = description[:100] + "..." if description else "Sem descrição"
                    print(f"     Descrição: {desc_preview}")
                    print()
                    continue

                # TEM EMAIL!
                location_text = data.get("location", "")
                salary = parse_salary(data.get("salary", ""))
                modality = detect_modality(
                    " ".join([description, title, location_text, data.get("employmentType", "")])
                )
                summary = summarize_description(description)

                vaga = {
                    "titulo": title,
                    "empresa": company,
                    "local": location_text,
                    "salario": salary,
                    "modelo": modality,
                    "emails": emails,
                    "resumo": summary,
                    "tipo": data.get("employmentType", ""),
                    "publicado": data.get("postedAgo", ""),
                    "links": data.get("applyLinks", []),
                    "fonte": data.get("source", ""),
                }
                vagas_com_email.append(vaga)

                print(f"  ✅ COM EMAIL!")
                print(f"  ┌──────────────────────────────────────")
                print(f"  │ 📌 Título:    {title}")
                print(f"  │ 🏢 Empresa:   {company}")
                print(f"  │ 📍 Local:     {location_text}")
                print(f"  │ 💰 Salário:   {salary}")
                print(f"  │ 🏠 Modelo:    {modality}")
                print(f"  │ 📧 Email(s):  {', '.join(emails)}")
                print(f"  │ 📝 Resumo:    {summary[:150]}...")
                print(f"  └──────────────────────────────────────")
                print()

            except Exception as e:
                print(f"  ⚠️ Erro no card {i+1}: {e}")
                continue

        await browser.close()

    # ---- RELATÓRIO FINAL ----
    print(f"\n{'='*70}")
    print(f"  RESULTADO FINAL")
    print(f"{'='*70}")
    print(f"  Total de cards analisados:  {card_count}")
    print(f"  Com email (coletadas):      {len(vagas_com_email)}")
    print(f"  Sem email (puladas):        {vagas_sem_email}")
    print(f"{'='*70}")

    if vagas_com_email:
        print(f"\n{'='*70}")
        print(f"  VAGAS COM EMAIL")
        print(f"{'='*70}")
        for idx, v in enumerate(vagas_com_email, 1):
            print(f"\n  ╔═══════════════════════════════════════════╗")
            print(f"  ║ Vaga #{idx}")
            print(f"  ╠═══════════════════════════════════════════╣")
            print(f"  ║ 📌 Título:    {v['titulo']}")
            print(f"  ║ 🏢 Empresa:   {v['empresa']}")
            print(f"  ║ 📍 Local:     {v['local']}")
            print(f"  ║ 💰 Salário:   {v['salario']}")
            print(f"  ║ 🏠 Modelo:    {v['modelo']}")
            if v.get("tipo"):
                print(f"  ║ 📋 Tipo:      {v['tipo']}")
            if v.get("publicado"):
                print(f"  ║ 🕐 Publicado: {v['publicado']}")
            if v.get("fonte"):
                print(f"  ║ 🌐 Fonte:     {v['fonte']}")
            print(f"  ║ 📧 Emails:    {', '.join(v['emails'])}")
            print(f"  ║ 📝 Resumo:    {v['resumo'][:200]}")
            if v.get("links"):
                print(f"  ║ 🔗 Links de candidatura:")
                for link in v["links"][:3]:
                    print(f"  ║    • {link.get('title', 'Link')[:40]}: {link['url'][:70]}...")
            print(f"  ╚═══════════════════════════════════════════╝")
    else:
        print("\n  ⚠️ Nenhuma vaga com email encontrada nesta busca.")

    print()


if __name__ == "__main__":
    asyncio.run(test_google_jobs())
