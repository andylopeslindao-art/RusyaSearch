#!/usr/bin/env python3
"""
RusyaSearch 2.0 — Servidor Oficial Model Context Protocol (MCP)
================================================================
Permite que agentes autônomos LLM (Claude Desktop, Cursor IDE, Antigravity,
CrewAI, AutoGen, LangChain) usem nativamente todas as capacidades do
RusyaSearch 2.0 via protocolo MCP stdio ou SSE.

Ferramentas Expostas (11 Ferramentas de IA):
- rusya_search: Pesquisa multi-fonte (Google/Web, Reddit, GitHub, arXiv, StackOverflow, etc.)
- rusya_search_reddit: Pesquisa em tempo real no Reddit com nosso motor 100% nativo autônomo (Playwright Stealth + .json bypass)
- rusya_search_images: Pesquisa de imagens (.jpg, .png, .svg) e thumbnails com links diretos HD
- rusya_browse: Entra em qualquer URL (inclusive posts do Reddit extraindo comentários ao vivo via Playwright nativo) e extrai Markdown limpo
- rusya_extract: Extrai tabelas, listas, links, imagens ou OCR de PDFs
- rusya_research: Deep Research consolidando pesquisa + navegação em Dossiê MD
- rusya_google_research: Pesquisa no Google e entra nos links retornados
- rusya_google_suggest: Sugestões e ideias em tempo real do autocompletar do Google
- rusya_scholar: Artigos científicos, PDFs acadêmicos e citações no Google Scholar
- rusya_smart_dork: Constrói e executa Google Dorks avançados para investigação
- rusya_google_deep_research: Super-Agente que pesquisa no agregador Google, acessa top páginas e gera Dossiê Executivo
- rusya_crawl: Crawler profundo que indexa sites para o Índice Local
"""

import asyncio
import json
import sys
from typing import Optional
from mcp.server.fastmcp import FastMCP

from core.search_engines import MetaSearchEngine
from core.browser import AgentBrowser, BrowseOptions
from core.extractor import MarkdownExtractor
from core.crawler import Crawler

# Inicializa o servidor FastMCP
mcp = FastMCP("RusyaSearch")


@mcp.tool()
async def rusya_search(
    query: str,
    sources: str = "all",
    max_results: int = 15,
    domain: str = "",
    time_range: str = "",
    lang: str = "pt"
) -> str:
    """
    Pesquisa e agrega resultados do Google/Web, Reddit, GitHub, arXiv, StackOverflow, Docs ou Base Local.

    Parâmetros:
    - query: Tópico de pesquisa.
    - sources: "all", "web", "reddit", "arxiv", "github", "stackoverflow", "docs", "local".
    - max_results: Quantidade máxima de resultados (padrão: 15).
    - domain: Filtrar por site/domínio específico (ex: 'github.com' ou 'reddit.com/r/Python').
    - time_range: Filtro de tempo ('d' 24h, 'w' semana, 'm' mês, 'y' ano).
    - lang: Idioma ('pt', 'en', etc.).
    """
    results = await MetaSearchEngine.search(
        query=query,
        sources=sources,
        max_results=max_results,
        domain=domain,
        time_range=time_range,
        lang=lang
    )
    formatted = []
    for idx, r in enumerate(results, 1):
        title = r["title"] if isinstance(r, dict) else r.title
        url = r["url"] if isinstance(r, dict) else r.url
        source = r["source"] if isinstance(r, dict) else r.source
        desc = r["description"] if isinstance(r, dict) else r.description
        formatted.append(
            f"{idx}. **[{title}]({url})** [{source}]\n   {desc}"
        )
    return f"### Resultados da Busca ({len(results)}):\n\n" + "\n\n".join(formatted)


@mcp.tool()
async def rusya_search_reddit(
    query: str,
    subreddit: str = "",
    limit: int = 15
) -> str:
    """
    Pesquisa em tempo real e extração anti-bot de discussões, dúvidas e códigos no Reddit.
    Utiliza nosso motor 100% nativo e autônomo (Playwright Chromium + injeção Stealth + .json bypass rotativo),
    garantindo que postagens recentes, votos e discussões sejam coletados sem bloqueios, sem CAPTCHA e sem depender de APIs de terceiros.

    Parâmetros:
    - query: Termo ou dúvida pesquisada no Reddit.
    - subreddit: Nome opcional do subreddit (ex: 'Python', 'learnprogramming', 'brasil').
    - limit: Número máximo de postagens (padrão: 15).
    """
    from core.search_engines import RedditSearcher
    domain_arg = f"reddit.com/r/{subreddit}" if subreddit else ""
    results = await RedditSearcher.search(query=query, limit=limit, domain=domain_arg)
    formatted = []
    for idx, r in enumerate(results, 1):
        title = r["title"] if isinstance(r, dict) else r.title
        url = r["url"] if isinstance(r, dict) else r.url
        source = r["source"] if isinstance(r, dict) else r.source
        desc = r["description"] if isinstance(r, dict) else r.description
        formatted.append(
            f"{idx}. **[{title}]({url})** [{source}]\n   {desc}"
        )
    return f"### Discussões e Posts no Reddit ({len(results)}):\n\n" + "\n\n".join(formatted) if formatted else "Nenhuma discussão encontrada no Reddit."


@mcp.tool()
async def rusya_search_images(
    query: str,
    limit: int = 15
) -> str:
    """
    Pesquisa e retorna links diretos de imagens (.png, .jpg, .webp, .svg), resoluções e thumbnails.
    Ideal para agentes IA ou desenvolvedores (Claude Code, Hermes, Cursor) construindo sites ou interfaces
    que precisam de tags <img src="..."> com imagens reais e funcionais da internet.

    Parâmetros:
    - query: Descrição ou termo da imagem desejada (ex: 'logo python png transparente', 'banner tech dark').
    - limit: Quantidade máxima de imagens retornadas (padrão 15).
    """
    from core.search_engines import ImageSearcher
    results = await ImageSearcher.search(query=query, limit=limit)
    formatted = []
    for idx, r in enumerate(results, 1):
        formatted.append(
            f"{idx}. **URL Direta da Imagem:** `{r.url}`\n   - Título: {r.title}\n   - Detalhes: {r.description}"
        )
    return f"### Imagens Encontradas ({len(results)}):\n\n" + "\n\n".join(formatted) if formatted else "Nenhuma imagem encontrada."


@mcp.tool()
async def rusya_browse(
    url: str,
    format: str = "markdown",
    js_render: bool = True
) -> str:
    """
    Entra em qualquer URL da web e retorna o conteúdo em Markdown limpo (.md)
    otimizado para o orçamento de tokens do LLM, sem scripts ou anúncios.

    Parâmetros:
    - url: URL completa da página a ser visitada.
    - format: Formato de retorno ('markdown', 'clean_html', 'text', 'json').
    - js_render: Renderizar JavaScript / Headless (padrão: True).
    """
    options = BrowseOptions(
        url=url,
        format=format,
        js_render=js_render
    )
    res = await AgentBrowser.browse(options)
    content = res.get("content", "")
    if isinstance(content, dict):
        return json.dumps(content, indent=2, ensure_ascii=False)
    return str(content)


@mcp.tool()
async def rusya_extract(
    url: str,
    target: str = "tables"
) -> str:
    """
    Extrai dados estruturados específicos de uma página da Web ou PDF.

    Parâmetros:
    - url: URL da página ou arquivo PDF.
    - target: Alvo da extração ('tables', 'lists', 'links', 'images', 'pdf_ocr').
    """
    import httpx
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": "RusyaSearch-MCP/2.0"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        if target == "pdf_ocr" or url.lower().endswith(".pdf"):
            try:
                import io
                import pypdf
                pdf = pypdf.PdfReader(io.BytesIO(resp.content))
                text = []
                for idx, page in enumerate(pdf.pages, 1):
                    t = page.extract_text()
                    if t:
                        text.append(f"## Página {idx}\n{t.strip()}")
                return f"# OCR / Texto Extraído de PDF: {url}\n\n" + "\n\n".join(text)
            except Exception as e:
                return f"Erro na extração de PDF: {str(e)}"

        html = resp.text
        if target == "tables":
            tables = MarkdownExtractor.extract_tables(html, base_url=url)
            md_tables = [t["markdown"] for t in tables]
            return f"### Tabelas Extraídas ({len(tables)}):\n\n" + "\n\n---\n\n".join(md_tables)
        elif target == "lists":
            lists = MarkdownExtractor.extract_lists(html, base_url=url)
            md_lists = ["\n".join(l["items"]) for l in lists]
            return f"### Listas Extraídas ({len(lists)}):\n\n" + "\n\n---\n\n".join(md_lists)
        elif target == "links":
            links = MarkdownExtractor.extract_links(html, base_url=url)
            formatted = [f"- [{l['text']}]({l['href']})" for l in links[:50]]
            return f"### Principais Links ({len(links)}):\n\n" + "\n".join(formatted)
        elif target == "images":
            images = MarkdownExtractor.extract_images(html, base_url=url)
            formatted = [f"![{img['alt']}]({img['src']})" for img in images[:30]]
            return f"### Imagens Extraídas ({len(images)}):\n\n" + "\n\n".join(formatted)
        else:
            extracted = MarkdownExtractor.extract(html, url=url)
            return extracted.markdown_with_frontmatter


@mcp.tool()
async def rusya_research(
    query: str,
    browse_top_n: int = 2
) -> str:
    """
    Agente de Deep Research: pesquisa sobre um tema em múltiplas fontes
    e ENTRA em paralelo nas Top N páginas, consolidando tudo num Dossiê Markdown.

    Parâmetros:
    - query: Tópico a ser pesquisado profundamente.
    - browse_top_n: Número de páginas para acessar e ler (padrão: 2).
    """
    search_results = await MetaSearchEngine.search(query, sources="all", max_results=max(10, browse_top_n * 2))
    top_results = search_results[:browse_top_n]

    dossier_lines = [
        f"# Dossiê de Pesquisa AI: {query}\n",
        f"**Páginas Navegadas:** {len(top_results)}\n",
        "## 1. Resumo dos Resultados:\n"
    ]
    for idx, r in enumerate(top_results, 1):
        dossier_lines.append(f"{idx}. **[{r.title}]({r.url})** — {r.description}")

    dossier_lines.append("\n---\n## 2. Conteúdo em Markdown das Páginas Navegadas\n")

    for r in top_results:
        try:
            options = BrowseOptions(url=r.url, format="markdown")
            page_res = await AgentBrowser.browse(options)
            content = page_res.get("content", "")
            dossier_lines.append(f"### {r.title}\n**URL:** {r.url}\n\n{content}\n---\n")
        except Exception as e:
            dossier_lines.append(f"### {r.title}\n**URL:** {r.url}\n\nErro ao navegar: {str(e)}\n---\n")

    return "\n".join(dossier_lines)


@mcp.tool()
async def rusya_google_research(
    query: str,
    browse_top_n: int = 2
) -> str:
    """
    Pesquisa direto no Google/Web e ENTRA nos links retornados pelo Google,
    entregando o conteúdo integral dos sites limpo em Markdown.

    Parâmetros:
    - query: Termo de busca no Google.
    - browse_top_n: Quantos links do Google visitar (padrão: 2).
    """
    search_results = await MetaSearchEngine.search(query, sources="web", max_results=browse_top_n)
    pages_md = []
    for r in search_results[:browse_top_n]:
        try:
            page_res = await AgentBrowser.browse(BrowseOptions(url=r.url, format="markdown"))
            content = page_res.get("content", "")
            pages_md.append(f"## {r.title}\n**URL:** {r.url}\n\n{content}")
        except Exception as e:
            pages_md.append(f"## {r.title}\n**URL:** {r.url}\n\nErro ao acessar: {str(e)}")

    return f"# Pesquisa Google & Acesso Aos Links: {query}\n\n" + "\n\n---\n\n".join(pages_md)


@mcp.tool()
async def rusya_google_suggest(query: str) -> str:
    """
    Obtém sugestões e ideias em tempo real do autocompletar do Google para explorar intenções e variações de palavras-chave.
    """
    from core.search_engines import GoogleSuggestSearcher
    suggestions = await GoogleSuggestSearcher.suggest(query)
    formatted = [f"- `{s}`" for s in suggestions]
    return f"### Sugestões do Google para '{query}' ({len(suggestions)}):\n\n" + "\n".join(formatted)


@mcp.tool()
async def rusya_scholar(query: str, limit: int = 12) -> str:
    """
    Pesquisa artigos científicos, PDFs acadêmicos e citações técnicas diretamente no Google Scholar e arXiv.
    """
    from core.search_engines import GoogleScholarSearcher
    results = await GoogleScholarSearcher.search(query, limit=limit)
    formatted = []
    for idx, r in enumerate(results, 1):
        formatted.append(f"{idx}. **[{r.title}]({r.url})**\n   {r.description}")
    return f"### Artigos Acadêmicos ({len(results)}):\n\n" + "\n\n".join(formatted) if formatted else "Nenhum artigo acadêmico encontrado."


@mcp.tool()
async def rusya_smart_dork(
    intent: str,
    domain: str = "",
    filetype: str = "",
    inurl: str = ""
) -> str:
    """
    Constrói e executa Google Dorks cirúrgicos (site:, filetype:, inurl:) a partir de uma intenção em linguagem natural.
    Ideal para auditoria de segurança, busca de manuais PDF, planilhas expostas ou rastreamento de dados em domínios alvos.
    """
    from core.search_engines import SmartDorkBuilder, MetaSearchEngine
    dork_query = SmartDorkBuilder.build_dork(intent, domain=domain, filetype=filetype, inurl=inurl)
    results = await MetaSearchEngine.search(dork_query, sources="web", max_results=15)
    formatted = []
    for idx, r in enumerate(results, 1):
        formatted.append(f"{idx}. **[{r.title}]({r.url})**\n   {r.description}")
    return f"### Google Dork Executado: `{dork_query}` ({len(results)} resultados):\n\n" + "\n\n".join(formatted)


@mcp.tool()
async def rusya_google_deep_research(
    query: str,
    browse_top_n: int = 2
) -> str:
    """
    Super-Agente de Deep Research no Google & Web:
    Consulta nosso agregador Quad-Google, acessa as páginas em paralelo e retorna um dossiê executivo em Markdown limpo com tabelas e links.
    """
    from core.agent_tools import AgentToolsService
    res = await AgentToolsService.google_deep_research(query, browse_top_n=browse_top_n, max_chars_per_page=7000)
    return res.get("consolidated_dossier_markdown", "Erro ao processar dossiê.")


@mcp.tool()
async def rusya_search_icons(
    query: str,
    limit: int = 15
) -> str:
    """
    Pesquisa ícones transparentes (PNG/SVG) e logos oficiais de marcas ou tecnologias,
    prontos para injeção de código HTML (<img src="..." />) no desenvolvimento de interfaces.

    Parâmetros:
    - query: Nome do ícone, marca ou tecnologia (ex: 'python logo', 'user icon svg').
    - limit: Quantidade máxima de ícones/logos a retornar (padrão: 15).
    """
    from core.agent_tools import AgentToolsService
    res = await AgentToolsService.search_icons(query, limit=limit)
    icons = res.get("icons", [])
    if not icons:
        return f"Nenhum ícone encontrado para '{query}'."
    formatted = [f"### {idx}. {ic['title']}\n- **URL do Ícone/PNG:** {ic['url']}\n- **Snippet:** `<img src='{ic['url']}' alt='{ic['title']}' />`\n- **Fonte:** {ic['source']}" for idx, ic in enumerate(icons, 1)]
    return f"# Ícones & SVGs Encontrados ({len(icons)}):\n\n" + "\n\n---\n\n".join(formatted)


@mcp.tool()
async def rusya_universal_access(
    url: str,
    max_chars: int = 10000
) -> str:
    """
    Acessa qualquer URL restrita, com bloqueio agressivo ou paywall, utilizando nossa Matriz Universal Quad-Tier
    (HTTPx -> Playwright Stealth/WebGL Spoof -> Jina Mirror -> Wayback CDX & Google Web Cache).
    Garante 100% de sucesso na extração do conteúdo em Markdown limpo para agentes de IA.

    Parâmetros:
    - url: Endereço web ou artigo restrito.
    - max_chars: Orçamento de caracteres para extração (padrão: 10000).
    """
    from core.agent_tools import AgentToolsService
    res = await AgentToolsService.universal_browse(url, max_chars=max_chars)
    return f"# [Matriz Universal Quad-Tier] {res.get('title')}\n**URL:** {res.get('url')} | **Motor Acionado:** `{res.get('engine_used')}` | **Palavras:** {res.get('word_count', 0)}\n\n---\n\n{res.get('markdown')}"


@mcp.tool()
async def rusya_crawl(
    seed_url: str,
    max_pages: int = 30,
    max_depth: int = 3,
    concurrency: int = 4
) -> str:
    """
    Crawl avançado de um site inteiro, convertendo todas as páginas para Markdown
    e gravando no Índice Local para buscas offline rápidas.

    Parâmetros:
    - seed_url: URL inicial do site.
    - max_pages: Máximo de páginas para indexar.
    - max_depth: Limite de profundidade de cliques.
    - concurrency: Workers assíncronos simultâneos.
    """
    crawler = Crawler(
        max_pages=max_pages,
        max_depth=max_depth,
        concurrency=concurrency
    )
    pages = await crawler.crawl(seed_url)
    return f"✔ Indexação Concluída para {seed_url}!\n• Páginas processadas em Markdown: {len(pages)}"


if __name__ == "__main__":
    # Rodar no modo stdio (padrão MCP para Cursor, Claude Desktop e CLI)
    mcp.run(transport="stdio")
