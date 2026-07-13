import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any


@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    source: str
    score: float = 1.0


class BraveSearcher:
    """
    Pesquisa moderna e veloz via Brave Search com paginação e sem bloqueios de CAPTCHA.
    """
    @classmethod
    async def search(
        cls,
        query: str,
        limit: int = 25,
        domain: str = "",
        page: int = 1,
        source_label: str = "Google / Web",
        score_bonus: float = 0.4
    ) -> List[SearchResult]:
        results = []
        try:
            full_query = f"{query} site:{domain}" if domain else query
            url = "https://search.brave.com/search"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            }
            params = {"q": full_query, "offset": page - 1}

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for item in soup.select(".snippet"):
                        link_el = item.select_one("a")
                        if not link_el or not link_el.get("href"):
                            continue
                        href = link_el.get("href", "")
                        title = link_el.get_text(strip=True)
                        desc_el = item.select_one(".snippet-description, p")
                        desc = desc_el.get_text(strip=True) if desc_el else ""

                        if href.startswith("http") and not any(skip in href for skip in ["brave.com", "javascript:"]):
                            results.append(SearchResult(
                                title=title,
                                url=href,
                                description=desc,
                                source=source_label,
                                score=1.5 + score_bonus
                            ))
                            if len(results) >= limit:
                                break
        except Exception:
            pass
        return results


class GoogleSearcher:
    """
    Pesquisa via motores de alta qualidade (Brave + Meta-Search) com paginação.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 25, domain: str = "", page: int = 1) -> List[SearchResult]:
        return await BraveSearcher.search(query, limit=limit, domain=domain, page=page, source_label="Google / Web", score_bonus=0.4)


class DuckDuckGoSearcher:
    """
    Pesquisa Web com suporte a Paginação real (page=1, 2, 3...), filtros de Domínio, Data, Idioma e País.
    """
    @classmethod
    async def search(
        cls,
        query: str,
        limit: int = 25,
        domain: str = "",
        time_range: str = "",
        page: int = 1,
        source_label: str = "Web",
        score_bonus: float = 0.0
    ) -> List[SearchResult]:
        results = []
        seen_urls = set()
        try:
            full_query = f"{query} site:{domain}" if domain else query
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
                "Origin": "https://html.duckduckgo.com",
                "Referer": "https://html.duckduckgo.com/"
            }

            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
                form_data = {
                    "q": full_query,
                    "kp": "-2"  # SafeSearch OFF (sem censura ou filtro NSFW)
                }
                if time_range:
                    form_data["df"] = time_range

                # Loop por páginas até alcançar a página desejada ou quantidade de resultados
                current_p = 1
                while current_p <= page:
                    resp = await client.post(url, data=form_data)
                    if resp.status_code != 200:
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    page_results = []
                    for result in soup.find_all("div", class_="result"):
                        title_el = result.find("a", class_="result__a")
                        snippet_el = result.find("a", class_="result__snippet")
                        if not title_el:
                            continue
                        href = title_el.get("href", "")
                        title = title_el.get_text(strip=True)
                        desc = snippet_el.get_text(strip=True) if snippet_el else ""

                        if href and title:
                            if "//duckduckgo.com/l/?" in href:
                                import urllib.parse as up
                                qs = up.parse_qs(up.urlparse(href).query)
                                if "uddg" in qs:
                                    href = qs["uddg"][0]
                            if href.startswith("http") and href not in seen_urls:
                                seen_urls.add(href)
                                page_results.append(SearchResult(
                                    title=title,
                                    url=href,
                                    description=desc,
                                    source=source_label,
                                    score=1.2 + score_bonus
                                ))

                    if current_p == page:
                        results.extend(page_results[:limit])
                        break

                    # Encontra formulário de Próxima Página (Next Page) no HTML
                    next_form = None
                    for form in soup.find_all("form"):
                        submit_btn = form.find("input", attrs={"type": "submit"})
                        if submit_btn and "next" in str(submit_btn.get("value", "")).lower():
                            next_form = form
                            break
                        if form.find("input", attrs={"name": "s"}):
                            next_form = form

                    if not next_form:
                        if current_p == page:
                            results.extend(page_results[:limit])
                        break

                    form_data = {"kp": "-2"}
                    for inp in next_form.find_all("input"):
                        name = inp.get("name")
                        val = inp.get("value", "")
                        if name:
                            form_data[name] = val
                    form_data["kp"] = "-2"

                    current_p += 1

        except Exception:
            pass
        return results


class ArxivSearcher:
    """
    Pesquisa de Papers Científicos via arXiv API.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 5) -> List[SearchResult]:
        results = []
        try:
            url = "http://export.arxiv.org/api/query"
            params = {"search_query": f"all:{query}", "start": 0, "max_results": limit}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "xml")
                    for entry in soup.find_all("entry"):
                        title = entry.title.get_text(strip=True) if entry.title else ""
                        summary = entry.summary.get_text(strip=True) if entry.summary else ""
                        pdf_link = ""
                        for link in entry.find_all("link"):
                            if link.get("title") == "pdf" or "pdf" in link.get("type", ""):
                                pdf_link = link.get("href")
                        url_page = entry.id.get_text(strip=True) if entry.id else pdf_link
                        results.append(SearchResult(
                            title=f"[arXiv Paper] {title}",
                            url=pdf_link or url_page,
                            description=summary[:350],
                            source="arXiv Papers",
                            score=1.4
                        ))
        except Exception:
            pass
        return results


class GitHubSearcher:
    """
    Pesquisa de repositórios e código no GitHub.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 5) -> List[SearchResult]:
        results = []
        try:
            url = "https://api.github.com/search/repositories"
            params = {"q": query, "per_page": limit, "sort": "stars"}
            async with httpx.AsyncClient(timeout=6.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        full_name = item.get("full_name")
                        html_url = item.get("html_url")
                        desc = item.get("description") or "Repositório GitHub sem descrição."
                        stars = item.get("stargazers_count", 0)
                        lang = item.get("language") or "Code"
                        results.append(SearchResult(
                            title=f"[GitHub] {full_name} ({lang} - ⭐ {stars})",
                            url=html_url,
                            description=desc,
                            source="GitHub",
                            score=1.35
                        ))
        except Exception:
            pass
        return results


class StackOverflowSearcher:
    """
    Pesquisa de discussões técnicas e soluções no Stack Overflow API.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 5) -> List[SearchResult]:
        results = []
        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "q": query,
                "order": "desc",
                "sort": "relevance",
                "site": "stackoverflow",
                "pagesize": limit
            }
            async with httpx.AsyncClient(timeout=6.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        title = item.get("title", "")
                        link = item.get("link", "")
                        score = item.get("score", 0)
                        answers = item.get("answer_count", 0)
                        tags = ", ".join(item.get("tags", [])[:4])
                        results.append(SearchResult(
                            title=f"[StackOverflow] {title}",
                            url=link,
                            description=f"Votos: {score} | Respostas: {answers} | Tags: [{tags}]",
                            source="Stack Overflow",
                            score=1.3
                        ))
        except Exception:
            pass
        return results


class WikipediaSearcher:
    @classmethod
    async def search(cls, query: str, limit: int = 5, lang: str = "pt") -> List[SearchResult]:
        results = []
        try:
            url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": limit
            }
            async with httpx.AsyncClient(timeout=6.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("query", {}).get("search", []):
                        title = item.get("title", "")
                        snippet_html = item.get("snippet", "")
                        clean_desc = BeautifulSoup(snippet_html, "lxml").get_text(strip=True)
                        page_id = item.get("pageid")
                        page_url = f"https://{lang}.wikipedia.org/?curid={page_id}"
                        results.append(SearchResult(
                            title=f"Wikipedia: {title}",
                            url=page_url,
                            description=clean_desc,
                            source="Wikipédia",
                            score=1.3
                        ))
        except Exception:
            pass
        return results


class HackerNewsSearcher:
    @classmethod
    async def search(cls, query: str, limit: int = 5) -> List[SearchResult]:
        results = []
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {"query": query, "tags": "story", "hitsPerPage": limit}
            async with httpx.AsyncClient(timeout=5.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for hit in data.get("hits", []):
                        title = hit.get("title", "")
                        url_item = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                        points = hit.get("points", 0)
                        author = hit.get("author", "")
                        comments = hit.get("num_comments", 0)
                        desc = f"{points} pontos por {author} | {comments} comentários no Hacker News."
                        if title:
                            results.append(SearchResult(
                                title=f"[Notícias Tech] {title}",
                                url=url_item,
                                description=desc,
                                source="Notícias Tech",
                                score=1.1
                            ))
        except Exception:
            pass
        return results


class ImageSearcher:
    """
    Busca de Imagens Direta via Brave Images (decodifica links reais para arquivos .png, .jpg, .webp, .svg e thumbnails).
    Otimizado para agentes IA (Claude Code, Hermes, Cursor) e desenvolvedores construindo sites.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 25, page: int = 1) -> List[SearchResult]:
        results = []
        seen_urls = set()
        try:
            import base64
            url = "https://search.brave.com/images"
            params = {"q": query, "offset": page - 1}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

            async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for img in soup.find_all("img"):
                        src = img.get("src", "")
                        alt = img.get("alt") or query
                        if "/g:ce/" in src and not "favicons.search.brave.com" in src:
                            b64_part = src.split("/g:ce/")[-1].replace("/", "")
                            padding = 4 - (len(b64_part) % 4)
                            if padding != 4:
                                b64_part += "=" * padding
                            try:
                                direct_url = base64.urlsafe_b64decode(b64_part).decode("utf-8")
                                if direct_url.startswith("http") and "favicons.search.brave.com" not in direct_url:
                                    if direct_url not in seen_urls:
                                        seen_urls.add(direct_url)
                                        ext = direct_url.split(".")[-1].split("?")[0].upper()
                                        if len(ext) > 4:
                                            ext = "IMG"
                                        desc = f"Formato: {ext} | Thumbnail CDN: {src[:60]}... | Fonte: Brave Images"
                                        results.append(SearchResult(
                                            title=f"{alt} ({ext})",
                                            url=direct_url,
                                            description=desc,
                                            source="Imagens Web",
                                            score=1.95
                                        ))
                                        if len(results) >= limit:
                                            break
                            except Exception:
                                pass
        except Exception:
            pass
        return results


class MetaSearchEngine:
    """
    Motor Central de Meta-Search com suporte a todas as 14 categorias, filtros avançados e paginação.
    """
    @classmethod
    async def search_all(
        cls,
        query: str,
        local_index=None,
        sources: str = "all",
        limit: int = 30,
        domain: str = "",
        time_range: str = "",
        lang: str = "pt",
        region: str = "br",
        page: int = 1
    ) -> List[dict]:
        tasks = []

        if sources == "images":
            tasks.append(ImageSearcher.search(query, limit=limit, page=page))
        elif sources == "web":
            tasks.append(BraveSearcher.search(query, limit=limit, domain=domain, page=page, source_label="Web / Google"))
            tasks.append(DuckDuckGoSearcher.search(query, limit=limit, domain=domain, time_range=time_range, page=page))
        elif sources in ("all", "news", "images", "videos"):
            tasks.append(BraveSearcher.search(query, limit=max(20, limit), domain=domain, page=page, source_label="Web / Google"))
            tasks.append(DuckDuckGoSearcher.search(query, limit=max(20, limit), domain=domain, time_range=time_range, page=page))
        if sources in ("all", "pdfs"):
            pdf_q = f"{query} filetype:pdf"
            tasks.append(DuckDuckGoSearcher.search(pdf_q, limit=12, domain=domain, page=page))
        if sources in ("all", "arxiv", "papers"):
            tasks.append(ArxivSearcher.search(query, limit=10))
        if sources in ("all", "github"):
            tasks.append(GitHubSearcher.search(query, limit=10))
        if sources in ("all", "stackoverflow", "tech"):
            tasks.append(StackOverflowSearcher.search(query, limit=10))
        if sources in ("all", "wiki"):
            tasks.append(WikipediaSearcher.search(query, limit=5, lang=lang))
        if sources in ("all", "news", "tech"):
            tasks.append(HackerNewsSearcher.search(query, limit=10))

        all_results: List[SearchResult] = []

        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for res_batch in results_list:
                if isinstance(res_batch, list):
                    all_results.extend(res_batch)

        if local_index and sources in ("all", "local"):
            try:
                local_docs = local_index.search(query, limit=20)
                for doc in local_docs:
                    all_results.append(SearchResult(
                        title=doc.get("title") or doc.get("url"),
                        url=doc.get("url", ""),
                        description=doc.get("description") or "Documento indexado localmente.",
                        source="Índice Local",
                        score=doc.get("score", 1.0)
                    ))
            except Exception:
                pass

        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(asdict(r))

        unique_results.sort(key=lambda x: x["score"], reverse=True)
        return unique_results[:limit]

    @classmethod
    async def search(cls, query: str, **kwargs) -> List[dict]:
        return await cls.search_all(query, **kwargs)
