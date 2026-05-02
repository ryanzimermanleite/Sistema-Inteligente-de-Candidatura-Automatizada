"""
Debug: inspeciona o DOM do Google Jobs para encontrar os seletores corretos dos cards.
"""
import asyncio
import sys
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')


async def debug():
    from playwright.async_api import async_playwright

    query = "programador Campinas, SP"
    params = {"q": query, "udm": "8", "hl": "pt-BR"}
    url = f"https://www.google.com/search?{urllib.parse.urlencode(params)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
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
            window.chrome = { runtime: {} };
        """)

        print(f"Navegando: {url}")
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # CAPTCHA check
        content = await page.content()
        if "captcha" in content.lower() or "unusual traffic" in content.lower():
            print("\n🚨 CAPTCHA! Resolva no navegador...")
            await page.wait_for_function(
                """() => {
                    const body = document.body.innerHTML.toLowerCase();
                    return !body.includes('captcha') && !body.includes('unusual traffic');
                }""",
                timeout=300000,
                polling=2000,
            )
            print("✅ CAPTCHA resolvido! Aguardando cards...")
            await asyncio.sleep(8)

        # Espera extra
        await asyncio.sleep(5)

        # Screenshot
        await page.screenshot(path="debug_page.png", full_page=False)
        print("📸 Screenshot salvo: debug_page.png")

        # Inspeciona DOM
        dom_info = await page.evaluate("""
        () => {
            const results = [];
            
            // 1. Tudo com role="button"
            const buttons = document.querySelectorAll('[role="button"]');
            const buttonInfo = [];
            for (const b of buttons) {
                const text = b.textContent.trim().substring(0, 80);
                if (text.length > 10) {
                    buttonInfo.push({
                        tag: b.tagName,
                        id: b.id || '',
                        classes: b.className.substring(0, 100),
                        text: text,
                        childCount: b.children.length,
                    });
                }
            }
            results.push({ name: 'role=button (text>10chars)', count: buttonInfo.length, items: buttonInfo.slice(0, 15) });
            
            // 2. li elements
            const lis = document.querySelectorAll('li');
            const liInfo = [];
            for (const li of lis) {
                const text = li.textContent.trim().substring(0, 80);
                if (text.length > 20 && text.length < 500) {
                    liInfo.push({
                        tag: 'LI',
                        classes: li.className.substring(0, 100),
                        text: text,
                    });
                }
            }
            results.push({ name: 'li elements (20<text<500)', count: liInfo.length, items: liInfo.slice(0, 15) });
            
            // 3. Elements with data-title
            const dataTitles = document.querySelectorAll('[data-title]');
            const dtInfo = [];
            for (const el of dataTitles) {
                dtInfo.push({
                    tag: el.tagName,
                    dataTitle: el.getAttribute('data-title').substring(0, 60),
                    classes: el.className.substring(0, 100),
                    id: el.id || '',
                });
            }
            results.push({ name: 'data-title elements', count: dtInfo.length, items: dtInfo.slice(0, 15) });
            
            // 4. Role="treeitem" or role="listitem" 
            const treeItems = document.querySelectorAll('[role="treeitem"], [role="listitem"]');
            const tiInfo = [];
            for (const el of treeItems) {
                tiInfo.push({
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    classes: el.className.substring(0, 100),
                    id: el.id || '',
                    text: el.textContent.trim().substring(0, 80),
                });
            }
            results.push({ name: 'treeitem/listitem', count: tiInfo.length, items: tiInfo.slice(0, 15) });
            
            // 5. role="list" or role="tree"
            const lists = document.querySelectorAll('[role="list"], [role="tree"]');
            const listInfo = [];
            for (const el of lists) {
                listInfo.push({
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    classes: el.className.substring(0, 100),
                    childCount: el.children.length,
                    firstChildTag: el.children[0] ? el.children[0].tagName : '',
                    firstChildClasses: el.children[0] ? el.children[0].className.substring(0, 100) : '',
                });
            }
            results.push({ name: 'list/tree containers', count: listInfo.length, items: listInfo });
            
            // 6. Procura por headings dentro de containers interativos
            const headings = document.querySelectorAll('[role="heading"]');
            const headingInfo = [];
            for (const h of headings) {
                const parent = h.closest('[role="button"], [role="treeitem"], [role="listitem"], li, [data-title]');
                headingInfo.push({
                    text: h.textContent.trim().substring(0, 80),
                    level: h.getAttribute('aria-level'),
                    parentTag: parent ? parent.tagName : 'none',
                    parentRole: parent ? (parent.getAttribute('role') || '') : '',
                    parentClasses: parent ? parent.className.substring(0, 100) : '',
                    parentId: parent ? (parent.id || '') : '',
                });
            }
            results.push({ name: 'headings with interactive parents', count: headingInfo.length, items: headingInfo.slice(0, 20) });

            // 7. Divs com jscontroller que parecem cards de vaga
            const jsControllers = document.querySelectorAll('div[jscontroller]');
            const jscInfo = [];
            for (const el of jsControllers) {
                const text = el.textContent.trim();
                if (text.length > 30 && text.length < 600 && el.querySelector('[role="heading"]')) {
                    jscInfo.push({
                        jscontroller: el.getAttribute('jscontroller'),
                        classes: el.className.substring(0, 100),
                        id: el.id || '',
                        text: text.substring(0, 100),
                        role: el.getAttribute('role') || '',
                    });
                }
            }
            results.push({ name: 'jscontroller divs with heading (30<text<600)', count: jscInfo.length, items: jscInfo.slice(0, 15) });
            
            // 8. All ul > li structure inspection
            const ulElements = document.querySelectorAll('ul');
            const ulInfo = [];
            for (const ul of ulElements) {
                if (ul.children.length >= 3) {
                    const firstChild = ul.children[0];
                    ulInfo.push({
                        classes: ul.className.substring(0, 100),
                        childCount: ul.children.length,
                        firstChildTag: firstChild.tagName,
                        firstChildClasses: firstChild.className.substring(0, 100),
                        firstChildTextLen: firstChild.textContent.trim().length,
                        firstChildText: firstChild.textContent.trim().substring(0, 80),
                    });
                }
            }
            results.push({ name: 'ul with 3+ children', count: ulInfo.length, items: ulInfo.slice(0, 10) });
            
            return results;
        }
        """)

        print("\n" + "="*70)
        print("  DOM INSPECTION RESULTS")
        print("="*70)
        for section in dom_info:
            print(f"\n--- {section['name']} ({section['count']}) ---")
            for item in section.get('items', []):
                for k, v in item.items():
                    print(f"  {k}: {v}")
                print("  ---")

        # Mantém navegador aberto para inspeção manual
        print("\n\n🔍 Navegador aberto para inspeção. Pressione Enter para fechar...")
        await asyncio.sleep(600)  # 10 min
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug())
