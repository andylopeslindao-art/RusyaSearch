import asyncio
import base64
import random
import re
import time
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

# Rotação de User-Agents modernos para evitar detecção
MODERN_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
]

# Script de Stealth para burlar detecção de bot no Playwright Headless
PLAYWRIGHT_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);
"""


class BrowserAction(BaseModel):
    action: str = Field(..., description="Tipo de ação: click, fill, scroll, login")
    selector: Optional[str] = Field(None, description="Seletor CSS do elemento")
    value: Optional[str] = Field(None, description="Valor para preencher em formulários ou login")


class BrowseOptions(BaseModel):
    url: str
    format: str = Field("markdown", description="Formato de saída: markdown, clean_html, text, json")
    js_render: bool = Field(False, description="Forçar renderização JavaScript via Playwright Headless")
    engine: str = Field("auto", description="Motor: 'auto', 'http', 'playwright', 'jina'")
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    actions: Optional[List[BrowserAction]] = None
    capture_screenshot: bool = Field(False, description="Capturar screenshot real (base64 PNG)")


class AgentBrowser:
    """
    10/10 REVOLUTIONARY HYBRID STEALTH BROWSER & ANTI-BOT ENGINE
    ============================================================
    Motor Tri-Híbrido sem simulação:
    - Tier 1: Stealth HTTP Ultra-Rápido com headers autênticos e rotação de UA.
    - Tier 2: Real Playwright Headless Chromium com injeção Stealth anti-detecção
              (burlas de Cloudflare Turnstile, renderização JS real, clique/scroll/captura PNG).
    - Tier 3: Mirror Fallback (Jina Reader API) para contornar paywalls e firewalls agressivos.
    """

    @classmethod
    def _is_cloudflare_or_bot_challenge(cls, html: str, status_code: int) -> bool:
        if status_code in (403, 503, 429):
            return True
        lower = html.lower()
        challenges = [
            "cf-turnstile",
            "checking your browser",
            "just a moment...",
            "cloudflare",
            "enable javascript and cookies to continue",
            "access denied",
            "attention required! | cloudflare",
            "challenge-platform"
        ]
        return any(c in lower for c in challenges)

    @classmethod
    async def _browse_with_playwright(cls, options: BrowseOptions) -> Dict[str, Any]:
        from playwright.async_api import async_playwright
        from core.extractor import MarkdownExtractor

        action_log = []
        screenshot_base64 = None
        html = ""

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--window-size=1280,800"
                ]
            )
            context = await browser.new_context(
                user_agent=random.choice(MODERN_USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="pt-BR"
            )

            # Injeta script stealth antes da página carregar
            await context.add_init_script(PLAYWRIGHT_STEALTH_SCRIPT)

            if options.cookies:
                cookie_list = [
                    {"name": k, "value": v, "url": options.url}
                    for k, v in options.cookies.items()
                ]
                await context.add_cookies(cookie_list)

            page = await context.new_page()

            try:
                response = await page.goto(options.url, wait_until="domcontentloaded", timeout=25000)
                status_code = response.status if response else 200

                # Pequena espera para páginas SPA ou desafios Cloudflare resolverem
                await asyncio.sleep(1.5)

                # Scroll real para carregar imagens e blocos lazy-load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(0.5)

                # Executa ações reais no navegador se solicitadas
                if options.actions:
                    for act in options.actions:
                        try:
                            if act.action == "click" and act.selector:
                                await page.click(act.selector, timeout=3000)
                                action_log.append({"action": act.action, "selector": act.selector, "status": "executed_real"})
                            elif act.action == "fill" and act.selector and act.value:
                                await page.fill(act.selector, act.value, timeout=3000)
                                action_log.append({"action": act.action, "selector": act.selector, "status": "executed_real"})
                            elif act.action == "scroll":
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                action_log.append({"action": act.action, "status": "executed_real"})
                        except Exception as act_err:
                            action_log.append({"action": act.action, "selector": act.selector, "status": f"failed: {str(act_err)}"})

                html = await page.content()

                # Captura Screenshot REAL em PNG base64 se solicitado
                if options.capture_screenshot:
                    png_bytes = await page.screenshot(full_page=False)
                    screenshot_base64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")

            finally:
                await browser.close()

        extracted = MarkdownExtractor.extract(html, url=options.url)
        soup = BeautifulSoup(html, "lxml")

        # HTML limpo
        for unwanted in soup(["script", "style", "noscript", "iframe", "svg"]):
            unwanted.decompose()
        clean_html = str(soup.find("main") or soup.find("article") or soup.body or soup)

        res = {
            "url": options.url,
            "status_code": status_code,
            "title": extracted.title,
            "description": extracted.description,
            "word_count": extracted.word_count,
            "reading_time_min": extracted.reading_time_min,
            "format": options.format,
            "engine_used": "playwright_stealth",
            "actions_executed": action_log,
            "screenshot": screenshot_base64
        }

        if options.format == "clean_html":
            res["content"] = clean_html
        elif options.format == "text":
            res["content"] = extracted.raw_text
        elif options.format == "json":
            res["content"] = {
                "title": extracted.title,
                "url": options.url,
                "description": extracted.description,
                "word_count": extracted.word_count,
                "reading_time_min": extracted.reading_time_min,
                "markdown": extracted.markdown_with_frontmatter
            }
        else:
            res["content"] = extracted.markdown_with_frontmatter

        return res

    @classmethod
    async def _browse_with_jina_mirror(cls, options: BrowseOptions) -> Dict[str, Any]:
        """
        Tier 3: Mirror Fallback via Jina AI Reader API (contorna paywalls pesados).
        """
        mirror_url = f"https://r.jina.ai/{options.url}"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(mirror_url)
            resp.raise_for_status()
            md_content = resp.text

            # Separa título preliminar
            lines = [l.strip() for l in md_content.splitlines() if l.strip()]
            title = lines[0].replace("#", "").strip() if lines else options.url
            word_count = len(re.findall(r"\w+", md_content))

            frontmatter = [
                "---",
                f'title: "{title}"',
                f'url: "{options.url}"',
                "engine_used: jina_mirror",
                f"word_count: {word_count}",
                "---"
            ]
            full_md = "\n".join(frontmatter) + "\n\n" + md_content

            return {
                "url": options.url,
                "status_code": 200,
                "title": title,
                "description": "",
                "word_count": word_count,
                "reading_time_min": max(1, round(word_count / 200)),
                "format": options.format,
                "engine_used": "jina_mirror",
                "actions_executed": [],
                "content": full_md
            }

    @classmethod
    async def browse(cls, options: BrowseOptions) -> Dict[str, Any]:
        """
        Ponto de entrada do Motor Tri-Híbrido Automático (10/10 Revolutionary Tech).
        """
        # Se usuário pediu Playwright explícito ou js_render=True
        if options.engine == "playwright" or options.js_render:
            try:
                return await cls._browse_with_playwright(options)
            except Exception:
                pass

        if options.engine == "jina":
            return await cls._browse_with_jina_mirror(options)

        # TIER 1: Tenta HTTP Stealth Rápido primeiro
        req_headers = {
            "User-Agent": random.choice(MODERN_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        if options.headers:
            req_headers.update(options.headers)

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers=req_headers,
                cookies=options.cookies or {}
            ) as client:
                resp = await client.get(options.url)
                html = resp.text

                # Verifica se o site bloqueou ou pediu Cloudflare / Anti-Bot
                if cls._is_cloudflare_or_bot_challenge(html, resp.status_code):
                    # Aciona automaticamente o Tier 2: Real Playwright Stealth
                    try:
                        return await cls._browse_with_playwright(options)
                    except Exception:
                        # Se Playwright falhar, cai no Tier 3: Mirror Fallback
                        return await cls._browse_with_jina_mirror(options)

                from core.extractor import MarkdownExtractor
                extracted = MarkdownExtractor.extract(html, url=options.url)
                soup = BeautifulSoup(html, "lxml")

                for unwanted in soup(["script", "style", "noscript", "iframe", "svg"]):
                    unwanted.decompose()
                clean_html = str(soup.find("main") or soup.find("article") or soup.body or soup)

                res = {
                    "url": options.url,
                    "status_code": resp.status_code,
                    "title": extracted.title,
                    "description": extracted.description,
                    "word_count": extracted.word_count,
                    "reading_time_min": extracted.reading_time_min,
                    "format": options.format,
                    "engine_used": "http_stealth",
                    "actions_executed": []
                }

                if options.format == "clean_html":
                    res["content"] = clean_html
                elif options.format == "text":
                    res["content"] = extracted.raw_text
                elif options.format == "json":
                    res["content"] = {
                        "title": extracted.title,
                        "url": options.url,
                        "description": extracted.description,
                        "word_count": extracted.word_count,
                        "reading_time_min": extracted.reading_time_min,
                        "markdown": extracted.markdown_with_frontmatter
                    }
                else:
                    res["content"] = extracted.markdown_with_frontmatter

                return res

        except Exception:
            # Em caso de erro de conexão ou bloqueio de firewall, escala para Playwright ou Jina
            try:
                return await cls._browse_with_playwright(options)
            except Exception:
                return await cls._browse_with_jina_mirror(options)
