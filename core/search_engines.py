import asyncio
import os
import json
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, quote
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any


@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    source: str
    score: float = 1.0

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return ["title", "url", "description", "source", "score"]


class BraveSearcher:
    """
    Motor de Busca Avançado (BraveSearcher v6.0 — 100% Grátis & Sem Chaves de API).
    Realiza extração direta de dados do ecossistema Brave sem depender de serviços pagos:
    1. Análise do Payload SvelteKit (`kit.start window data` AST) para capturar resultados puros diretamente no JS antes da renderização.
    2. Busca simultânea com o filtro técnico `tech.goggles` para desenvolvedores (elimina spam e foca em GitHub/Stack Overflow/ArXiv).
    3. Extração estruturada de painéis informativos (`Knowledge Cards`), Q&As diretos e Sitelinks.
    4. Mapeamento de sugestões e autocompletar (`Related Queries`).
    """
    @classmethod
    async def search(
        cls,
        query: str,
        limit: int = 25,
        domain: str = "",
        page: int = 1,
        source_label: str = "Brave / Web",
        score_bonus: float = 0.5,
        quantum_parallel: bool = True
    ) -> List[SearchResult]:
        results_map = {}
        full_query = f"{query} site:{domain}" if domain else query

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://search.brave.com/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Upgrade-Insecure-Requests": "1"
        }

        # Dimensões Quânticas 100% Gratuitas e Sem API Paga!
        urls_params = [
            ("https://search.brave.com/search", {"q": full_query, "offset": page - 1, "source": "web"}, "Brave Organic")
        ]
        if quantum_parallel and not domain:
            # Adiciona dimensão Brave Tech Goggles (eliminação 100% de spam de SEO e foco em desenvolvedores)
            urls_params.append((
                "https://search.brave.com/search",
                {"q": full_query, "offset": page - 1, "goggles_id": "https://raw.githubusercontent.com/brave/goggles-quickstart/main/goggles/tech.goggles"},
                "Brave Tech Goggles"
            ))

        async def fetch_dimension(url: str, params: dict, label: str):
            dim_results = []
            try:
                async with httpx.AsyncClient(timeout=9.0, follow_redirects=True, headers=headers) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        return dim_results
                    html_text = resp.text
                    soup = BeautifulSoup(html_text, "lxml")

                    # -----------------------------------------------------------------
                    # CAMADA 1: Engenharia Reversa do Payload JS SvelteKit (`kit.start`)
                    # -----------------------------------------------------------------
                    # O servidor Brave injeta todos os dados originais no script inline do SvelteKit antes do DOM renderizar.
                    try:
                        for script in soup.find_all("script"):
                            txt = script.string or ""
                            if "web:{" in txt or "results:[" in txt or "kit.start(" in txt:
                                # Varre todas as URLs no script e busca title/description na janela local
                                urls_found = [m for m in re.finditer(r'url\s*:\s*("https?://(?:\\["\\/bfnrt]|[^"\\])*")', txt)]
                                for u_match in urls_found:
                                    try:
                                        u_str = u_match.group(1)
                                        url_clean = json.loads(u_str)
                                        if any(skip in url_clean for skip in ["brave.com", "w3.org", "javascript:"]):
                                            continue
                                        
                                        # Janela AST de [-500, +850] caracteres ao redor do URL
                                        start_p = max(0, u_match.start() - 500)
                                        end_p = min(len(txt), u_match.end() + 850)
                                        window = txt[start_p:end_p]
                                        
                                        t_match = re.search(r'title\s*:\s*("(?:\\["\\/bfnrt]|[^"\\])*")', window)
                                        title_clean = json.loads(t_match.group(1)) if t_match else "N/A"
                                        
                                        d_match = re.search(r'description\s*:\s*("(?:\\["\\/bfnrt]|[^"\\])*")', window)
                                        desc_clean = json.loads(d_match.group(1)) if d_match else ""
                                        if desc_clean:
                                            # Remove tags HTML embutidas (ex: \u003Cstrong>)
                                            import html as html_lib
                                            desc_clean = html_lib.unescape(re.sub(r'<[^>]+>', '', desc_clean))
                                        
                                        if title_clean != "N/A" and len(title_clean) > 2:
                                            score_js = 2.8 + score_bonus
                                            if label == "Brave Tech Goggles":
                                                score_js += 0.4
                                            dim_results.append(SearchResult(
                                                title=title_clean,
                                                url=url_clean,
                                                description=desc_clean,
                                                source=f"{label} [JS Engine]",
                                                score=score_js
                                            ))
                                    except Exception:
                                        continue
                                break
                    except Exception:
                        pass

                    # -----------------------------------------------------------------
                    # CAMADA 2: Extração DOM de Knowledge Cards / Infobox & Q&A Direct Answers
                    # -----------------------------------------------------------------
                    try:
                        info_box = soup.select_one("#infobox, .infobox, .sidebar-card, .entity-card")
                        if info_box:
                            i_title = info_box.select_one("h1, h2, .title, .entity-title")
                            i_title_txt = i_title.get_text(strip=True) if i_title else query
                            i_desc = info_box.select_one(".desc, .snippet-description, p, .description")
                            i_desc_txt = i_desc.get_text(strip=True) if i_desc else ""
                            if i_title_txt and i_desc_txt:
                                dim_results.append(SearchResult(
                                    title=f"💡 [Knowledge Card] {i_title_txt}",
                                    url=f"https://search.brave.com/search?q={quote(query)}",
                                    description=i_desc_txt[:450],
                                    source=f"{label} [Infobox]",
                                    score=5.2 + score_bonus
                                ))
                    except Exception:
                        pass

                    try:
                        for qa in soup.select(".qa-block, details.question, .qa-answer, .deep-answers, .discussion-snippet"):
                            q_el = qa.select_one(".question, summary, h3, h4, .q")
                            a_el = qa.select_one(".answer, .a, p, .content")
                            if q_el and a_el:
                                q_t = q_el.get_text(strip=True)
                                a_t = a_el.get_text(strip=True)
                                if len(q_t) > 5 and len(a_t) > 10:
                                    dim_results.append(SearchResult(
                                        title=f"💬 [Direct Answer] {q_t}",
                                        url=f"https://search.brave.com/search?q={quote(q_t)}",
                                        description=a_t,
                                        source=f"{label} [Q&A]",
                                        score=4.9 + score_bonus
                                    ))
                    except Exception:
                        pass

                    # -----------------------------------------------------------------
                    # CAMADA 3: Extração DOM Complementar (Sitelinks e Expansão de Sugestões)
                    # -----------------------------------------------------------------
                    for item in soup.select(".snippet:not(.standalone), .result-wrapper, .snippet[data-type='web'], div[data-pos]"):
                        link_el = item.select_one("a[href]")
                        if not link_el or not link_el.get("href"):
                            continue
                        href = link_el.get("href", "")
                        if not href.startswith("http") or any(skip in href for skip in ["brave.com", "javascript:"]):
                            continue

                        title_el = link_el.select_one(".title, .search-snippet-title, div[class*='title'], h3, h2")
                        title = title_el.get_text(strip=True) if title_el else link_el.get_text(separator=" ", strip=True)
                        if not title or len(title) < 2:
                            continue

                        desc_el = item.select_one(".content, .snippet-content, .snippet-description, div[class*='content'], p")
                        if desc_el:
                            for unwanted_hdr in desc_el.select(".result-header, .site-name-wrapper, .favicon-wrapper, a[class*='title']"):
                                unwanted_hdr.decompose()
                            desc = desc_el.get_text(separator=" ", strip=True)
                        else:
                            desc = ""

                        age_el = item.select_one(".snippet-age, time, .age")
                        if age_el:
                            age_txt = age_el.get_text(strip=True)
                            if age_txt and not age_txt in desc:
                                desc = f"🕒 [{age_txt}] {desc}"

                        sitelinks = []
                        for sl in item.select(".deep-links a, .sitelinks a, .sublinks a, .deep-results a, ul.links a"):
                            sl_h = sl.get("href", "")
                            sl_t = sl.get_text(strip=True)
                            if sl_h.startswith("http") and sl_t and sl_h != href:
                                sitelinks.append(f"[{sl_t}] -> {sl_h}")
                        if sitelinks:
                            desc += f"\n📌 Sitelinks: {' | '.join(sitelinks[:4])}"

                        score = 2.4 + score_bonus
                        if label == "Brave Tech Goggles":
                            score += 0.4

                        dim_results.append(SearchResult(
                            title=title,
                            url=href,
                            description=desc,
                            source=label,
                            score=score
                        ))

                    # Extração de Sugestões Relacionadas para Agentes
                    try:
                        related_list = []
                        for rq in soup.select(".related-queries a, .deep-queries a, .suggestions a, [class*='related'] a"):
                            rq_txt = rq.get_text(strip=True)
                            if rq_txt and len(rq_txt) > 3:
                                related_list.append(rq_txt)
                        if related_list:
                            dim_results.append(SearchResult(
                                title=f"🔮 [Sugestões Relacionadas] Expansões para '{query}'",
                                url=f"https://search.brave.com/search?q={quote(query)}",
                                description=" | ".join([f"• {rq}" for rq in set(related_list[:6])]),
                                source=f"{label} [Deep Suggest]",
                                score=3.0 + score_bonus
                            ))
                    except Exception:
                        pass

            except Exception:
                pass
            return dim_results

        # Execução Quântica Paralela das Camadas (Svelte JS + DOM + Tech Goggles)
        try:
            tasks = [fetch_dimension(u, p, l) for u, p, l in urls_params]
            batch_lists = await asyncio.gather(*tasks)
            for b_list in batch_lists:
                for r in b_list:
                    clean_u = r.url.split("#")[0].rstrip("/")
                    if clean_u in results_map:
                        # Validação Multi-Camadas e consolidação de Sitelinks
                        results_map[clean_u].score += 0.9
                        if "Sitelinks:" in r.description and not "Sitelinks:" in results_map[clean_u].description:
                            results_map[clean_u].description += "\n" + r.description.split("\n📌 Sitelinks:")[1]
                        # Preferência por descrição vinda da extração JS por ser mais limpa
                        if "[JS Engine]" in r.source and len(r.description) > len(results_map[clean_u].description):
                            results_map[clean_u].description = r.description
                    else:
                        results_map[clean_u] = r
        except Exception:
            pass

        final_list = sorted(results_map.values(), key=lambda r: r.score, reverse=True)
        return final_list[:limit]


class GoogleSearcher:
    """
    Motor Multi-Camadas de Busca Web (`GoogleSearcher`).
    Agrega 4 fontes e estratégias em paralelo para evitar bloqueios de CAPTCHA/429 e maximizar a cobertura:
    1. Google News / Feeds RSS (100% livre de bloqueios, excelente para conteúdos recentes com datas).
    2. DuckDuckGo HTML Deep Search (Com suporte a paginação real e filtros por data/site).
    3. Brave Search Organic Engine (Extração limpa e rápida de snippets).
    4. Google Lite Mobile (Tentativa de extração direta via interface móvel/leve).
    """
    @classmethod
    async def search(
        cls,
        query: str,
        limit: int = 30,
        domain: str = "",
        time_range: str = "",
        page: int = 1,
        source_label: str = "Google / Web",
        score_bonus: float = 0.5
    ) -> List[SearchResult]:
        results = []
        seen_urls = set()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
        }

        async def fetch_google_news_rss():
            local_res = []
            try:
                import xml.etree.ElementTree as ET
                q_rss = f"{query} site:{domain}" if domain else query
                url = f"https://news.google.com/rss/search?q={q_rss}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
                async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        for item in root.findall(".//item")[:15]:
                            title = item.findtext("title", "")
                            link = item.findtext("link", "")
                            pub = item.findtext("pubDate", "")
                            if not link:
                                continue
                            src_name = "Google News"
                            if " - " in title:
                                parts = title.rsplit(" - ", 1)
                                title = parts[0]
                                src_name = f"Google ({parts[1]})"
                            desc = f"⚡ Indexado pelo Google em tempo real | Data: {pub[:22]} | Fonte: {src_name}"
                            local_res.append(SearchResult(
                                title=title,
                                url=link,
                                description=desc,
                                source="Google / Web",
                                score=2.1 + score_bonus
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_ddg():
            try:
                items = await DuckDuckGoSearcher.search(
                    query=query, limit=limit, domain=domain, time_range=time_range,
                    page=page, source_label="Google / Web", score_bonus=score_bonus
                )
                return items
            except Exception:
                return []

        async def fetch_brave():
            try:
                items = await BraveSearcher.search(
                    query=query, limit=limit, domain=domain, page=page,
                    source_label="Google / Web", score_bonus=score_bonus - 0.1
                )
                return items
            except Exception:
                return []

        async def fetch_google_direct():
            local_res = []
            try:
                mobile_ua = "Mozilla/5.0 (Linux; U; Android 4.4.2; pt-br; LGMS323 Build/KOT49I.MS32310c) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.103 Mobile Safari/537.36"
                g_url = "https://www.google.com/search"
                params = {"q": f"{query} site:{domain}" if domain else query, "gbv": "1", "num": "20", "hl": "pt-BR"}
                async with httpx.AsyncClient(timeout=6.0, headers={"User-Agent": mobile_ua, "Accept-Language": "pt-BR,pt;q=0.9"}, follow_redirects=True) as client:
                    resp = await client.get(g_url, params=params)
                    if resp.status_code == 200 and not any(bad in resp.text.lower()[:400] for bad in ["sorry", "enablejs"]):
                        soup = BeautifulSoup(resp.text, "lxml")
                        for a in soup.find_all("a"):
                            href = a.get("href", "")
                            if "/url?q=" in href and not "google.com" in href.split("/url?q=")[1].split("&")[0]:
                                real_u = href.split("/url?q=")[1].split("&")[0]
                                title_text = a.get_text(strip=True)
                                if title_text and real_u.startswith("http"):
                                    local_res.append(SearchResult(
                                        title=title_text,
                                        url=real_u,
                                        description="⚡ Resultado Orgânico Direto do Google Search (gbv=1 bypass).",
                                        source="Google Orgânico",
                                        score=2.2 + score_bonus
                                    ))
            except Exception:
                pass
            return local_res

        batches = await asyncio.gather(
            fetch_google_news_rss(), fetch_google_direct(), fetch_ddg(), fetch_brave(),
            return_exceptions=True
        )
        for batch in batches:
            if isinstance(batch, list):
                for r in batch:
                    clean_u = r.url.split("#")[0].rstrip("/")
                    if clean_u and clean_u not in seen_urls and not any(bad in clean_u.lower() for bad in ["doubleclick", "googleadservices"]):
                        seen_urls.add(clean_u)
                        results.append(r)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


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


class GoogleScholarSearcher:
    """
    Motor Especializado de Pesquisa Científica Híbrido (OpenAlex API + Google Scholar).
    Extrai artigos acadêmicos, contagem de citações, links de PDFs abertos e resumos científicos livres de CAPTCHA.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 15) -> List[SearchResult]:
        results = []
        seen_urls = set()

        async def fetch_openalex():
            local_res = []
            try:
                url = "https://api.openalex.org/works"
                params = {"search": query, "per_page": str(limit)}
                async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "mailto:rusyasearch@github.com"}) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        for w in data.get("results", []):
                            title = w.get("title") or "Sem título"
                            doi = w.get("doi") or w.get("id", "")
                            year = w.get("publication_year", "")
                            cits = w.get("cited_by_count", 0)
                            oa_url = w.get("open_access", {}).get("oa_url", "") or doi
                            if oa_url and oa_url not in seen_urls:
                                seen_urls.add(oa_url)
                                desc = f"Artigo científico publicado em {year} | 📊 {cits} citações acadêmicas."
                                local_res.append(SearchResult(
                                    title=f"🎓 [{year}] {title}",
                                    url=oa_url,
                                    description=f"📚 [OpenAlex / Scholar] {desc}",
                                    source="Google Scholar / OpenAlex",
                                    score=2.5
                                ))
            except Exception:
                pass
            return local_res

        async def fetch_scholar_html():
            local_res = []
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
                }
                url = "https://scholar.google.com/scholar"
                params = {"q": query, "hl": "pt-BR"}
                async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200 and not any(bad in resp.text.lower()[:400] for bad in ["sorry", "enablejs"]):
                        soup = BeautifulSoup(resp.text, "lxml")
                        for h3 in soup.find_all("h3"):
                            a = h3.find("a")
                            if not a or not a.get("href"):
                                continue
                            href = a["href"]
                            title = h3.get_text(strip=True)
                            if href.startswith("http") and href not in seen_urls:
                                seen_urls.add(href)
                                parent = h3.find_parent("div")
                                snippet_el = parent.select_one(".gs_rs") if parent else None
                                desc = snippet_el.get_text(strip=True) if snippet_el else "Artigo acadêmico indexado pelo Google Scholar."
                                local_res.append(SearchResult(
                                    title=f"🎓 {title}",
                                    url=href,
                                    description=f"📚 [Google Scholar] {desc}",
                                    source="Google Scholar",
                                    score=2.3
                                ))
            except Exception:
                pass
            return local_res

        batches = await asyncio.gather(fetch_openalex(), fetch_scholar_html(), return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                results.extend(batch)
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class GoogleSuggestSearcher:
    """
    Motor de Autocompletar / Sugestões em Tempo Real do Google.
    Permite que agentes IA de deep research explorem palavras-chave relacionadas, intenção de busca e tendências.
    """
    @classmethod
    async def suggest(cls, query: str) -> List[str]:
        try:
            url = "http://suggestqueries.google.com/complete/search"
            params = {"client": "chrome", "q": query, "hl": "pt-BR"}
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        return data[1][:15]
        except Exception:
            pass
        return [query]


class SmartDorkBuilder:
    """
    Construtor e Executador de Google Dorks Avançados.
    Converte intenção em comandos precisos (site:, filetype:, intitle:, inurl:) para extração cirúrgica de dados e segurança.
    """
    @classmethod
    def build_dork(cls, intent: str, domain: str = "", filetype: str = "", inurl: str = "") -> str:
        dork = intent
        if domain and "site:" not in dork:
            dork += f" site:{domain}"
        if filetype and "filetype:" not in dork:
            dork += f" filetype:{filetype}"
        if inurl and "inurl:" not in dork:
            dork += f" inurl:{inurl}"
        return dork.strip()


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


class RedditSearcher:
    """
    Motor Quad-Híbrido Revolucionário para Pesquisa no Reddit (Bypass Anti-Bot / Cloudflare).
    Combina:
    1. PullPush API (Mirror em tempo real sem rate-limit ou CAPTCHA).
    2. Reddit .json endpoint com spoofing de headers modernos.
    3. Arctic Shift API Archive.
    4. Meta-Dorking com DuckDuckGo/Brave Search.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 25, domain: str = "", page: int = 1) -> List[SearchResult]:
        results = []
        seen_urls = set()
        
        subreddit = ""
        clean_q = query
        if domain and "reddit.com/r/" in domain.lower():
            subreddit = domain.lower().split("reddit.com/r/")[-1].strip("/")
        elif domain and domain.lower().startswith("r/"):
            subreddit = domain[2:].strip("/")
            
        r_match = re.search(r"\b(r/[a-zA-Z0-9_]+|subreddit:[a-zA-Z0-9_]+)\b", query, re.I)
        if r_match:
            sub_raw = r_match.group(0)
            subreddit = sub_raw.replace("subreddit:", "").replace("r/", "").strip("/")
            clean_q = re.sub(r"\b(r/[a-zA-Z0-9_]+|subreddit:[a-zA-Z0-9_]+)\b", "", query, flags=re.I).strip()

        if not clean_q and subreddit:
            clean_q = subreddit

        async def fetch_pullpush():
            local_res = []
            try:
                url = "https://api.pullpush.io/reddit/search/submission/"
                params = {"q": clean_q, "size": limit, "sort": "desc"}
                if subreddit:
                    params["subreddit"] = subreddit
                async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        for item in resp.json().get("data", []):
                            title = item.get("title", "Sem Título")
                            permalink = item.get("permalink", "")
                            item_url = item.get("url") or (f"https://www.reddit.com{permalink}" if permalink else "")
                            if not item_url and permalink:
                                item_url = f"https://www.reddit.com{permalink}"
                            if not item_url:
                                continue
                            author = item.get("author", "anônimo")
                            score = item.get("score", 0)
                            num_comments = item.get("num_comments", 0)
                            sub = item.get("subreddit") or subreddit or "Reddit"
                            selftext = (item.get("selftext", "") or "")[:220].replace("\n", " ")
                            if selftext in ("[removed]", "[deleted]"):
                                selftext = ""
                            desc = f"⬆️ {score} votos | 💬 {num_comments} comentários | u/{author} em r/{sub}\n{selftext}".strip()
                            local_res.append(SearchResult(
                                title=f"[{sub}] {title}",
                                url=f"https://www.reddit.com{permalink}" if permalink else item_url,
                                description=desc,
                                source=f"Reddit - r/{sub}",
                                score=1.8
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_reddit_json():
            local_res = []
            try:
                if subreddit:
                    url = f"https://www.reddit.com/r/{subreddit}/search.json"
                    params = {"q": clean_q, "restrict_sr": "on", "sort": "relevance", "limit": limit}
                else:
                    url = "https://www.reddit.com/search.json"
                    params = {"q": clean_q, "sort": "relevance", "limit": limit}
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
                }
                async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        for child in data.get("data", {}).get("children", []):
                            item = child.get("data", {})
                            title = item.get("title", "Sem Título")
                            permalink = item.get("permalink", "")
                            item_url = f"https://www.reddit.com{permalink}" if permalink else item.get("url", "")
                            if not item_url:
                                continue
                            author = item.get("author", "anônimo")
                            score = item.get("score", 0)
                            num_comments = item.get("num_comments", 0)
                            sub = item.get("subreddit") or subreddit or "Reddit"
                            selftext = (item.get("selftext", "") or "")[:220].replace("\n", " ")
                            if selftext in ("[removed]", "[deleted]"):
                                selftext = ""
                            desc = f"⬆️ {score} votos | 💬 {num_comments} comentários | u/{author} em r/{sub}\n{selftext}".strip()
                            local_res.append(SearchResult(
                                title=f"[{sub}] {title}",
                                url=item_url,
                                description=desc,
                                source=f"Reddit - r/{sub}",
                                score=1.75
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_arctic_shift():
            local_res = []
            try:
                url = "https://arctic-shift.eno.win/api/reddit/search/submission/"
                params = {"q": clean_q, "limit": limit}
                if subreddit:
                    params["subreddit"] = subreddit
                async with httpx.AsyncClient(timeout=7.0, headers={"User-Agent": "RusyaSearch/2.0"}) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        for item in resp.json().get("data", []):
                            title = item.get("title", "Sem Título")
                            permalink = item.get("permalink", "")
                            item_url = f"https://www.reddit.com{permalink}" if permalink else item.get("url", "")
                            if not item_url:
                                continue
                            author = item.get("author", "anônimo")
                            score = item.get("score", 0)
                            num_comments = item.get("num_comments", 0)
                            sub = item.get("subreddit") or subreddit or "Reddit"
                            desc = f"⬆️ {score} votos | 💬 {num_comments} comentários | u/{author} em r/{sub}"
                            local_res.append(SearchResult(
                                title=f"[{sub}] {title}",
                                url=item_url,
                                description=desc,
                                source=f"Reddit - r/{sub}",
                                score=1.65
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_dork():
            local_res = []
            try:
                dork_q = f"site:reddit.com/r/{subreddit} {clean_q}" if subreddit else f"site:reddit.com {clean_q}"
                ddg_res = await DuckDuckGoSearcher.search(dork_q, limit=limit, page=page)
                for r in ddg_res:
                    sub_name = "Reddit"
                    m = re.search(r"reddit\.com/r/([^/]+)", r.url, re.I)
                    if m:
                        sub_name = m.group(1)
                    r.source = f"Reddit - r/{sub_name}"
                    if not r.title.startswith(f"[{sub_name}]"):
                        r.title = f"[{sub_name}] {re.sub(r' : r/.*$', '', r.title, flags=re.I)}"
                    r.score = 1.5
                    local_res.append(r)
            except Exception:
                pass
            return local_res

        async def fetch_playwright_native():
            local_res = []
            try:
                from playwright.async_api import async_playwright
                from core.browser import PLAYWRIGHT_STEALTH_SCRIPT, MODERN_USER_AGENTS
                import random as py_random
                
                search_url = f"https://old.reddit.com/r/{subreddit}/search?q={clean_q}&restrict_sr=on&sort=relevance" if subreddit else f"https://old.reddit.com/search?q={clean_q}&sort=relevance"
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--no-sandbox",
                            "--disable-setuid-sandbox"
                        ]
                    )
                    ctx = await browser.new_context(
                        user_agent=py_random.choice(MODERN_USER_AGENTS),
                        viewport={"width": 1280, "height": 800},
                        locale="pt-BR"
                    )
                    await ctx.add_init_script(PLAYWRIGHT_STEALTH_SCRIPT)
                    page = await ctx.new_page()
                    
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=22000)
                    html = await page.content()
                    await browser.close()
                    
                    soup = BeautifulSoup(html, "lxml")
                    for item in soup.select(".search-result-link, div.search-result")[:limit]:
                        title_el = item.select_one("a.search-title")
                        if not title_el or not title_el.get("href"):
                            continue
                        href = title_el["href"]
                        if href.startswith("/"):
                            href = f"https://old.reddit.com{href}"
                        href = href.replace("old.reddit.com", "www.reddit.com")
                        title = title_el.get_text(strip=True)
                        sub_el = item.select_one("a.search-subreddit-link")
                        sub = sub_el.get_text(strip=True).replace("r/", "") if sub_el else (subreddit or "Reddit")
                        author_el = item.select_one("a.author")
                        author = author_el.get_text(strip=True) if author_el else "anon"
                        score_el = item.select_one(".search-score")
                        score = score_el.get_text(strip=True) if score_el else "⬆️"
                        snippet_el = item.select_one(".search-result-body")
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                        desc = f"{score} | u/{author} em r/{sub}\n{snippet}".strip()
                        local_res.append(SearchResult(
                            title=f"[{sub}] {title}",
                            url=href,
                            description=desc,
                            source=f"Reddit - r/{sub}",
                            score=2.0
                        ))
            except Exception:
                pass
            return local_res

        tasks = [fetch_pullpush(), fetch_reddit_json(), fetch_playwright_native(), fetch_arctic_shift(), fetch_dork()]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                for r in batch:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        results.append(r)
                        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class ImageSearcher:
    """
    Motor Central de Meta-Busca de Imagens 1000x Revolucionário (v3.0 Revolution).
    Agrega 5 motores de alta resolução simultaneamente com zero rate limit ou CAPTCHA:
    1. Wikimedia Commons API (Fotos HD originais, licença livre, dimensões exatas).
    2. Reddit PullPush API (Wallpapers HD, fotografia virais e artes diretas em i.redd.it).
    3. Flickr Creative Commons Scraper (Fotografia e imagens ao vivo de alta qualidade).
    4. Brave Images Decoder (Links originais decodificados do cache g:ce).
    5. Brand Logo & Vector Generator (Clearbit + SVG/PNG automáticos para marcas e tecnologias).
    Otimizado para agentes IA (Claude Code, Cursor, LLMs) e desenvolvedores construindo sites.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 35, page: int = 1) -> List[SearchResult]:
        results = []
        seen_urls = set()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }

        async def fetch_wikimedia():
            local_res = []
            try:
                url = "https://commons.wikimedia.org/w/api.php"
                params = {
                    "action": "query",
                    "generator": "search",
                    "gsrnamespace": 6,
                    "gsrsearch": query,
                    "gsroffset": (page - 1) * 15,
                    "gsrlimit": 15,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "iiurlwidth": 960,
                    "format": "json"
                }
                async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200 and "query" in resp.json():
                        pages = resp.json()["query"].get("pages", {})
                        for k, p in pages.items():
                            info = p.get("imageinfo", [{}])[0]
                            img_url = info.get("url", "")
                            if not img_url:
                                continue
                            width = info.get("width", 0)
                            height = info.get("height", 0)
                            mime = info.get("mime", "image/jpeg").split("/")[-1].upper()
                            meta = info.get("extmetadata", {})
                            title = meta.get("ObjectName", {}).get("value") or p.get("title", "").replace("File:", "").split(".")[0]
                            title = re.sub(r"<[^>]+>", "", title).strip() or query
                            desc = f"📐 Resolução: {width}x{height} | 🖼️ Formato: {mime} | 💡 Fonte: Wikimedia Commons HD"
                            local_res.append(SearchResult(
                                title=f"{title} ({width}x{height})",
                                url=img_url,
                                description=desc,
                                source="Imagens Web",
                                score=2.0 if width >= 1920 else 1.85
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_reddit_media():
            local_res = []
            try:
                url = "https://api.pullpush.io/reddit/search/submission/"
                params = {"q": query, "sort": "desc", "size": 25}
                async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "RusyaSearch/3.0"}) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        for item in resp.json().get("data", []):
                            img_url = item.get("url", "")
                            if not img_url or not any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not "i.redd.it" in img_url:
                                continue
                            title = item.get("title", query)
                            sub = item.get("subreddit", "Reddit")
                            score = item.get("score", 0)
                            ext = img_url.split(".")[-1].split("?")[0].upper()
                            if len(ext) > 4:
                                ext = "JPG"
                            desc = f"📐 Alta Definição | 🖼️ Formato: {ext} | ⬆️ {score} votos | 💡 Fonte: r/{sub}"
                            local_res.append(SearchResult(
                                title=f"{title} [r/{sub}]",
                                url=img_url,
                                description=desc,
                                source="Imagens Web",
                                score=1.9
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_flickr():
            local_res = []
            try:
                url = "https://www.flickr.com/search/"
                params = {"text": query, "view_all": 1}
                async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for img in soup.find_all("img"):
                            src = img.get("src", "")
                            if not src or not ("live.staticflickr.com" in src or "farm" in src):
                                continue
                            if src.startswith("//"):
                                src = "https:" + src
                            high_res = re.sub(r"_[a-z]\.jpg$", "_b.jpg", src)
                            alt = img.get("alt") or query
                            desc = f"📐 Resolução HD | 🖼️ Formato: JPG | 💡 Fonte: Flickr Creative Commons"
                            local_res.append(SearchResult(
                                title=f"{alt} (Flickr HD)",
                                url=high_res,
                                description=desc,
                                source="Imagens Web",
                                score=1.8
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_brave():
            local_res = []
            try:
                import base64
                url = "https://search.brave.com/images"
                params = {"q": query, "offset": page - 1}
                async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
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
                                        ext = direct_url.split(".")[-1].split("?")[0].upper()
                                        if len(ext) > 4:
                                            ext = "IMG"
                                        desc = f"📐 Dimensão Original | 🖼️ Formato: {ext} | 💡 Fonte: Brave Images"
                                        local_res.append(SearchResult(
                                            title=f"{alt} ({ext})",
                                            url=direct_url,
                                            description=desc,
                                            source="Imagens Web",
                                            score=1.75
                                        ))
                                except Exception:
                                    pass
            except Exception:
                pass
            return local_res

        async def fetch_logos():
            local_res = []
            try:
                q_clean = query.lower().replace("logo", "").replace("icon", "").replace("ícone", "").replace("png", "").strip()
                if q_clean and (any(w in query.lower() for w in ["logo", "icon", "ícone", "png", "brand", "marca"]) or len(query.split()) <= 2):
                    domain_guess = f"{re.sub(r'[^a-z0-9]', '', q_clean)}.com"
                    logo_url = f"https://logo.clearbit.com/{domain_guess}"
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        r = await client.head(logo_url)
                        if r.status_code == 200:
                            desc = f"📐 Transparente | 🖼️ Formato: PNG/SVG | 💡 Fonte: Clearbit Brand Logo HD"
                            local_res.append(SearchResult(
                                title=f"Logo Oficial {q_clean.title()} (PNG/SVG)",
                                url=logo_url,
                                description=desc,
                                source="Imagens Web",
                                score=2.1
                            ))
            except Exception:
                pass
            return local_res

        tasks = [fetch_wikimedia(), fetch_reddit_media(), fetch_flickr(), fetch_brave(), fetch_logos()]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                for r in batch:
                    if r.url and r.url not in seen_urls and not any(bad in r.url.lower() for bad in ["pixel.gif", "spacer", "tracking", "ad.doubleclick"]):
                        seen_urls.add(r.url)
                        results.append(r)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class IconAndVectorSearcher:
    """
    Motor Especializado de Ícones Transparente, SVGs Vetoriais e Logos para Agentes IA construindo interfaces e UIs web.
    Agrega OpenClipArt, Clearbit Brand Logos e ícones transparentes da web.
    Retorna a URL direta do PNG/SVG, transparência, dimensões e snippet de código <img src="..." alt="...">.
    """
    @classmethod
    async def search(cls, query: str, limit: int = 25) -> List[SearchResult]:
        results = []
        seen_urls = set()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}

        async def fetch_openclipart():
            local_res = []
            try:
                url = "https://openclipart.org/search/json/"
                params = {"query": query, "amount": 15}
                async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("payload", []):
                            svg_url = item.get("svg", {}).get("url") or item.get("detail_link")
                            png_url = item.get("png_full_lossy", {}).get("url") or svg_url
                            if not png_url:
                                continue
                            title = item.get("title", query)
                            desc = f"✨ Ícone Vetorial / ClipArt | 🖼️ Formato: SVG/PNG Transparente | 💡 Snippet: `<img src='{png_url}' alt='{title}' />`"
                            local_res.append(SearchResult(
                                title=f"Ícone: {title} (SVG/PNG)",
                                url=png_url,
                                description=desc,
                                source="Ícones & SVGs",
                                score=2.3
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_clearbit_and_icons():
            local_res = []
            try:
                q_clean = query.lower().replace("icon", "").replace("ícone", "").replace("svg", "").replace("logo", "").replace("png", "").strip()
                if q_clean:
                    domain_guess = f"{re.sub(r'[^a-z0-9]', '', q_clean)}.com"
                    logo_url = f"https://logo.clearbit.com/{domain_guess}"
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        r = await client.head(logo_url)
                        if r.status_code == 200:
                            desc = f"✨ Logo Transparente Oficial | 🖼️ Formato: PNG HD | 💡 Snippet: `<img src='{logo_url}' alt='{q_clean.title()}' />`"
                            local_res.append(SearchResult(
                                title=f"Logo / Ícone Oficial {q_clean.title()} (PNG)",
                                url=logo_url,
                                description=desc,
                                source="Ícones & SVGs",
                                score=2.5
                            ))
            except Exception:
                pass
            return local_res

        async def fetch_ddg_icons():
            local_res = []
            try:
                icon_q = f"{query} icon svg transparent png"
                ddg_res = await DuckDuckGoSearcher.search(icon_q, limit=12)
                for r in ddg_res:
                    if any(r.url.lower().endswith(ext) for ext in [".svg", ".png", ".webp"]) or "icon" in r.title.lower():
                        r.source = "Ícones & SVGs"
                        r.description = f"✨ Ícone Web Transparente | 🖼️ Link Direto | 💡 Snippet: `<img src='{r.url}' alt='{r.title}' />`"
                        r.score = 2.1
                        local_res.append(r)
            except Exception:
                pass
            return local_res

        tasks = [fetch_openclipart(), fetch_clearbit_and_icons(), fetch_ddg_icons()]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                for r in batch:
                    if r.url and r.url not in seen_urls:
                        seen_urls.add(r.url)
                        results.append(r)
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class MetaSearchEngine:
    """
    Motor Central de Meta-Search com suporte a todas as 15 categorias, filtros avançados e paginação.
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

        if sources in ("brave", "quantum"):
            tasks.append(BraveSearcher.search(query, limit=limit, domain=domain, page=page, source_label="Brave Quantum v5.0"))
        elif sources == "images":
            tasks.append(ImageSearcher.search(query, limit=limit, page=page))
            tasks.append(IconAndVectorSearcher.search(query, limit=12))
        elif sources in ("icons", "svgs", "logos"):
            tasks.append(IconAndVectorSearcher.search(query, limit=limit))
        elif sources == "reddit":
            tasks.append(RedditSearcher.search(query, limit=limit, domain=domain, page=page))
        elif sources == "web":
            tasks.append(GoogleSearcher.search(query, limit=limit, domain=domain, time_range=time_range, page=page))
            tasks.append(BraveSearcher.search(query, limit=limit, domain=domain, page=page, source_label="Brave Quantum v5.0"))
        elif sources in ("all", "news", "images", "videos"):
            tasks.append(GoogleSearcher.search(query, limit=max(25, limit), domain=domain, time_range=time_range, page=page))
            tasks.append(BraveSearcher.search(query, limit=max(20, limit), domain=domain, page=page, source_label="Brave Quantum v5.0"))
        if sources in ("all", "icons", "svgs"):
            tasks.append(IconAndVectorSearcher.search(query, limit=10))
        if sources in ("all", "reddit") or re.search(r"\b(r/[a-zA-Z0-9_]+|reddit|subreddit:[a-zA-Z0-9_]+)\b", query, re.I):
            tasks.append(RedditSearcher.search(query, limit=15, domain=domain, page=page))
        if sources in ("all", "pdfs"):
            pdf_q = f"{query} filetype:pdf"
            tasks.append(DuckDuckGoSearcher.search(pdf_q, limit=12, domain=domain, page=page))
        if sources in ("all", "arxiv", "papers", "scholar"):
            tasks.append(ArxivSearcher.search(query, limit=10))
            tasks.append(GoogleScholarSearcher.search(query, limit=12))
        if sources in ("all", "github"):
            tasks.append(GitHubSearcher.search(query, limit=10))
        if sources in ("all", "stackoverflow", "tech"):
            tasks.append(StackOverflowSearcher.search(query, limit=10))
            tasks.append(BraveSearcher.search(query, limit=12, domain=domain, page=page, source_label="Brave Tech Quantum"))
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
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:limit]

    @classmethod
    async def search(cls, query: str, **kwargs) -> List[dict]:
        if "max_results" in kwargs:
            kwargs["limit"] = kwargs.pop("max_results")
        return await cls.search_all(query, **kwargs)
