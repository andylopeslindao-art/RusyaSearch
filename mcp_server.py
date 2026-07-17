#!/usr/bin/env python3
"""
RusyaSearch 3.0 Supreme — Servidor Oficial Model Context Protocol (MCP)
========================================================================
Especialmente otimizado para agentes autônomos de código (Claude Code, Cursor IDE,
Windsurf, Antigravity, CrewAI, AutoGen, LangChain).
Permite que agentes utilizem nativamente nosso motor primário Brave Supreme v9.0,
extração limpa de Markdown sem anúncios, OCR de PDFs, Google Dorks e resolução rápida
de erros de programação sem CAPTCHA e sem depender de APIs pagas.

Ferramentas Expostas (14 Ferramentas de IA):
- rusya_code_solve: (Especial Claude Code) Pesquisa paralela de erros e dúvidas técnicas (StackOverflow + GitHub + Brave Tech) com extração direta de soluções e blocos de código.
- rusya_read_documentation: (Especial Claude Code) Pesquisa e lê a documentação oficial de bibliotecas/APIs devolvendo apenas blocos de código e tabelas de referência.
- rusya_spellcheck_and_suggest: Autocompletar em tempo real e correção ortográfica (Svelte AST) para verificação de nomes de pacotes e intenções.
- rusya_search: Pesquisa multi-fonte (Brave Supreme Primário, Reddit, GitHub, arXiv, StackOverflow, etc.) com filtro de data e domínio.
- rusya_search_reddit: Pesquisa em tempo real no Reddit com nosso motor nativo autônomo sem CAPTCHA.
- rusya_search_images: Pesquisa de imagens (.jpg, .png, .svg) e thumbnails com links diretos HD.
- rusya_search_icons: Ícones transparentes e logos de marcas prontas para tags <img src="...">.
- rusya_browse: Entra em qualquer URL da web e converte para Markdown limpo otimizado para tokens.
- rusya_universal_access: Acessa URLs restritas ou complexas via Matriz Universal Quad-Tier.
- rusya_extract: Extrai tabelas, listas, links, imagens ou OCR completo de PDFs.
- rusya_research: Deep Research consolidando navegação paralela de Top N páginas num Dossiê MD.
- rusya_google_research: Pesquisa e acessa diretamente os links retornados pelo Google em Markdown.
- rusya_scholar: Artigos científicos, PDFs acadêmicos e citações técnicas no Scholar/arXiv.
- rusya_smart_dork: Constrói e executa Google Dorks avançados para auditoria e investigação.
"""

import asyncio
import json
import sys
import argparse
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

from core.search_engines import MetaSearchEngine, BraveSearcher
from core.browser import AgentBrowser, BrowseOptions
from core.extractor import MarkdownExtractor
from core.crawler import Crawler

# Inicializa o servidor FastMCP
mcp = FastMCP("RusyaSearch Supreme")


def _get_attr(item: Any, key: str, default: Any = "") -> Any:
    """Extrai atributo de forma segura tanto de dicionário quanto de objeto SearchResult."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


@mcp.tool()
async def rusya_code_solve(
    error_message_or_question: str,
    language: str = "python",
    max_solutions: int = 4
) -> str:
    """
    [ESPECIAL CLAUDE CODE & IDEs] Solucionador Rápido de Erros e Bugs de Código.
    Realiza busca cruzada e extração em paralelo no StackOverflow (com corpo e código da resposta aceita),
    GitHub Issues e Brave Tech Supreme, devolvendo blocos de código prontos para copiar e aplicar.

    Parâmetros:
    - error_message_or_question: A mensagem de erro (traceback) ou dúvida técnica exata.
    - language: Linguagem ou framework (ex: 'python', 'rust', 'nextjs', 'fastapi').
    - max_solutions: Quantidade de soluções comentadas a extrair (padrão: 4).
    """
    q_tech = f"{error_message_or_question} {language} fix solution"
    
    so_task = MetaSearchEngine.search_all(query=q_tech, sources="stackoverflow", limit=max_solutions)
    gh_task = MetaSearchEngine.search_all(query=q_tech, sources="github", limit=2)
    brave_task = MetaSearchEngine.search_all(query=f"{error_message_or_question} {language}", sources="brave", limit=2)

    so_res, gh_res, brave_res = await asyncio.gather(so_task, gh_task, brave_task)
    
    all_res = so_res + gh_res + brave_res
    formatted = [f"# 🛠️ Rusya Quantum Code Solver — Diagnóstico & Solução: `{error_message_or_question}` ({language})\n"]
    seen_urls = set()
    count = 0

    for r in all_res:
        title = _get_attr(r, "title")
        url = _get_attr(r, "url")
        desc = _get_attr(r, "description")
        source = _get_attr(r, "source", "Tech Search")

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        count += 1

        # Se for do StackOverflow novo, desc já traz a resposta completa em Markdown e código!
        if "StackOverflow Aceita" in source or "StackOverflow Resposta" in source or "```" in desc:
            formatted.append(f"## {count}. {title}\n**Link Oficial:** [{url}]({url}) | **Fonte:** `{source}`\n\n{desc}\n")
        else:
            formatted.append(f"## {count}. {title}\n**Link Oficial:** [{url}]({url}) | **Fonte:** `{source}`\n**Resumo / Detalhes:**\n```text\n{desc[:1000]}\n```\n")

        if count >= max_solutions:
            break

    if count == 0:
        return f"Não foram encontradas soluções imediatas para `{error_message_or_question}`. Tente usar `rusya_search` com termos mais gerais."
    return "\n---\n".join(formatted)


@mcp.tool()
async def rusya_read_documentation(
    package_or_topic: str,
    browse_page: bool = True
) -> str:
    """
    [ESPECIAL CLAUDE CODE] Leitor Cirúrgico de Documentação e Referência de APIs.
    Localiza a documentação oficial da biblioteca ou tecnologia e, se browse_page=True,
    acessa a página de referência extraindo preferencialmente tabelas, construtores,
    assinaturas de funções e blocos de código em Markdown limpo.

    Parâmetros:
    - package_or_topic: Nome da biblioteca e módulo (ex: 'pydantic v2 BaseSettings', 'sveltekit load function docs').
    - browse_page: Se True, entra automaticamente na página da doc principal e extrai o conteúdo (padrão: True).
    """
    q_docs = f"{package_or_topic} official documentation API reference"
    search_res = await MetaSearchEngine.search_all(q_docs, sources="web", limit=3)

    if not search_res:
        return f"Documentação oficial não encontrada para '{package_or_topic}'."

    top_doc = search_res[0]
    title = _get_attr(top_doc, "title")
    url = _get_attr(top_doc, "url")
    desc = _get_attr(top_doc, "description")

    out = [f"# 📚 Referência de Documentação: {package_or_topic}\n**Página Principal:** [{title}]({url})\n**Resumo Indexado:** {desc}\n"]

    if browse_page and url:
        try:
            from core.agent_tools import AgentToolsService
            res = await AgentToolsService.universal_browse(url, max_chars=12000)
            md = res.get("markdown", "")
            out.append(f"\n## Conteúdo da Documentação em Markdown:\n\n{md}")
        except Exception as e:
            out.append(f"\n*Aviso: Não foi possível navegar no link ({str(e)}). Use o resumo acima ou acesse o link via rusya_browse.*")

    return "\n".join(out)


@mcp.tool()
async def rusya_spellcheck_and_suggest(query: str) -> str:
    """
    Verificação ortográfica imediata de comandos/bibliotecas (via Svelte AST do Brave)
    e expansão de sugestões em tempo real. Ideal para agentes checarem nomes corretos
    de pacotes antes de instalar ou buscar.
    """
    from core.search_engines import GoogleSuggestSearcher
    # Teste de busca no Brave para ver se há sugestão de correção AST
    brave_res = await BraveSearcher.search(query, limit=2)
    spell_msg = ""
    for r in brave_res:
        t = _get_attr(r, "title")
        if "Correção Ortográfica" in t or "Spellcheck" in _get_attr(r, "source"):
            spell_msg = f"✨ **Correção Ortográfica AST Detectada:** `{t}`\n   - Detalhes: {_get_attr(r, 'description')}\n\n"
            break

    suggestions = await GoogleSuggestSearcher.suggest(query)
    formatted = [f"- `{s}`" for s in suggestions[:12]]
    return f"{spell_msg}### Sugestões e Variações em Tempo Real para '{query}' ({len(suggestions)}):\n\n" + "\n".join(formatted)


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
    Pesquisa multi-fonte primária (Brave Supreme v9.0, Reddit, GitHub, arXiv, StackOverflow ou Base Local).

    Parâmetros:
    - query: Tópico de pesquisa.
    - sources: "all", "web", "reddit", "arxiv", "github", "stackoverflow", "local".
    - max_results: Quantidade máxima de resultados (padrão: 15).
    - domain: Filtrar por site específico (ex: 'github.com' ou 'reddit.com/r/Python').
    - time_range: Filtro de tempo ('pd' 24h, 'pw' semana, 'pm' mês, 'py' ano).
    - lang: Idioma ('pt', 'en', etc.).
    """
    results = await MetaSearchEngine.search_all(
        query=query,
        sources=sources,
        limit=max_results,
        domain=domain,
        time_range=time_range,
        lang=lang
    )
    formatted = []
    for idx, r in enumerate(results, 1):
        title = _get_attr(r, "title")
        url = _get_attr(r, "url")
        source = _get_attr(r, "source", "Brave Supreme")
        desc = _get_attr(r, "description")
        formatted.append(f"{idx}. **[{title}]({url})** `[{source}]`\n   {desc}")
    return f"### Resultados da Busca ({len(results)}):\n\n" + "\n\n".join(formatted)


@mcp.tool()
async def rusya_search_reddit(
    query: str,
    subreddit: str = "",
    limit: int = 15
) -> str:
    """
    Pesquisa em tempo real de discussões, opiniões da comunidade e dúvidas no Reddit.
    Utiliza motor nativo anti-bot (Playwright Chromium + .json bypass), sem CAPTCHAs.

    Parâmetros:
    - query: Termo pesquisado no Reddit.
    - subreddit: Nome opcional do subreddit (ex: 'Python', 'MachineLearning', 'brasil').
    - limit: Número máximo de postagens (padrão: 15).
    """
    from core.search_engines import RedditSearcher
    domain_arg = f"reddit.com/r/{subreddit}" if subreddit else ""
    results = await RedditSearcher.search(query=query, limit=limit, domain=domain_arg)
    formatted = []
    for idx, r in enumerate(results, 1):
        title = _get_attr(r, "title")
        url = _get_attr(r, "url")
        source = _get_attr(r, "source", "Reddit")
        desc = _get_attr(r, "description")
        formatted.append(f"{idx}. **[{title}]({url})** `[{source}]`\n   {desc}")
    return f"### Discussões no Reddit ({len(results)}):\n\n" + "\n\n".join(formatted) if formatted else "Nenhuma discussão encontrada no Reddit."


@mcp.tool()
async def rusya_search_images(
    query: str,
    limit: int = 15
) -> str:
    """
    Pesquisa e retorna links diretos de imagens (.png, .jpg, .webp, .svg) e thumbnails HD.
    Ideal para agentes IA construindo sites ou interfaces que precisam de tags <img src="..."> reais.
    """
    from core.search_engines import ImageSearcher
    results = await ImageSearcher.search(query=query, limit=limit)
    formatted = []
    for idx, r in enumerate(results, 1):
        formatted.append(f"{idx}. **URL Direta da Imagem:** `{r.url}`\n   - Título: {r.title}\n   - Detalhes: {r.description}")
    return f"### Imagens Encontradas ({len(results)}):\n\n" + "\n\n".join(formatted) if formatted else "Nenhuma imagem encontrada."


@mcp.tool()
async def rusya_search_icons(
    query: str,
    limit: int = 15
) -> str:
    """
    Pesquisa ícones transparentes (PNG/SVG) e logos oficiais de tecnologias/marcas,
    prontos para injeção em HTML (<img src="..." />) de sistemas e dashboards.
    """
    from core.agent_tools import AgentToolsService
    res = await AgentToolsService.search_icons(query, limit=limit)
    icons = res.get("icons", [])
    if not icons:
        return f"Nenhum ícone encontrado para '{query}'."
    formatted = [f"### {idx}. {ic['title']}\n- **URL do Ícone/PNG:** {ic['url']}\n- **Snippet:** `<img src='{ic['url']}' alt='{ic['title']}' />`\n- **Fonte:** {ic['source']}" for idx, ic in enumerate(icons, 1)]
    return f"# Ícones & SVGs Encontrados ({len(icons)}):\n\n" + "\n\n---\n\n".join(formatted)


@mcp.tool()
async def rusya_browse(
    url: str,
    format: str = "markdown",
    js_render: bool = True
) -> str:
    """
    Entra em qualquer URL da web e retorna o conteúdo em Markdown limpo (.md)
    otimizado para o orçamento de tokens do LLM, sem anúncios.
    """
    options = BrowseOptions(url=url, format=format, js_render=js_render)
    res = await AgentBrowser.browse(options)
    content = res.get("content", "")
    if isinstance(content, dict):
        return json.dumps(content, indent=2, ensure_ascii=False)
    return str(content)


@mcp.tool()
async def rusya_universal_access(
    url: str,
    max_chars: int = 12000
) -> str:
    """
    Acessa qualquer URL restrita, com bloqueio agressivo ou paywall utilizando nossa Matriz Universal Quad-Tier
    (HTTPx -> Playwright Stealth -> Jina Mirror -> Wayback CDX & Google Cache).
    """
    from core.agent_tools import AgentToolsService
    res = await AgentToolsService.universal_browse(url, max_chars=max_chars)
    return f"# [Matriz Universal Quad-Tier] {res.get('title')}\n**URL:** {res.get('url')} | **Motor Acionado:** `{res.get('engine_used')}` | **Palavras:** {res.get('word_count', 0)}\n\n---\n\n{res.get('markdown')}"


@mcp.tool()
async def rusya_extract(
    url: str,
    target: str = "tables"
) -> str:
    """
    Extrai dados estruturados específicos de uma página ou realiza OCR de arquivo PDF.
    Alvos: 'tables', 'lists', 'links', 'images', 'pdf_ocr'.
    """
    import httpx
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": "RusyaSearch-MCP/3.0"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        if target == "pdf_ocr" or url.lower().endswith(".pdf"):
            try:
                import io
                import pypdf
                pdf = pypdf.PdfReader(io.BytesIO(resp.content))
                text = [f"## Página {idx}\n{page.extract_text().strip()}" for idx, page in enumerate(pdf.pages, 1) if page.extract_text()]
                return f"# OCR do PDF: {url}\n\n" + "\n\n".join(text)
            except Exception as e:
                return f"Erro na extração de PDF: {str(e)}"

        html = resp.text
        if target == "tables":
            tables = MarkdownExtractor.extract_tables(html, base_url=url)
            return f"### Tabelas Extraídas ({len(tables)}):\n\n" + "\n\n---\n\n".join([t["markdown"] for t in tables])
        elif target == "lists":
            lists = MarkdownExtractor.extract_lists(html, base_url=url)
            return f"### Listas Extraídas ({len(lists)}):\n\n" + "\n\n---\n\n".join(["\n".join(l["items"]) for l in lists])
        elif target == "links":
            links = MarkdownExtractor.extract_links(html, base_url=url)
            return f"### Principais Links ({len(links)}):\n\n" + "\n".join([f"- [{l['text']}]({l['href']})" for l in links[:50]])
        elif target == "images":
            images = MarkdownExtractor.extract_images(html, base_url=url)
            return f"### Imagens Extraídas ({len(images)}):\n\n" + "\n\n".join([f"![{img['alt']}]({img['src']})" for img in images[:30]])
        else:
            extracted = MarkdownExtractor.extract(html, url=url)
            return extracted.markdown_with_frontmatter


@mcp.tool()
async def rusya_research(
    query: str,
    browse_top_n: int = 2
) -> str:
    """
    Agente de Deep Research: pesquisa sobre um tema e ENTRA em paralelo nas Top N páginas,
    consolidando tudo num Dossiê Markdown profundo.
    """
    search_results = await MetaSearchEngine.search_all(query, sources="all", limit=max(10, browse_top_n * 2))
    top_results = search_results[:browse_top_n]

    dossier_lines = [
        f"# Dossiê de Pesquisa AI: {query}\n",
        f"**Páginas Navegadas:** {len(top_results)}\n",
        "## 1. Resumo dos Resultados:\n"
    ]
    for idx, r in enumerate(top_results, 1):
        title = _get_attr(r, "title")
        url = _get_attr(r, "url")
        desc = _get_attr(r, "description")
        dossier_lines.append(f"{idx}. **[{title}]({url})** — {desc}")

    dossier_lines.append("\n---\n## 2. Conteúdo em Markdown das Páginas Navegadas\n")

    for r in top_results:
        url = _get_attr(r, "url")
        title = _get_attr(r, "title")
        try:
            page_res = await AgentBrowser.browse(BrowseOptions(url=url, format="markdown"))
            content = page_res.get("content", "")
            dossier_lines.append(f"### {title}\n**URL:** {url}\n\n{content}\n---\n")
        except Exception as e:
            dossier_lines.append(f"### {title}\n**URL:** {url}\n\nErro ao navegar: {str(e)}\n---\n")

    return "\n".join(dossier_lines)


@mcp.tool()
async def rusya_google_research(
    query: str,
    browse_top_n: int = 2
) -> str:
    """
    Pesquisa e ENTRA nos links retornados entregando o conteúdo integral dos sites em Markdown.
    """
    search_results = await MetaSearchEngine.search_all(query, sources="web", limit=browse_top_n)
    pages_md = []
    for r in search_results[:browse_top_n]:
        url = _get_attr(r, "url")
        title = _get_attr(r, "title")
        try:
            page_res = await AgentBrowser.browse(BrowseOptions(url=url, format="markdown"))
            content = page_res.get("content", "")
            pages_md.append(f"## {title}\n**URL:** {url}\n\n{content}")
        except Exception as e:
            pages_md.append(f"## {title}\n**URL:** {url}\n\nErro ao acessar: {str(e)}")

    return f"# Pesquisa Web & Acesso Aos Links: {query}\n\n" + "\n\n---\n\n".join(pages_md)


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
    """
    from core.search_engines import SmartDorkBuilder
    dork_query = SmartDorkBuilder.build_dork(intent, domain=domain, filetype=filetype, inurl=inurl)
    results = await MetaSearchEngine.search_all(dork_query, sources="web", limit=15)
    formatted = []
    for idx, r in enumerate(results, 1):
        title = _get_attr(r, "title")
        url = _get_attr(r, "url")
        desc = _get_attr(r, "description")
        formatted.append(f"{idx}. **[{title}]({url})**\n   {desc}")
    return f"### Google Dork Executado: `{dork_query}` ({len(results)} resultados):\n\n" + "\n\n".join(formatted)


def main():
    parser = argparse.ArgumentParser(description="RusyaSearch 3.0 Supreme MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Modo de transporte MCP (padrão: stdio)")
    parser.add_argument("--port", type=int, default=8081, help="Porta para o servidor SSE (se transport=sse)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host para o servidor SSE")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"🚀 Iniciando RusyaSearch MCP Server em modo SSE na porta {args.port}...")
        mcp.settings.port = args.port
        mcp.settings.host = args.host
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
