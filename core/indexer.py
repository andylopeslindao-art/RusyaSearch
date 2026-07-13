import math
import re
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "whom", "where",
    "when", "why", "how", "not", "no", "nor", "so", "if", "then",
    "than", "too", "very", "just", "about", "above", "after", "again",
    "all", "also", "any", "as", "because", "before", "between", "both",
    "each", "few", "more", "most", "other", "some", "such", "into",
    "only", "own", "same", "through", "during", "out", "up", "down",
    "de", "do", "da", "em", "para", "com", "um", "uma", "os", "as",
    "no", "na", "dos", "das", "que", "se", "por", "mais", "e", "o",
    "a", "e", "ou", "isso", "isto", "ele", "ela", "nos", "eles",
}


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-záàâãéèêíïóôõúüç0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


@dataclass
class IndexEntry:
    doc_id: int
    url: str
    title: str
    description: str
    tf: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    markdown: str = ""
    word_count: int = 0
    reading_time_min: int = 1


class InvertedIndex:
    def __init__(self):
        self.index: dict[str, set[int]] = defaultdict(set)
        self.documents: dict[int, IndexEntry] = {}
        self.doc_count = 0
        self.avg_dl = 0
        self.doc_lengths: dict[int, int] = {}
        self._dirty = False

    def add_document(
        self,
        url: str,
        title: str,
        content: str,
        description: str = "",
        markdown: str = "",
        word_count: int = 0,
        reading_time_min: int = 1
    ) -> int:
        doc_id = self.doc_count
        self.doc_count += 1

        all_text = f"{title} {title} {content}"
        tokens = tokenize(all_text)
        self.doc_lengths[doc_id] = len(tokens)

        tf_counts = defaultdict(int)
        for token in tokens:
            tf_counts[token] += 1

        max_tf = max(tf_counts.values()) if tf_counts else 1
        tf = {t: 0.5 + 0.5 * (c / max_tf) for t, c in tf_counts.items()}

        for token in tf:
            self.index[token].add(doc_id)

        self.documents[doc_id] = IndexEntry(
            doc_id=doc_id,
            url=url,
            title=title,
            description=description[:300],
            tf=tf,
            markdown=markdown,
            word_count=word_count,
            reading_time_min=reading_time_min
        )

        self.avg_dl = sum(self.doc_lengths.values()) / max(self.doc_count, 1)
        self._dirty = True
        return doc_id

    def search(self, query: str, limit: int = 20) -> list[dict]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        candidate_scores = defaultdict(float)

        for token in query_tokens:
            matched_terms = [t for t in self.index.keys() if token in t or t in token]
            if not matched_terms:
                continue

            for term in matched_terms:
                doc_ids = self.index[term]
                idf = math.log((self.doc_count - len(doc_ids) + 0.5) / (len(doc_ids) + 0.5) + 1)
                sim_factor = 1.0 if term == token else 0.65

                for doc_id in doc_ids:
                    entry = self.documents[doc_id]
                    tf_val = entry.tf.get(term, 0)
                    dl = self.doc_lengths[doc_id]
                    norm = dl / self.avg_dl if self.avg_dl else 1
                    bm25_part = (tf_val * (1.5 + 1)) / (tf_val + 1.5 * (1 - 0.75 + 0.75 * norm))
                    candidate_scores[doc_id] += (idf * bm25_part * sim_factor)

        for doc_id in candidate_scores:
            title_bonus = 0
            entry = self.documents[doc_id]
            for token in query_tokens:
                if token in entry.title.lower():
                    title_bonus += 2.5
            candidate_scores[doc_id] *= (1 + title_bonus)

        sorted_docs = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        results = []
        for doc_id, score in sorted_docs:
            entry = self.documents[doc_id]
            results.append({
                "doc_id": entry.doc_id,
                "url": entry.url,
                "title": entry.title,
                "description": entry.description,
                "score": round(score, 4),
                "markdown": entry.markdown,
                "word_count": entry.word_count,
                "reading_time_min": entry.reading_time_min,
                "source": "Índice Local"
            })

        return results

    def save(self, path: str):
        data = {
            "doc_count": self.doc_count,
            "documents": {
                str(did): {
                    "url": e.url,
                    "title": e.title,
                    "description": e.description,
                    "tf": e.tf,
                    "markdown": e.markdown,
                    "word_count": e.word_count,
                    "reading_time_min": e.reading_time_min
                }
                for did, e in self.documents.items()
            },
            "doc_lengths": {str(k): v for k, v in self.doc_lengths.items()},
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._dirty = False

    @classmethod
    def load(cls, path: str) -> "InvertedIndex":
        idx = cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        idx.doc_count = data.get("doc_count", 0)
        for did_str, doc_data in data.get("documents", {}).items():
            did = int(did_str)
            entry = IndexEntry(
                doc_id=did,
                url=doc_data.get("url", ""),
                title=doc_data.get("title", ""),
                description=doc_data.get("description", ""),
                tf=doc_data.get("tf", {}),
                markdown=doc_data.get("markdown", ""),
                word_count=doc_data.get("word_count", 0),
                reading_time_min=doc_data.get("reading_time_min", 1)
            )
            idx.documents[did] = entry
            for token in entry.tf:
                idx.index[token].add(did)

        idx.doc_lengths = {int(k): v for k, v in data.get("doc_lengths", {}).items()}
        idx.avg_dl = sum(idx.doc_lengths.values()) / max(idx.doc_count, 1) if idx.doc_count else 0
        return idx
