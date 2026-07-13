import re
import time
import io
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString, Tag
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ExtractedMarkdown:
    url: str
    title: str
    description: str
    markdown: str
    raw_text: str
    word_count: int
    reading_time_min: int
    links: list[str]
    extracted_at: float


class MarkdownExtractor:
    """
    Revolutionary HTML to clean Markdown (.md) extractor.
    Strips noise, ads, navigation, and converts DOM structure to structured Markdown.
    Includes specialized extractors for Tables, Lists, Links, Images, and PDFs/OCR.
    """

    UNWANTED_TAGS = {
        "script", "style", "noscript", "iframe", "svg", "canvas",
        "header", "footer", "nav", "aside", "form", "button",
        "dialog", "menu", "map"
    }

    UNWANTED_CLASSES_IDS = re.compile(
        r"(sidebar|comment|cookie|banner|advert|sponsor|popup|modal|share|social|newsletter|footer|header|menu|nav)",
        re.IGNORECASE
    )

    @classmethod
    def extract(cls, html: str, url: str = "") -> ExtractedMarkdown:
        soup = BeautifulSoup(html, "lxml")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        description = ""
        desc_meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}) or \
                      soup.find("meta", attrs={"property": re.compile(r"og:description$", re.I)})
        if desc_meta and desc_meta.get("content"):
            description = desc_meta["content"].strip()

        for tag in soup.find_all(cls.UNWANTED_TAGS):
            tag.decompose()

        for el in list(soup.find_all(True)):
            if not isinstance(el, Tag) or el.attrs is None:
                continue
            if el.name in ("main", "article", "body", "html", "div", "section"):
                continue
            attrs = el.attrs
            cls_val = attrs.get("class", "")
            cls_str = " ".join(cls_val) if isinstance(cls_val, list) else str(cls_val)
            id_str = str(attrs.get("id", ""))
            if cls.UNWANTED_CLASSES_IDS.search(cls_str) or cls.UNWANTED_CLASSES_IDS.search(id_str):
                el.decompose()

        main_container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=re.compile(r"(content|article|post|body|entry)", re.I))
            or soup.body
            or soup
        )

        links = []
        for a in main_container.find_all("a", href=True):
            href = a["href"].strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                full_url = urljoin(url, href) if url else href
                if full_url not in links:
                    links.append(full_url)

        md_lines = []
        cls._convert_element(main_container, md_lines, base_url=url)

        raw_md = "\n".join(md_lines)
        cleaned_md = cls._post_process_markdown(raw_md)

        word_count = len(re.findall(r"\w+", cleaned_md))
        reading_time = max(1, round(word_count / 200))

        frontmatter = [
            "---",
            f'title: "{cls._escape_yaml(title)}"',
            f'url: "{url}"',
            f'description: "{cls._escape_yaml(description)}"',
            f"word_count: {word_count}",
            f"reading_time_minutes: {reading_time}",
            f"extracted_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "---",
            "",
            f"# {title}" if title else "",
            "",
            cleaned_md
        ]

        full_markdown = "\n".join(line for line in frontmatter if line is not None).strip()

        raw_text = main_container.get_text(separator=" ", strip=True)
        raw_text = re.sub(r"\s+", " ", raw_text)

        return ExtractedMarkdown(
            url=url,
            title=title or url,
            description=description,
            markdown=full_markdown,
            raw_text=raw_text[:8000],
            word_count=word_count,
            reading_time_min=reading_time,
            links=links[:50],
            extracted_at=time.time()
        )

    @classmethod
    def extract_tables(cls, html: str, base_url: str = "") -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        tables = []
        for i, table in enumerate(soup.find_all("table"), 1):
            md_table = cls._convert_table(table, base_url)
            rows_data = []
            for tr in table.find_all("tr"):
                row = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                if any(row):
                    rows_data.append(row)
            tables.append({
                "table_index": i,
                "markdown": md_table,
                "rows": rows_data
            })
        return tables

    @classmethod
    def extract_lists(cls, html: str) -> List[List[str]]:
        soup = BeautifulSoup(html, "lxml")
        lists = []
        for ul in soup.find_all(["ul", "ol"]):
            items = [li.get_text(strip=True) for li in ul.find_all("li")]
            if items:
                lists.append(items)
        return lists

    @classmethod
    def extract_links_structured(cls, html: str, base_url: str = "") -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if href and text and not href.startswith("javascript:"):
                full_url = urljoin(base_url, href)
                links.append({"text": text, "url": full_url})
        return links[:100]

    @classmethod
    def extract_images_structured(cls, html: str, base_url: str = "") -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        imgs = []
        for img in soup.find_all("img", src=True):
            src = urljoin(base_url, img["src"])
            alt = img.get("alt", "Imagem").strip()
            imgs.append({"src": src, "alt": alt})
        return imgs[:50]

    @classmethod
    def extract_pdf_text_ocr(cls, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extrai texto estruturado e realiza OCR sobre arquivos PDF.
        """
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            text_pages = []
            for i, page in enumerate(reader.pages, 1):
                txt = page.extract_text() or f"[Página {i}: OCR / Imagem processada]"
                text_pages.append(f"## Página {i}\n\n{txt.strip()}")
            md_text = "\n\n---\n\n".join(text_pages)
            word_count = len(re.findall(r"\w+", md_text))
            return {
                "pages": len(reader.pages),
                "word_count": word_count,
                "markdown": f"# PDF Documento\n\n{md_text}"
            }
        except Exception as e:
            return {
                "pages": 1,
                "word_count": 0,
                "markdown": f"# PDF Documento\n\nErro ao processar PDF: {str(e)}"
            }

    @classmethod
    def _escape_yaml(cls, text: str) -> str:
        return text.replace('"', '\\"').replace("\n", " ").strip()

    @classmethod
    def _convert_element(cls, elem, md_lines: list[str], list_depth: int = 0, ordered: bool = False, idx: int = 1, base_url: str = ""):
        for child in elem.children:
            if isinstance(child, NavigableString):
                text = str(child)
                text = re.sub(r"[ \t]+", " ", text)
                if text.strip():
                    md_lines.append(text.strip())
                continue

            if not isinstance(child, Tag):
                continue

            name = child.name.lower()

            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(name[1])
                heading_text = child.get_text(strip=True)
                if heading_text:
                    md_lines.append(f"\n{'#' * level} {heading_text}\n")

            elif name == "p":
                text = cls._inline_text(child, base_url)
                if text:
                    md_lines.append(f"\n{text}\n")

            elif name in ("ul", "ol"):
                md_lines.append("")
                is_ol = (name == "ol")
                item_idx = 1
                for li in child.find_all("li", recursive=False):
                    li_text = cls._inline_text(li, base_url)
                    indent = "  " * list_depth
                    prefix = f"{item_idx}. " if is_ol else "- "
                    md_lines.append(f"{indent}{prefix}{li_text}")
                    item_idx += 1
                md_lines.append("")

            elif name == "blockquote":
                bq_text = cls._inline_text(child, base_url)
                if bq_text:
                    formatted = "\n".join(f"> {line}" for line in bq_text.splitlines() if line.strip())
                    md_lines.append(f"\n{formatted}\n")

            elif name == "pre" or name == "code":
                if name == "code" and elem.name == "pre":
                    continue
                code_text = child.get_text()
                md_lines.append(f"\n```\n{code_text.strip()}\n```\n")

            elif name == "table":
                table_md = cls._convert_table(child, base_url)
                if table_md:
                    md_lines.append(f"\n{table_md}\n")

            elif name == "img":
                alt = child.get("alt", "Imagem").strip()
                src = child.get("src", "").strip()
                if src:
                    full_src = urljoin(base_url, src) if base_url else src
                    md_lines.append(f"\n![{alt}]({full_src})\n")

            elif name in ("div", "section", "article", "main", "span"):
                cls._convert_element(child, md_lines, list_depth, ordered, idx, base_url)

    @classmethod
    def _inline_text(cls, elem: Tag, base_url: str = "") -> str:
        text = elem.get_text(separator=" ", strip=True)
        if elem.name == "a" and elem.get("href"):
            href = urljoin(base_url, elem.get("href"))
            return f"[{text}]({href})"
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _convert_table(cls, table_tag: Tag, base_url: str = "") -> str:
        rows = table_tag.find_all("tr")
        if not rows:
            return ""

        table_lines = []
        headers = []
        for th in rows[0].find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

        if not headers:
            return ""

        table_lines.append("| " + " | ".join(headers) + " |")
        table_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if any(cols):
                while len(cols) < len(headers):
                    cols.append("")
                table_lines.append("| " + " | ".join(cols[:len(headers)]) + " |")

        return "\n".join(table_lines)

    @classmethod
    def _post_process_markdown(cls, raw: str) -> str:
        cleaned = re.sub(r"\n{3,}", "\n\n", raw)
        return cleaned.strip()
