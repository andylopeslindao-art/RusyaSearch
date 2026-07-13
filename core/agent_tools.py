import asyncio
import time
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field

from core.search_engines import MetaSearchEngine
from core.extractor import MarkdownExtractor
from core.indexer import InvertedIndex


class AgentSearchRequest(BaseModel):
    query: str = Field(..., description="A consulta de pesquisa web para o agente de IA")
    max_results: int = Field(5, ge=1, le=20, description="Número máximo de resultados")
    sources: str = Field("all", description="Fonte: all, web, wiki, tech, local")


class AgentBrowseRequest(BaseModel):
    url: str = Field(..., description="URL da página web para visitar e extrair em Markdown")
    max_chars: int = Field(8000, ge=500, le=50000, description="Limite máximo de caracteres no Markdown para caber no contexto do LLM")
    include_links: bool = Field(True, description="Incluir lista de links encontrados na página")


class AgentResearchRequest(BaseModel):
    query: str = Field(..., description="A consulta ou tópico que o agente deseja pesquisar a fundo")
    num_results: int = Field(5, ge=1, le=15, description="Quantidade de resultados na busca")
    browse_top_n: int = Field(2, ge=1, le=5, description="Entrar automaticamente nas N primeiras páginas e extrair o Markdown completo")
    max_chars_per_page: int = Field(5000, ge=1000, le=20000, description="Orçamento de caracteres por página navegada")


class AgentToolsService:
    """
    Serviço especializado para Agentes de Inteligência Artificial (LLMs, LangChain, OpenAI, Claude, CrewAI).
    Pesquisa no Google/Web, entra em páginas, extrai Markdown otimizado para tokens.
    """

    @staticmethod
    def trim_markdown(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        trimmed = text[:max_chars]
        # Try to cut at the last paragraph break
        last_n = trimmed.rfind("\n\n")
        if last_n > max_chars * 0.6:
            trimmed = trimmed[:last_n]
        return trimmed + f"\n\n... [Truncado para o limite do agente: {max_chars} caracteres] ..."

    @classmethod
    async def search(cls, req: AgentSearchRequest, local_index: Optional[InvertedIndex] = None) -> Dict[str, Any]:
        results = await MetaSearchEngine.search_all(
            query=req.query,
            local_index=local_index,
            sources=req.sources,
            limit=req.max_results
        )

        formatted_results = []
        for i, r in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
                "source": r.get("source", "Web")
            })

        return {
            "query": req.query,
            "total_results": len(formatted_results),
            "results": formatted_results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    async def browse(cls, req: AgentBrowseRequest) -> Dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RusyaSearchAgent/2.0; +https://github.com/rusya)"}
        ) as client:
            resp = await client.get(req.url)
            resp.raise_for_status()

            extracted = MarkdownExtractor.extract(resp.text, url=req.url)
            markdown_content = cls.trim_markdown(extracted.markdown, req.max_chars)

            res = {
                "url": req.url,
                "title": extracted.title,
                "description": extracted.description,
                "word_count": extracted.word_count,
                "reading_time_min": extracted.reading_time_min,
                "markdown": markdown_content
            }
            if req.include_links:
                res["links"] = extracted.links[:30]
            return res

    @classmethod
    async def research(cls, req: AgentResearchRequest, local_index: Optional[InvertedIndex] = None) -> Dict[str, Any]:
        """
        O super-comando para agentes:
        1. Pesquisa na web.
        2. Entra nas Top N páginas concorrentemente.
        3. Converte tudo para Markdown estruturado no limite de tokens.
        """
        search_results = await MetaSearchEngine.search_all(
            query=req.query,
            local_index=local_index,
            sources="all",
            limit=req.num_results
        )

        urls_to_browse = [r["url"] for r in search_results[:req.browse_top_n] if r.get("url")]

        async def fetch_one(url: str):
            try:
                b_req = AgentBrowseRequest(url=url, max_chars=req.max_chars_per_page, include_links=False)
                return await cls.browse(b_req)
            except Exception as e:
                return {"url": url, "error": str(e), "markdown": ""}

        browsed_pages = await asyncio.gather(*(fetch_one(u) for u in urls_to_browse))

        # Build combined research dossier in clean Markdown
        dossier_lines = [
            f"# Dossiê de Pesquisa AI: {req.query}",
            f"**Data:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Páginas Navegadas:** {len(browsed_pages)}",
            "",
            "## 1. Visão Geral dos Resultados da Busca",
            ""
        ]

        for i, r in enumerate(search_results, 1):
            dossier_lines.append(f"{i}. **[{r.get('title')}]({r.get('url')})** — {r.get('description')}")

        dossier_lines.extend(["", "---", "", "## 2. Conteúdo em Markdown das Páginas Navegadas", ""])

        for page in browsed_pages:
            if page.get("error"):
                continue
            dossier_lines.extend([
                f"### {page.get('title', page.get('url'))}",
                f"**URL:** {page.get('url')} | **Palavras:** {page.get('word_count', 0)}",
                "",
                page.get("markdown", "")[:req.max_chars_per_page],
                "",
                "---",
                ""
            ])

        dossier_md = "\n".join(dossier_lines)

        return {
            "query": req.query,
            "search_results": search_results,
            "browsed_pages": browsed_pages,
            "consolidated_dossier_markdown": dossier_md
        }

    @classmethod
    def get_agent_tools_schema(cls) -> Dict[str, Any]:
        """
        Retorna as definições de schemas de ferramentas prontas para OpenAI, Claude, LangChain e MCP.
        """
        return {
            "openai_functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_search",
                        "description": "Pesquisa na web (Google/DuckDuckGo/Wikipédia/Tech) e retorna lista de resultados relevantes com título, url e resumo.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Termo de busca na web"},
                                "max_results": {"type": "integer", "default": 5, "description": "Quantidade de resultados"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_browse",
                        "description": "Entra em uma URL específica e retorna o conteúdo limpo e extraído em Markdown (.md).",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "URL da página para navegar"},
                                "max_chars": {"type": "integer", "default": 8000, "description": "Limite de caracteres de Markdown"}
                            },
                            "required": ["url"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_research",
                        "description": "Pesquisa na web E navega automaticamente nas Top N páginas, retornando um dossiê consolidado em Markdown.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Tópico da pesquisa completa"},
                                "browse_top_n": {"type": "integer", "default": 2, "description": "Quantidade de páginas para entrar e ler em Markdown"}
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            "langchain_python_snippet": """
# Exemplo LangChain / CrewAI / Python SDK para Agentes de IA
import httpx

class RusyaSearchAgent:
    BASE_URL = "http://localhost:8080/api/v1/agent"

    @classmethod
    def search(cls, query: str, max_results: int = 5):
        return httpx.post(f"{cls.BASE_URL}/search", json={"query": query, "max_results": max_results}).json()

    @classmethod
    def browse(cls, url: str, max_chars: int = 8000):
        return httpx.post(f"{cls.BASE_URL}/browse", json={"url": url, "max_chars": max_chars}).json()

    @classmethod
    def research(cls, query: str, browse_top_n: int = 2):
        return httpx.post(f"{cls.BASE_URL}/research", json={"query": query, "browse_top_n": browse_top_n}).json()
"""
        }
