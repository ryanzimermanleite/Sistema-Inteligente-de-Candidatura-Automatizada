"""
Mecanismos anti-detecção para web scraping.

Fornece user-agents rotacionados e delays aleatórios para evitar bloqueio.
"""

from __future__ import annotations

import asyncio
import random
from typing import Optional

from loguru import logger


# Lista de User-Agents reais e atuais (Chrome, Firefox, Edge em Windows/Mac/Linux)
USER_AGENTS: list[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


def get_random_user_agent() -> str:
    """
    Retorna um User-Agent aleatório da lista.

    Returns:
        String do User-Agent.
    """
    return random.choice(USER_AGENTS)


async def random_delay(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
    """
    Aplica um delay aleatório assíncrono.

    Args:
        min_seconds: Delay mínimo em segundos.
        max_seconds: Delay máximo em segundos.
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Aguardando {delay:.1f}s (anti-detecção)")
    await asyncio.sleep(delay)


def random_delay_sync(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
    """
    Aplica um delay aleatório síncrono.

    Args:
        min_seconds: Delay mínimo em segundos.
        max_seconds: Delay máximo em segundos.
    """
    import time

    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Aguardando {delay:.1f}s (anti-detecção)")
    time.sleep(delay)


def get_stealth_browser_args() -> list[str]:
    """
    Retorna argumentos de launch do Playwright para evasão de detecção.

    Returns:
        Lista de argumentos para o browser.
    """
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-web-security",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--no-first-run",
        "--no-zygote",
        "--disable-gpu",
    ]


async def apply_stealth_scripts(page) -> None:
    """
    Aplica scripts de evasão de detecção em uma página do Playwright.

    Args:
        page: Instância de Page do Playwright.
    """
    # Remove navigator.webdriver
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # Override navigator.plugins
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)

    # Override navigator.languages
    await page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['pt-BR', 'pt', 'en-US', 'en']
        });
    """)

    # Override chrome property
    await page.add_init_script("""
        window.chrome = {
            runtime: {}
        };
    """)

    # Override permissions
    await page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)

    logger.debug("Scripts de stealth aplicados na página")
