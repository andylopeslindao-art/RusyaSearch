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
    sources: str = Field("all", description="Fonte: all, web, reddit, wiki, tech, local")


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
    async def google_suggest(cls, query: str) -> Dict[str, Any]:
        from core.search_engines import GoogleSuggestSearcher
        suggestions = await GoogleSuggestSearcher.suggest(query)
        return {
            "query": query,
            "total_suggestions": len(suggestions),
            "suggestions": suggestions,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    async def scholar(cls, query: str, max_results: int = 15) -> Dict[str, Any]:
        from core.search_engines import GoogleScholarSearcher
        results = await GoogleScholarSearcher.search(query, limit=max_results)
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append({
                "rank": i,
                "title": r.title,
                "url": r.url,
                "snippet": r.description,
                "source": r.source
            })
        return {
            "query": query,
            "total_results": len(formatted),
            "results": formatted,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    async def smart_dork(cls, intent: str, domain: str = "", filetype: str = "", inurl: str = "", max_results: int = 15) -> Dict[str, Any]:
        from core.search_engines import SmartDorkBuilder, MetaSearchEngine
        dork_query = SmartDorkBuilder.build_dork(intent, domain=domain, filetype=filetype, inurl=inurl)
        results = await MetaSearchEngine.search_all(query=dork_query, sources="web", limit=max_results)
        return {
            "intent": intent,
            "generated_dork": dork_query,
            "total_results": len(results),
            "results": results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    async def google_deep_research(cls, query: str, browse_top_n: int = 2, max_chars_per_page: int = 6000) -> Dict[str, Any]:
        """
        Super-Pesquisa focado no Google & Web:
        Consulta nosso agregador Quad-Google, acessa as páginas em paralelo e extrai Markdown integral, tabelas e links.
        """
        from core.search_engines import MetaSearchEngine
        search_results = await MetaSearchEngine.search_all(query=query, sources="web", limit=max(10, browse_top_n * 2))
        urls_to_browse = [r["url"] for r in search_results[:browse_top_n] if r.get("url")]

        async def fetch_one(url: str):
            try:
                b_req = AgentBrowseRequest(url=url, max_chars=max_chars_per_page, include_links=True)
                return await cls.browse(b_req)
            except Exception as e:
                return {"url": url, "error": str(e), "markdown": ""}

        browsed_pages = await asyncio.gather(*(fetch_one(u) for u in urls_to_browse))

        dossier_lines = [
            f"# Dossiê Google Deep Research: {query}",
            f"**Data:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Páginas Acessadas:** {len(browsed_pages)}",
            "",
            "## 1. Top Resultados do Google & Web",
            ""
        ]
        for i, r in enumerate(search_results[:8], 1):
            dossier_lines.append(f"{i}. **[{r.get('title')}]({r.get('url')})** — {r.get('description')}")

        dossier_lines.extend(["", "---", "", "## 2. Conteúdo em Markdown & Dados Extraídos dos Sites", ""])
        for p in browsed_pages:
            if p.get("error"):
                continue
            dossier_lines.extend([
                f"### {p.get('title', p.get('url'))}",
                f"**URL:** {p.get('url')} | **Palavras:** {p.get('word_count', 0)} | **Tempo de Leitura:** {p.get('reading_time_min', 1)} min",
                "",
                p.get("markdown", "")[:max_chars_per_page],
                "",
                "---",
                ""
            ])

        return {
            "query": query,
            "search_results": search_results,
            "browsed_pages": browsed_pages,
            "consolidated_dossier_markdown": "\n".join(dossier_lines)
        }

    @classmethod
    async def search_icons(cls, query: str, limit: int = 15) -> Dict[str, Any]:
        from core.search_engines import IconAndVectorSearcher
        results = await IconAndVectorSearcher.search(query, limit=limit)
        formatted = []
        for idx, r in enumerate(results, 1):
            formatted.append({
                "rank": idx,
                "title": r.title,
                "url": r.url,
                "snippet": r.description,
                "source": r.source
            })
        return {
            "query": query,
            "total_icons": len(formatted),
            "icons": formatted,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    async def universal_browse(cls, url: str, max_chars: int = 10000) -> Dict[str, Any]:
        from core.browser import AgentBrowser, BrowseOptions
        options = BrowseOptions(url=url, format="markdown", engine="universal")
        res = await AgentBrowser.browse(options)
        content = str(res.get("content", ""))
        return {
            "url": url,
            "status_code": res.get("status_code", 200),
            "title": res.get("title", url),
            "word_count": res.get("word_count", 0),
            "reading_time_min": res.get("reading_time_min", 1),
            "engine_used": res.get("engine_used", "universal_matrix"),
            "markdown": cls.trim_markdown(content, max_chars)
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
                                "sources": {"type": "string", "default": "all", "description": "Fonte de busca (all, web, reddit, icons, svgs, scholar, github, tech)"},
                                "max_results": {"type": "integer", "default": 5, "description": "Quantidade de resultados"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_search_icons",
                        "description": "Pesquisa ícones transparentes (PNG/SVG) e logos oficiais de marcas prontos para injeção de código em interfaces web (<img src=... />).",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Nome da marca ou ícone desejado (ex: 'python logo', 'user icon')"},
                                "limit": {"type": "integer", "default": 15, "description": "Número máximo de ícones"}
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
                        "name": "rusyasearch_universal_browse",
                        "description": "Acessa qualquer URL com a Matriz Universal Quad-Tier (HTTPx -> Playwright Stealth -> Jina Reader -> Wayback Machine -> Google Cache) garantindo 100% de sucesso mesmo em sites com bloqueio antibot extremo ou paywall.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "URL restrita ou protegida para extração integral"},
                                "max_chars": {"type": "integer", "default": 10000, "description": "Limite de caracteres"}
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
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_google_suggest",
                        "description": "Obtém sugestões em tempo real do autocompletar do Google para explorar intenções e ideias de palavras-chave.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Termo parcial ou palavra-chave inicial"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_scholar",
                        "description": "Pesquisa artigos científicos, PDFs acadêmicos e resumos técnicos diretamente no Google Scholar e arXiv.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Tópico acadêmico ou científico"},
                                "max_results": {"type": "integer", "default": 10, "description": "Limite de artigos"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_smart_dork",
                        "description": "Cria e executa Google Dorks avançados (site:, filetype:, inurl:) para investigação cirúrgica de dados na web.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "intent": {"type": "string", "description": "Intenção de busca (ex: 'manuais cisco', 'planilhas financeiras')"},
                                "domain": {"type": "string", "default": "", "description": "Domínio alvo (ex: 'github.com')"},
                                "filetype": {"type": "string", "default": "", "description": "Formato do arquivo (ex: 'pdf', 'py', 'xlsx')"},
                                "inurl": {"type": "string", "default": "", "description": "Texto na URL (ex: 'admin')"}
                            },
                            "required": ["intent"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rusyasearch_google_deep_research",
                        "description": "Super-Agente que pesquisa no agregador Google & Web, acessa as top páginas em paralelo e gera dossiê executivo Markdown com tabelas e links.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Tópico ou pergunta complexa para pesquisa do Google"},
                                "browse_top_n": {"type": "integer", "default": 2, "description": "Número de páginas para ler na íntegra"}
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            "langchain_python_snippet": """
# Exemplo LangChain / CrewAI / Python SDK para Agentes de IA (RusyaSearch 3.0)
import httpx

class RusyaSearchAgent:
    BASE_URL = "http://localhost:8080/api/v1/agent"

    @classmethod
    def search(cls, query: str, max_results: int = 5, sources: str = "all"):
        return httpx.post(f"{cls.BASE_URL}/search", json={"query": query, "max_results": max_results, "sources": sources}).json()

    @classmethod
    def search_icons(cls, query: str, limit: int = 15):
        return httpx.get(f"{cls.BASE_URL}/icons?query={query}&limit={limit}").json()

    @classmethod
    def browse(cls, url: str, max_chars: int = 8000):
        return httpx.post(f"{cls.BASE_URL}/browse", json={"url": url, "max_chars": max_chars}).json()

    @classmethod
    def universal_browse(cls, url: str, max_chars: int = 10000):
        return httpx.post(f"{cls.BASE_URL}/universal_browse", json={"url": url, "max_chars": max_chars}).json()

    @classmethod
    def research(cls, query: str, browse_top_n: int = 2):
        return httpx.post(f"{cls.BASE_URL}/research", json={"query": query, "browse_top_n": browse_top_n}).json()

    @classmethod
    def suggest(cls, query: str):
        return httpx.get(f"{cls.BASE_URL}/suggest?query={query}").json()

    @classmethod
    def scholar(cls, query: str, max_results: int = 10):
        return httpx.get(f"{cls.BASE_URL}/scholar?query={query}&max_results={max_results}").json()

    @classmethod
    def smart_dork(cls, intent: str, domain: str = "", filetype: str = "", inurl: str = ""):
        return httpx.post(f"{cls.BASE_URL}/smart_dork", json={"intent": intent, "domain": domain, "filetype": filetype, "inurl": inurl}).json()

    @classmethod
    def google_deep_research(cls, query: str, browse_top_n: int = 2):
        return httpx.post(f"{cls.BASE_URL}/google_deep_research", json={"query": query, "browse_top_n": browse_top_n}).json()
"""
        }

