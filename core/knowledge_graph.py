import re
import json
import os
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Set
from collections import Counter


@dataclass
class Entity:
    id: str
    name: str
    type: str  # person, technology, organization, place, concept, language, tool
    occurrences: int = 1
    sources: list[str] = field(default_factory=list)
    description: str = ""
    created_at: float = field(default_factory=time.time)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


@dataclass
class Relation:
    source_id: str
    target_id: str
    type: str  # uses, created_by, works_at, related_to, built_with, part_of
    weight: int = 1
    contexts: list[str] = field(default_factory=list)


class KnowledgeGraphEngine:
    """
    Revolutionary Knowledge Graph Engine v1.0
    - Zero-dependency NER using pattern-based entity extraction
    - Relation inference from sentence-level co-occurrence
    - Graph persistence in JSON format
    - Real-time incremental updates
    """

    GRAPH_PATH = os.path.expanduser("~/.rusyasearch/knowledge_graph.json")

    # Entity type detection patterns
    ENTITY_PATTERNS = {
        "technology": re.compile(
            r"\b(Python|JavaScript|TypeScript|Rust|Go|Golang|Java|C\+\+|C#|Ruby|PHP|Swift|Kotlin|"
            r"React|Vue\.?js|Angular|Svelte|Next\.?js|Nuxt\.?js|FastAPI|Django|Flask|Express\.?js|"
            r"Node\.?js|Docker|Kubernetes|K8s|AWS|Azure|GCP|Linux|Windows|macOS|"
            r"PostgreSQL|MySQL|MongoDB|Redis|SQLite|Elasticsearch|"
            r"Git|GitHub|GitLab|VS Code|Neovim|Vim|"
            r"TensorFlow|PyTorch|Keras|HuggingFace|OpenAI|Anthropic|Claude|GPT-?\d*|LLaMA|Mistral|"
            r"HTML|CSS|GraphQL|REST|gRPC|WebSocket|"
            r"LLM|AGI|NLP|CV|AI|ML|DL)\b",
            re.IGNORECASE
        ),
        "language": re.compile(
            r"\b(Portuguese|English|Spanish|French|German|Japanese|Chinese|Russian|"
            r"portugu[eê]s|ingl[eê]s|espanhol|franc[eê]s|alem[aã]o|japon[eê]s|"
            r"Portugu[eê]s|Ingl[eê]s|Espanhol)\b",
            re.IGNORECASE
        ),
        "organization": re.compile(
            r"\b(Google|Microsoft|Apple|Amazon|Meta|Facebook|Netflix|Tesla|SpaceX|OpenAI|"
            r"Anthropic|DeepMind|NVIDIA|Intel|AMD|Samsung|IBM|Oracle|"
            r"Mozilla|Linux Foundation|CNCF|Apache|"
            r"GitHub|Stack Overflow|Hacker News|Reddit|Twitter|X\.com|"
            r"MIT|Stanford|Harvard|Oxford|Cambridge|"
            r"Unicamp|USP|UFRJ|UFMG|UNESP|FGV)\b",
            re.IGNORECASE
        ),
        "person": re.compile(
            r"\b(Elon Musk|Sam Altman|Tim Berners-Lee|Linus Torvalds|Guido van Rossum|"
            r"Bill Gates|Mark Zuckerberg|Jeff Bezos|Sundar Pichai|Satya Nadella|"
            r"Andrej Karpathy|Yann LeCun|Geoffrey Hinton|Andrew Ng|"
            r"Ilya Sutskever|Dario Amodei|Daniela Amodei|"
            r"Richard Stallman|Donald Knuth|Bjarne Stroustrup)\b"
        ),
        "concept": re.compile(
            r"\b(machine learning|deep learning|reinforcement learning|neural network|"
            r"transformer|attention mechanism|fine-tuning|RAG|retrieval augmented|"
            r"embeddings|vector database|semantic search|"
            r"microservices|serverless|containerization|CI/CD|DevOps|"
            r"web scraping|crawling|indexing|inverted index|"
            r"knowledge graph|graph database|ontology|"
            r"zero-shot|few-shot|chain-of-thought|prompt engineering)\b",
            re.IGNORECASE
        ),
        "place": re.compile(
            r"\b(Silicon Valley|San Francisco|New York|London|Berlin|Tokyo|"
            r"T[uó]quio|Londres|Berlim|São Paulo|Rio de Janeiro|"
            r"California|Bay Area)\b",
            re.IGNORECASE
        )
    }

    # Relationship inference patterns (sentence-level)
    RELATION_PATTERNS = {
        "created_by": re.compile(r"(.+?)\s+(?:created|founded|built|developed|launched|invented)\s+(.+)", re.I),
        "works_at": re.compile(r"(.+?)\s+(?:works?\s+at|leads?\s+|CEO\s+of|CTO\s+of|runs?|heads?)\s+(.+)", re.I),
        "uses": re.compile(r"(.+?)\s+(?:uses?|utilizes?|relies?\s+on|built\s+with|powered\s+by|uses?)\s+(.+)", re.I),
        "part_of": re.compile(r"(.+?)\s+(?:is\s+part\s+of|belongs?\s+to|inside|within)\s+(.+)", re.I),
        "related_to": re.compile(r"(.+?)\s+(?:related\s+to|similar\s+to|compared\s+to|versus|vs\.?)\s+(.+)", re.I),
    }

    @classmethod
    def load(cls) -> Dict[str, Any]:
        if os.path.exists(cls.GRAPH_PATH):
            try:
                with open(cls.GRAPH_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"entities": {}, "relations": [], "last_updated": 0}

    @classmethod
    def save(cls, graph: Dict[str, Any]):
        os.makedirs(os.path.dirname(cls.GRAPH_PATH), exist_ok=True)
        graph["last_updated"] = time.time()
        with open(cls.GRAPH_PATH, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    @classmethod
    def _make_entity_id(cls, name: str, entity_type: str) -> str:
        raw = f"{name.lower().strip()}:{entity_type}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @classmethod
    def extract_entities(cls, text: str, source_url: str = "") -> List[Entity]:
        entities = []
        seen = set()

        for etype, pattern in cls.ENTITY_PATTERNS.items():
            matches = pattern.findall(text)
            counter = Counter(m.strip() for m in matches if len(m.strip()) > 1)

            for name, count in counter.items():
                eid = cls._make_entity_id(name, etype)
                if eid not in seen:
                    seen.add(eid)
                    entities.append(Entity(
                        id=eid,
                        name=name.strip(),
                        type=etype,
                        occurrences=count,
                        sources=[source_url] if source_url else []
                    ))

        return entities

    @classmethod
    def extract_relations(cls, text: str, found_entities: List[Entity]) -> List[Relation]:
        relations = []
        entity_names = {e.name.lower(): e.id for e in found_entities}
        sentences = re.split(r'[.!?;]\s+', text)

        for sentence in sentences:
            sentence_lower = sentence.lower()
            present = [name for name in entity_names if name in sentence_lower]

            if len(present) < 2:
                continue

            for rtype, pattern in cls.RELATION_PATTERNS.items():
                match = pattern.search(sentence)
                if match:
                    src_text = match.group(1).lower().strip()
                    tgt_text = match.group(2).lower().strip()

                    src_id = None
                    tgt_id = None
                    for name, eid in entity_names.items():
                        if name in src_text:
                            src_id = eid
                        if name in tgt_text:
                            tgt_id = eid

                    if src_id and tgt_id and src_id != tgt_id:
                        relations.append(Relation(
                            source_id=src_id,
                            target_id=tgt_id,
                            type=rtype,
                            weight=1,
                            contexts=[sentence.strip()[:200]]
                        ))

            if len(present) >= 2:
                names_sorted = sorted(present[:3])
                for i in range(len(names_sorted)):
                    for j in range(i + 1, len(names_sorted)):
                        eid_a = entity_names[names_sorted[i]]
                        eid_b = entity_names[names_sorted[j]]
                        relations.append(Relation(
                            source_id=eid_a,
                            target_id=eid_b,
                            type="co_occurs",
                            weight=1,
                            contexts=[sentence.strip()[:200]]
                        ))

        return relations

    @classmethod
    def ingest_text(cls, text: str, source_url: str = "") -> Dict[str, Any]:
        graph = cls.load()

        entities = cls.extract_entities(text, source_url)
        relations = cls.extract_relations(text, entities)

        for entity in entities:
            eid = entity.id
            if eid in graph["entities"]:
                existing = graph["entities"][eid]
                existing["occurrences"] = existing.get("occurrences", 0) + entity.occurrences
                if source_url and source_url not in existing.get("sources", []):
                    existing.setdefault("sources", []).append(source_url)
            else:
                graph["entities"][eid] = asdict(entity)

        for rel in relations:
            existing_match = None
            for i, r in enumerate(graph["relations"]):
                if (r["source_id"] == rel.source_id and
                    r["target_id"] == rel.target_id and
                    r["type"] == rel.type):
                    existing_match = i
                    break

            if existing_match is not None:
                graph["relations"][existing_match]["weight"] = graph["relations"][existing_match].get("weight", 0) + 1
                ctx = rel.contexts[0] if rel.contexts else ""
                if ctx and ctx not in graph["relations"][existing_match].get("contexts", []):
                    graph["relations"][existing_match].setdefault("contexts", []).append(ctx)
            else:
                graph["relations"].append(asdict(rel))

        cls.save(graph)

        entity_count = len(graph["entities"])
        rel_count = len(graph["relations"])
        type_counts = Counter(e["type"] for e in graph["entities"].values())

        return {
            "entities_added": len(entities),
            "relations_added": len(relations),
            "total_entities": entity_count,
            "total_relations": rel_count,
            "entity_type_distribution": dict(type_counts),
            "top_entities": sorted(
                graph["entities"].values(),
                key=lambda x: x.get("occurrences", 0),
                reverse=True
            )[:20]
        }

    @classmethod
    def ingest_page(cls, title: str, content: str, url: str, markdown: str = "") -> Dict[str, Any]:
        combined_text = f"{title}\n{content}\n{markdown}"
        return cls.ingest_text(combined_text, source_url=url)

    @classmethod
    def get_graph_for_viz(cls, min_weight: int = 1, max_nodes: int = 150) -> Dict[str, Any]:
        graph = cls.load()

        entities = list(graph["entities"].values())
        entities.sort(key=lambda x: x.get("occurrences", 0), reverse=True)
        entities = entities[:max_nodes]

        entity_ids = {e["id"] for e in entities}

        nodes = []
        for e in entities:
            nodes.append({
                "id": e["id"],
                "name": e["name"],
                "type": e["type"],
                "size": min(30, 8 + e.get("occurrences", 1) * 3),
                "occurrences": e.get("occurrences", 1)
            })

        edges = []
        for r in graph["relations"]:
            if (r["source_id"] in entity_ids and
                r["target_id"] in entity_ids and
                r.get("weight", 1) >= min_weight):
                edges.append({
                    "source": r["source_id"],
                    "target": r["target_id"],
                    "type": r["type"],
                    "weight": r.get("weight", 1)
                })

        type_counts = Counter(e["type"] for e in entities)
        rel_type_counts = Counter(e["type"] for e in edges)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "entity_types": dict(type_counts),
                "relation_types": dict(rel_type_counts)
            },
            "last_updated": graph.get("last_updated", 0)
        }

    @classmethod
    def get_entity_detail(cls, entity_id: str) -> Optional[Dict[str, Any]]:
        graph = cls.load()

        entity = graph["entities"].get(entity_id)
        if not entity:
            return None

        related = []
        for r in graph["relations"]:
            if r["source_id"] == entity_id or r["target_id"] == entity_id:
                other_id = r["target_id"] if r["source_id"] == entity_id else r["source_id"]
                other = graph["entities"].get(other_id, {})
                related.append({
                    "entity_name": other.get("name", "?"),
                    "entity_type": other.get("type", "?"),
                    "relation_type": r["type"],
                    "weight": r.get("weight", 1),
                    "contexts": r.get("contexts", [])[:3]
                })

        related.sort(key=lambda x: x["weight"], reverse=True)

        return {
            "entity": entity,
            "related_entities": related[:30],
            "total_connections": len(related)
        }

    @classmethod
    def search_entities(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        graph = cls.load()
        q = query.lower()
        results = []

        for eid, e in graph["entities"].items():
            score = 0
            name_lower = e.get("name", "").lower()
            if q in name_lower:
                score = 10 + (10 - len(q))
            elif any(w in name_lower for w in q.split()):
                score = 5

            if score > 0:
                results.append({
                    "id": eid,
                    "name": e.get("name", ""),
                    "type": e.get("type", ""),
                    "occurrences": e.get("occurrences", 1),
                    "score": score
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    @classmethod
    def clear(cls):
        if os.path.exists(cls.GRAPH_PATH):
            os.remove(cls.GRAPH_PATH)
