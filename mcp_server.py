#!/usr/bin/env python3
"""
RusyaSearch 2.0 — Servidor Oficial Model Context Protocol (MCP)
================================================================
Permite que agentes autônomos LLM (Claude Desktop, Cursor IDE, Antigravity,
CrewAI, AutoGen, LangChain) usem nativamente todas as capacidades do
RusyaSearch 2.0 via protocolo MCP stdio ou SSE.

Ferramentas Expostas:
- rusya_search: Pesquisa multi-fonte (Google/Web, GitHub, arXiv, StackOverflow, etc.)
- rusya_browse: Entra em qualquer URL e extrai Markdown limpo / HTML limpo
- rusya_extract: Extrai tabelas, listas, links, imagens ou OCR de PDFs
- rusya_research: Deep Research consolidando pesquisa + navegação em Dossiê MD
- rusya_google_research: Pesquisa no Google e entra nos links retornados
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
    Pesquisa na Web/Google, arXiv, GitHub, StackOverflow, Documentações ou Índice Local.

    Parâmetros:
    - query: Tópico de pesquisa.
    - sources: "all", "web", "arxiv", "github", "stackoverflow", "docs", "local".
    - max_results: Quantidade máxima de resultados (padrão: 15).
    - domain: Filtrar por site/domínio específico (ex: 'github.com').
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
        formatted.append(
            f"{idx}. **[{r.title}]({r.url})** [{r.source}]\n   {r.description}"
        )
    return f"### Resultados da Busca ({len(results)}):\n\n" + "\n\n".join(formatted)


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
