import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import time
import asyncio
from dataclasses import dataclass, field
from core.extractor import MarkdownExtractor


@dataclass
class Page:
    url: str
    title: str
    content: str
    description: str
    markdown: str = ""
    word_count: int = 0
    reading_time_min: int = 1
    depth: int = 0
    crawled_at: float = field(default_factory=time.time)

    @property
    def fingerprint(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()


class Crawler:
    """
    Spiders / Crawler Profundo e Paralelo para Agentes e Busca Local.
    Suporta:
    - Limite de profundidade (max_depth)
    - Paralelismo e controle de workers assíncronos (concurrency)
    - Descoberta via sitemap.xml
    - Verificação de robots.txt
    - Deduplicação automática por URL e fingerprint
    """
    def __init__(
        self,
        max_pages: int = 100,
        max_depth: int = 3,
        concurrency: int = 4,
        delay: float = 0.2,
        timeout: float = 12.0,
        respect_robots: bool = True
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.delay = delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.visited: set[str] = set()
        self.pages: list[Page] = []
        self.robots_disallowed: set[str] = set()

    async def _parse_robots_txt(self, base_url: str):
        try:
            parsed = urlparse(base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        if line.strip().lower().startswith("disallow:"):
                            parts = line.split(":")
                            if len(parts) > 1:
                                path = parts[1].strip()
                                if path:
                                    self.robots_disallowed.add(path)
        except Exception:
            pass

    async def _parse_sitemap(self, base_url: str) -> list[str]:
        urls = []
        try:
            parsed = urlparse(base_url)
            sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(sitemap_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "xml")
                    for loc in soup.find_all("loc"):
                        txt = loc.get_text(strip=True)
                        if txt and txt not in self.visited:
                            urls.append(txt)
        except Exception:
            pass
        return urls[:50]

    def _is_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        path = urlparse(url).path
        for dis in self.robots_disallowed:
            if path.startswith(dis):
                return False
        return True

    async def fetch_page(self, url: str, depth: int = 0) -> Page | None:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; RusyaSearch/2.0; +https://github.com/rusya)"}
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

                extracted = MarkdownExtractor.extract(resp.text, url=url)

                return Page(
                    url=url,
                    title=extracted.title,
                    content=extracted.raw_text,
                    description=extracted.description,
                    markdown=extracted.markdown,
                    word_count=extracted.word_count,
                    reading_time_min=extracted.reading_time_min,
                    depth=depth
                )
        except Exception:
            return None

    def extract_links(self, url: str, soup: BeautifulSoup) -> list[str]:
        links = []
        base_netloc = urlparse(url).netloc
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(url, href)
            parsed = urlparse(full)
            if parsed.scheme in ("http", "https") and parsed.netloc == base_netloc and not any(
                full.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".svg", ".zip", ".mp4", ".exe"]
            ):
                clean_url = full.split("#")[0].rstrip("/")
                if clean_url not in links:
                    links.append(clean_url)
        return links

    async def crawl(self, seed_url: str, callback=None) -> list[Page]:
        self.visited.clear()
        self.pages.clear()
        self.robots_disallowed.clear()

        if self.respect_robots:
            await self._parse_robots_txt(seed_url)

        # Queue items: tuple (url, depth)
        queue = [(seed_url, 0)]

        # Check sitemap first
        sitemap_urls = await self._parse_sitemap(seed_url)
        for sm_url in sitemap_urls:
            queue.append((sm_url, 1))

        sem = asyncio.Semaphore(self.concurrency)

        while queue and len(self.visited) < self.max_pages:
            batch = queue[:self.concurrency]
            queue = queue[self.concurrency:]

            async def process_item(item):
                url, depth = item
                if url in self.visited or depth > self.max_depth or not self._is_allowed(url):
                    return
                self.visited.add(url)

                async with sem:
                    page = await self.fetch_page(url, depth=depth)
                    if page:
                        self.pages.append(page)
                        if callback:
                            callback(url, len(self.pages))

                        if depth < self.max_depth:
                            try:
                                async with httpx.AsyncClient(
                                    timeout=self.timeout,
                                    follow_redirects=True,
                                    headers={"User-Agent": "RusyaSearch/2.0"}
                                ) as client:
                                    resp = await client.get(url)
                                    soup = BeautifulSoup(resp.text, "lxml")
                                    new_links = self.extract_links(url, soup)
                                    for l in new_links:
                                        if l not in self.visited:
                                            queue.append((l, depth + 1))
                            except Exception:
                                pass
                if self.delay:
                    await asyncio.sleep(self.delay)

            await asyncio.gather(*(process_item(item) for item in batch))

        return self.pages
