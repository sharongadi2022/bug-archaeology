import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import AskRequest, AskResponse, Source, IngestResponse
from .ingest import fetch_repository_history
from .retrieval import get_records, keyword_search, vector_search, answer_from_evidence

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
app = FastAPI(title="Bug Archaeology API", version="1.0.0",
              description="Repository history search with evidence-backed answers.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

records = get_records()
mode = "sample"


@app.get("/")
def root():
    return {"name": "Bug Archaeology API", "status": "ok", "mode": mode}


@app.get("/health")
def health():
    return {"status": "healthy", "records": len(records), "mode": mode}


@app.get("/stats")
def stats():
    kinds = {}
    for record in records:
        kinds[record.get("kind", "other")] = kinds.get(record.get("kind", "other"), 0) + 1
    return {"repository": os.getenv("GITHUB_REPO", "sample/shop"), "total": len(records),
            "types": kinds, "mode": mode}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    hits = vector_search(payload.question, records) if os.getenv("USE_CHROMA", "false").lower() == "true" else keyword_search(payload.question, records)
    answer = answer_from_evidence(payload.question, hits)
    sources = [Source(id=str(x.get("id", "")), kind=x.get("kind", "record"),
                      title=x.get("title", "Untitled"), excerpt=x.get("text", "")[:260],
                      url=x.get("url", ""), date=x.get("date", ""), score=float(x.get("score", 0)))
               for x in hits]
    return AskResponse(answer=answer, sources=sources, mode=mode)


@app.post("/ingest", response_model=IngestResponse)
def ingest():
    global records, mode
    repo = os.getenv("GITHUB_REPO", "").strip()
    if not repo or "/" not in repo:
        raise HTTPException(400, "Set GITHUB_REPO=owner/repository in backend/.env")
    try:
        records = fetch_repository_history(repo)
        mode = "github"
        return IngestResponse(indexed=len(records), message="Repository history indexed.",
                              repository=repo)
    except Exception as exc:
        raise HTTPException(502, f"GitHub ingestion failed: {exc}")
