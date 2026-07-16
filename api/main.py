import os
import re
import time
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.crawler import Crawler
from core.indexer import InvertedIndex
from core.extractor import MarkdownExtractor
from core.search_engines import MetaSearchEngine
from core.browser import AgentBrowser, BrowseOptions
from core.knowledge_graph import KnowledgeGraphEngine
from api.agent_router import router as agent_router

INDEX_PATH = os.path.expanduser("~/.rusyasearch/index.json")
CRAWL_STATUS: dict = {
    "running": False,
    "pages": 0,
    "total": 0,
    "last_url": "",
    "start_time": 0.0
}


async def background_crawl(
    seed_url: str,
    max_pages: int = 100,
    max_depth: int = 3,
    concurrency: int = 4,
    respect_robots: bool = True
):
    CRAWL_STATUS["running"] = True
    CRAWL_STATUS["pages"] = 0
    CRAWL_STATUS["total"] = max_pages
    CRAWL_STATUS["start_time"] = time.time()

    crawler = Crawler(
        max_pages=max_pages,
        max_depth=max_depth,
        concurrency=concurrency,
        delay=0.2,
        respect_robots=respect_robots
    )

    def progress(url, count):
        CRAWL_STATUS["pages"] = count
        CRAWL_STATUS["last_url"] = url

    pages = await crawler.crawl(seed_url, callback=progress)

    idx = InvertedIndex.load(INDEX_PATH) if os.path.exists(INDEX_PATH) else InvertedIndex()
    for page in pages:
        idx.add_document(
            url=page.url,
            title=page.title,
            content=page.content,
            description=page.description,
            markdown=page.markdown,
            word_count=page.word_count,
            reading_time_min=page.reading_time_min
        )
        # Auto-ingest into Knowledge Graph
        try:
            KnowledgeGraphEngine.ingest_page(page.title, page.content, page.url, page.markdown)
        except Exception:
            pass
    idx.save(INDEX_PATH)
    CRAWL_STATUS["running"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    if not os.path.exists(INDEX_PATH):
        InvertedIndex().save(INDEX_PATH)
    yield


app = FastAPI(title="RusyaSearch 2.0 API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)

static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root(request: Request):
    accept = request.headers.get("accept", "").lower()
    if "application/json" in accept and not "text/html" in accept:
        return {
            "status": "online",
            "system": "RusyaSearch 3.0 — AI Agent Core Suite",
            "description": "Universal AI Agent API & MCP Server with Quad-Tier Anti-Bot Bypass",
            "version": "3.0.0",
            "engines": [
                "Tier 1: HTTPx Stealth Fast Rotation",
                "Tier 2: Playwright Chromium + WebGL & GPU Spoofing + Cookie Auto-Clicker",
                "Tier 3: Jina AI Mirror Fallback",
                "Tier 4: Universal Wayback CDX & Google Cache Matrix"
            ],
            "endpoints": {
                "agent_search": "POST /api/v1/agent/search",
                "agent_icons": "GET /api/v1/agent/icons",
                "agent_browse": "POST /api/v1/agent/browse",
                "agent_universal_browse": "POST /api/v1/agent/universal_browse",
                "agent_research": "POST /api/v1/agent/research",
                "agent_tools_schema": "GET /api/v1/agent/tools_schema",
                "swagger_docs": "GET /docs"
            }
        }
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def api_status():
    return {
        "status": "active",
        "name": "RusyaSearch 3.0 Agent Core",
        "version": "3.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/api/search")
async def search(
    q: str = Query(..., description="Search query"),
    source: str = Query("all", description="Filter source: all, web, reddit, wiki, tech, local"),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1, description="Página de resultados (1, 2, 3...)")
):
    idx = InvertedIndex.load(INDEX_PATH) if os.path.exists(INDEX_PATH) else None

    if source == "local":
        if not idx:
            return {"results": [], "total": 0, "query": q, "source": source, "page": page}
        all_local = idx.search(q, limit=limit * page)
        start_idx = (page - 1) * limit
        page_results = all_local[start_idx : start_idx + limit]
        return {
            "results": page_results,
            "total": len(page_results),
            "query": q,
            "source": source,
            "page": page
        }

    results = await MetaSearchEngine.search_all(
        query=q,
        local_index=idx,
        sources=source,
        limit=limit,
        page=page
    )

    return {
        "results": results,
        "total": len(results),
        "query": q,
        "source": source,
        "page": page
    }


class ExtractRequest(BaseModel):
    url: str


@app.get("/api/extract")
async def extract_url_get(url: str = Query(..., description="URL to extract to Markdown")):
    return await _extract_url_logic(url)


@app.post("/api/extract")
async def extract_url_post(req: ExtractRequest):
    return await _extract_url_logic(req.url)


async def _extract_url_logic(url: str):
    # First check if we already have it in local index
    if os.path.exists(INDEX_PATH):
        idx = InvertedIndex.load(INDEX_PATH)
        for doc_id, entry in idx.documents.items():
            if entry.url == url and entry.markdown:
                return {
                    "url": entry.url,
                    "title": entry.title,
                    "description": entry.description,
                    "markdown": entry.markdown,
                    "word_count": entry.word_count,
                    "reading_time_min": entry.reading_time_min,
                    "cached": True
                }

    # Se for URL do Reddit, usa diretamente o motor anti-bot do AgentBrowser
    if "reddit.com" in url.lower() or "redd.it" in url.lower():
        try:
            b_res = await AgentBrowser.browse(BrowseOptions(url=url, format="markdown"))
            return {
                "url": url,
                "title": b_res.get("title", url),
                "description": b_res.get("description", ""),
                "markdown": b_res.get("content", ""),
                "word_count": b_res.get("word_count", 0),
                "reading_time_min": b_res.get("reading_time_min", 1),
                "cached": False
            }
        except Exception:
            pass

    # Fetch live web page and extract clean Markdown
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RusyaSearch/2.0; +https://github.com/rusya)"
            }
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            extracted = MarkdownExtractor.extract(resp.text, url=url)
            return {
                "url": url,
                "title": extracted.title,
                "description": extracted.description,
                "markdown": extracted.markdown,
                "word_count": extracted.word_count,
                "reading_time_min": extracted.reading_time_min,
                "cached": False
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao extrair URL: {str(e)}")


@app.get("/api/download/md")
async def download_markdown(url: str = Query(..., description="URL to download as .md file")):
    res = await _extract_url_logic(url)
    title = res.get("title", "documento")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", title)[:60].strip("-") or "documento"
    filename = f"{safe_name}.md"

    return Response(
        content=res["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/export/search.md")
async def export_search_markdown(
    q: str = Query(..., description="Search query to export"),
    source: str = Query("all", description="Source filter")
):
    idx = InvertedIndex.load(INDEX_PATH) if os.path.exists(INDEX_PATH) else None
    results = await MetaSearchEngine.search_all(q, local_index=idx, sources=source, limit=25)

    lines = [
        f"# Relatório de Pesquisa RusyaSearch: {q}",
        f"**Fonte:** {source.upper()} | **Total de Resultados:** {len(results)} | **Data:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        ""
    ]

    for i, r in enumerate(results, 1):
        title = r.get("title", "Sem Título")
        url = r.get("url", "")
        desc = r.get("description", "Sem descrição.")
        src = r.get("source", "Web")

        lines.extend([
            f"## {i}. {title}",
            f"- **URL:** [{url}]({url})",
            f"- **Fonte:** {src}",
            "",
            f"{desc}",
            "",
            "---",
            ""
        ])

    md_content = "\n".join(lines)
    safe_q = re.sub(r"[^a-zA-Z0-9_-]", "-", q)[:40].strip("-") or "pesquisa"
    filename = f"rusyasearch-{safe_q}.md"

    return Response(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/api/crawl")
async def start_crawl(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Seed URL to crawl"),
    max_pages: int = Query(50, ge=1, le=500),
):
    if CRAWL_STATUS["running"]:
        return {"error": "Crawl already in progress", "status": CRAWL_STATUS}

    background_tasks.add_task(background_crawl, url, max_pages)
    return {"message": "Crawl started", "seed": url, "max_pages": max_pages}


@app.get("/api/crawl/status")
async def crawl_status():
    return CRAWL_STATUS


@app.get("/api/stats")
async def stats():
    if not os.path.exists(INDEX_PATH):
        return {"documents": 0, "unique_terms": 0, "index_size": 0}

    idx = InvertedIndex.load(INDEX_PATH)
    return {
        "documents": idx.doc_count,
        "unique_terms": len(idx.index),
        "index_size": os.path.getsize(INDEX_PATH),
    }


@app.delete("/api/index")
async def clear_index():
    InvertedIndex().save(INDEX_PATH)
    return {"message": "Index cleared"}


# ── Knowledge Graph Endpoints ──────────────────────────────────────────────────

@app.get("/api/graph")
async def get_knowledge_graph(
    min_weight: int = Query(1, ge=1, description="Peso minimo da aresta"),
    max_nodes: int = Query(150, ge=10, le=500, description="Maximo de nos no grafo")
):
    return KnowledgeGraphEngine.get_graph_for_viz(min_weight=min_weight, max_nodes=max_nodes)


@app.get("/api/graph/entity/{entity_id}")
async def get_entity_detail(entity_id: str):
    detail = KnowledgeGraphEngine.get_entity_detail(entity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Entidade nao encontrada no grafo")
    return detail


@app.get("/api/graph/search")
async def search_graph_entities(
    q: str = Query(..., description="Busca por entidade no grafo"),
    limit: int = Query(20, ge=1, le=100)
):
    return KnowledgeGraphEngine.search_entities(q, limit=limit)


@app.post("/api/graph/ingest")
async def ingest_text_to_graph(
    text: str = Query(..., description="Texto para extrair entidades e relacoes"),
    source_url: str = Query("", description="URL de origem do texto")
):
    return KnowledgeGraphEngine.ingest_text(text, source_url=source_url)


@app.delete("/api/graph")
async def clear_knowledge_graph():
    KnowledgeGraphEngine.clear()
    return {"message": "Knowledge Graph cleared"}


@app.get("/api/graph/stats")
async def graph_stats():
    graph = KnowledgeGraphEngine.load()
    entities = graph.get("entities", {})
    relations = graph.get("relations", [])
    from collections import Counter
    type_counts = Counter(e.get("type", "unknown") for e in entities.values())
    return {
        "total_entities": len(entities),
        "total_relations": len(relations),
        "entity_type_distribution": dict(type_counts),
        "last_updated": graph.get("last_updated", 0)
    }
