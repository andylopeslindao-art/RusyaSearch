import os
import httpx
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from core.agent_tools import (
    AgentToolsService,
    AgentSearchRequest,
    AgentBrowseRequest,
    AgentResearchRequest
)
from core.browser import AgentBrowser, BrowseOptions, BrowserAction
from core.extractor import MarkdownExtractor
from core.crawler import Crawler
from core.indexer import InvertedIndex

router = APIRouter(prefix="/api/v1/agent", tags=["AI Agent Suite"])
INDEX_PATH = os.path.expanduser("~/.rusyasearch/index.json")


def _get_local_index():
    return InvertedIndex.load(INDEX_PATH) if os.path.exists(INDEX_PATH) else None


class AdvancedSearchRequest(BaseModel):
    query: str = Field(..., description="Termo de pesquisa")
    sources: str = Field("all", description="Categoria: all, web, reddit, news, images, videos, pdfs, arxiv, github, stackoverflow, docs, wiki, tech, local")
    max_results: int = Field(25, ge=1, le=100)
    domain: str = Field("", description="Filtro de domínio (site:dominio.com)")
    time_range: str = Field("", description="Filtro por data (d, w, m, y)")
    lang: str = Field("pt", description="Filtro de idioma")
    region: str = Field("br", description="Filtro de país/região")
    page: int = Field(1, ge=1, description="Página de resultados (1, 2, 3...)")


@router.post("/search")
async def agent_search_post(req: AdvancedSearchRequest):
    from core.search_engines import MetaSearchEngine
    results = await MetaSearchEngine.search_all(
        query=req.query,
        local_index=_get_local_index(),
        sources=req.sources,
        limit=req.max_results,
        domain=req.domain,
        time_range=req.time_range,
        lang=req.lang,
        region=req.region,
        page=req.page
    )
    return {
        "query": req.query,
        "sources": req.sources,
        "page": req.page,
        "total": len(results),
        "results": results
    }


@router.get("/search")
async def agent_search_get(
    query: str,
    sources: str = "all",
    max_results: int = 25,
    domain: str = "",
    time_range: str = "",
    lang: str = "pt",
    region: str = "br",
    page: int = 1
):
    req = AdvancedSearchRequest(
        query=query,
        sources=sources,
        max_results=max_results,
        domain=domain,
        time_range=time_range,
        lang=lang,
        region=region,
        page=page
    )
    return await agent_search_post(req)


@router.post("/browse")
async def agent_browse_advanced_post(req: BrowseOptions):
    try:
        return await AgentBrowser.browse(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao navegar na URL: {str(e)}")


@router.get("/browse")
async def agent_browse_get(
    url: str,
    format: str = "markdown",
    js_render: bool = False,
    capture_screenshot: bool = False
):
    req = BrowseOptions(
        url=url,
        format=format,
        js_render=js_render,
        capture_screenshot=capture_screenshot
    )
    try:
        return await AgentBrowser.browse(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao navegar na URL: {str(e)}")


class ExtractStructuredRequest(BaseModel):
    url: str
    target: str = Field("markdown", description="Alvo: markdown, clean_html, text, tables, lists, links, images, pdf_ocr")


@router.post("/extract")
async def agent_extract_post(req: ExtractStructuredRequest):
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
            resp = await client.get(req.url)
            resp.raise_for_status()

            if req.target == "pdf_ocr" or req.url.lower().endswith(".pdf"):
                return MarkdownExtractor.extract_pdf_text_ocr(resp.content)

            html = resp.text
            if req.target == "tables":
                return {"url": req.url, "tables": MarkdownExtractor.extract_tables(html, req.url)}
            elif req.target == "lists":
                return {"url": req.url, "lists": MarkdownExtractor.extract_lists(html)}
            elif req.target == "links":
                return {"url": req.url, "links": MarkdownExtractor.extract_links_structured(html, req.url)}
            elif req.target == "images":
                return {"url": req.url, "images": MarkdownExtractor.extract_images_structured(html, req.url)}
            else:
                extracted = MarkdownExtractor.extract(html, url=req.url)
                return {
                    "url": req.url,
                    "title": extracted.title,
                    "word_count": extracted.word_count,
                    "reading_time_min": extracted.reading_time_min,
                    "markdown": extracted.markdown
                }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao extrair {req.target}: {str(e)}")


class AdvancedCrawlRequest(BaseModel):
    seed_url: str
    max_pages: int = Field(50, ge=1, le=500)
    max_depth: int = Field(3, ge=1, le=10)
    concurrency: int = Field(4, ge=1, le=16)
    respect_robots: bool = Field(True)


@router.post("/crawl")
async def agent_crawl_post(req: AdvancedCrawlRequest, background_tasks: BackgroundTasks):
    from api.main import background_crawl
    background_tasks.add_task(background_crawl, req.seed_url, req.max_pages, req.max_depth, req.concurrency, req.respect_robots)
    return {"message": "Crawl avançado iniciado", "seed_url": req.seed_url, "max_depth": req.max_depth, "concurrency": req.concurrency}


@router.post("/research")
async def agent_research_post(req: AgentResearchRequest):
    return await AgentToolsService.research(req, local_index=_get_local_index())


@router.get("/suggest")
async def agent_google_suggest(query: str = Query(..., description="Palavra-chave inicial")):
    return await AgentToolsService.google_suggest(query)


@router.get("/scholar")
async def agent_scholar(query: str = Query(..., description="Tópico de pesquisa científica"), max_results: int = 15):
    return await AgentToolsService.scholar(query, max_results=max_results)


class SmartDorkRequest(BaseModel):
    intent: str
    domain: str = ""
    filetype: str = ""
    inurl: str = ""
    max_results: int = 15


@router.post("/smart_dork")
async def agent_smart_dork_post(req: SmartDorkRequest):
    return await AgentToolsService.smart_dork(req.intent, domain=req.domain, filetype=req.filetype, inurl=req.inurl, max_results=req.max_results)


class GoogleDeepResearchRequest(BaseModel):
    query: str
    browse_top_n: int = Field(2, ge=1, le=6)
    max_chars_per_page: int = Field(6000, ge=1000, le=20000)


@router.post("/google_deep_research")
async def agent_google_deep_research_post(req: GoogleDeepResearchRequest):
    return await AgentToolsService.google_deep_research(req.query, browse_top_n=req.browse_top_n, max_chars_per_page=req.max_chars_per_page)


@router.get("/icons")
async def agent_search_icons(query: str = Query(..., description="Nome do ícone ou marca"), limit: int = 15):
    return await AgentToolsService.search_icons(query, limit=limit)


class UniversalBrowseRequest(BaseModel):
    url: str = Field(..., description="URL restrita para extração via Matriz Universal")
    max_chars: int = Field(10000, ge=500, le=50000)


@router.post("/universal_browse")
async def agent_universal_browse_post(req: UniversalBrowseRequest):
    return await AgentToolsService.universal_browse(req.url, max_chars=req.max_chars)


@router.get("/tools_schema")
async def agent_tools_schema():
    return AgentToolsService.get_agent_tools_schema()



