import os
import re
from collections import Counter
from pathlib import Path


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def keyword_search(question: str, records: list[dict], limit: int = 5) -> list[dict]:
    """Small dependency-free baseline retriever; replace with vector search when enabled."""
    query = Counter(_tokens(question))
    scored = []
    for record in records:
        words = Counter(_tokens(record.get("title", "") + " " + record.get("text", "")))
        overlap = sum(min(count, words[token]) for token, count in query.items())
        if overlap:
            score = overlap / max(1, sum(query.values())) + overlap / max(8, sum(words.values()))
            scored.append(({**record, "score": round(score, 3)}, score))
    return [item for item, _ in sorted(scored, key=lambda x: x[1], reverse=True)[:limit]]


def vector_search(question: str, records: list[dict], limit: int = 5) -> list[dict]:
    """Optional local Chroma + sentence-transformers path."""
    try:
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_core.documents import Document
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        docs = [Document(page_content=r["title"] + "\n" + r["text"], metadata=r)
                for r in records]
        store = Chroma.from_documents(docs, embeddings, collection_name="bug_archaeology")
        hits = store.similarity_search_with_relevance_scores(question, k=limit)
        return [{**doc.metadata, "text": doc.page_content, "score": float(score)}
                for doc, score in hits]
    except Exception:
        return keyword_search(question, records, limit)


def answer_from_evidence(question: str, sources: list[dict]) -> str:
    if not sources:
        return ("I couldn't find enough repository history to answer that. "
                "Try a function name, error message, feature or issue number.")
    context = "\n".join(f"- {s.get('title')}: {s.get('text', '')[:420]}" for s in sources[:4])
    ollama_url = os.getenv("OLLAMA_URL", "").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    if ollama_url:
        try:
            import requests
            response = requests.post(f"{ollama_url}/api/generate", json={
                "model": model,
                "prompt": ("Answer the question using only the repository evidence below. "
                           "If the evidence does not contain the answer, say so. Be concise.\n\n"
                           f"Evidence:\n{context}\n\nQuestion: {question}"),
                "stream": False
            }, timeout=45)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception:
            pass
    lead = sources[0]
    return (f"The strongest match is **{lead.get('title', 'this repository record')}**. "
            f"{lead.get('text', '')[:500]} "
            "This answer is an evidence summary, not a generated conclusion; open the sources below "
            "to verify the original discussion.")


def get_records() -> list[dict]:
    from .ingest import load_sample
    path = Path(__file__).with_name("sample_data.json")
    return load_sample(str(path))
