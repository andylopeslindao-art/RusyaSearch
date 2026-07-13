#!/usr/bin/env python3
"""
RusyaSearch 2.0 - AI Agent SDK & CLI Client
Suporte completo para:
- 🔎 Pesquisa: Web, Deep Research, Domínio, Data, Idioma, País, Notícias, Imagens, Vídeos, PDFs, Papers (arXiv), GitHub, StackOverflow, Docs
- 🌐 Navegação: Browse URL, simulação JS/Headless, clique/scroll/preencher, Screenshot, PDF
- 📄 Extração: Markdown, HTML limpo, Texto, JSON, Tabelas, Listas, Links, Imagens, OCR/PDF
- 🕷️ Crawl: Profundidade, Paralelismo, Sitemap, robots.txt, Deduplicação
"""

import sys
import json
import httpx
from typing import Dict, Any, List, Optional


class RusyaAgent:
    def __init__(self, base_url: str = "http://localhost:8080/api/v1/agent"):
        self.base_url = base_url.rstrip("/")

    def search(
        self,
        query: str,
        sources: str = "all",
        max_results: int = 15,
        domain: str = "",
        time_range: str = "",
        lang: str = "pt",
        region: str = "br"
    ) -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}/search",
            json={
                "query": query,
                "sources": sources,
                "max_results": max_results,
                "domain": domain,
                "time_range": time_range,
                "lang": lang,
                "region": region
            },
            timeout=18.0
        )
        resp.raise_for_status()
        return resp.json()

    def browse(
        self,
        url: str,
        format: str = "markdown",
        js_render: bool = False,
        capture_screenshot: bool = False
    ) -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}/browse",
            json={
                "url": url,
                "format": format,
                "js_render": js_render,
                "capture_screenshot": capture_screenshot
            },
            timeout=20.0
        )
        resp.raise_for_status()
        return resp.json()

    def extract(self, url: str, target: str = "markdown") -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}/extract",
            json={"url": url, "target": target},
            timeout=18.0
        )
        resp.raise_for_status()
        return resp.json()

    def crawl(
        self,
        seed_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        concurrency: int = 4,
        respect_robots: bool = True
    ) -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}/crawl",
            json={
                "seed_url": seed_url,
                "max_pages": max_pages,
                "max_depth": max_depth,
                "concurrency": concurrency,
                "respect_robots": respect_robots
            },
            timeout=15.0
        )
        resp.raise_for_status()
        return resp.json()

    def research(self, query: str, num_results: int = 5, browse_top_n: int = 2) -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}/research",
            json={"query": query, "num_results": num_results, "browse_top_n": browse_top_n},
            timeout=35.0
        )
        resp.raise_for_status()
        return resp.json()

    def google_research(self, query: str, browse_top_n: int = 2) -> Dict[str, Any]:
        """
        Pesquisa no Google / Web e ENTRA em cada um dos links retornados,
        extraindo todo o conteúdo em Markdown.
        """
        search_res = self.search(query, sources="web", max_results=browse_top_n)
        links = [r["url"] for r in search_res.get("results", [])[:browse_top_n]]
        pages_md = []
        for url in links:
            try:
                page = self.browse(url, format="markdown")
                pages_md.append(f"## {page.get('title', url)}\n**URL:** {url}\n\n{page.get('content', '')}")
            except Exception as e:
                pages_md.append(f"## Erro ao acessar {url}\n{str(e)}")

        dossier = f"# Pesquisa Google & Acesso Aos Links: {query}\n\n" + "\n\n---\n\n".join(pages_md)
        return {"query": query, "links_visited": links, "markdown": dossier}


def main():
    if len(sys.argv) < 3:
        print("Uso: python agent_client.py <search|browse|extract|crawl|research|google_research> <arg> [opcoes]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    arg = sys.argv[2]
    agent = RusyaAgent()

    if cmd == "search":
        print(json.dumps(agent.search(arg), indent=2, ensure_ascii=False))
    elif cmd == "browse":
        res = agent.browse(arg)
        print(res.get("content", ""))
    elif cmd == "extract":
        res = agent.extract(arg)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif cmd == "crawl":
        print(json.dumps(agent.crawl(arg), indent=2, ensure_ascii=False))
    elif cmd == "research":
        res = agent.research(arg)
        print(res.get("consolidated_dossier_markdown", ""))
    elif cmd == "google_research":
        res = agent.google_research(arg)
        print(res.get("markdown", ""))
    else:
        print(f"Comando desconhecido: {cmd}")


if __name__ == "__main__":
    main()
