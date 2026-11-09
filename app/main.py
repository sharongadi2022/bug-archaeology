from contextlib import asynccontextmanager
from typing import Any
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import json,os
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .rag import BugArchaeologyRAG
rag=None
@asynccontextmanager
async def lifespan(app):
 global rag
 rag=BugArchaeologyRAG()
 yield
 rag=None
app=FastAPI(title="Bug Archaeology API",version="1.0.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory="app/static"),name="static")
class AskRequest(BaseModel):
 question:str=Field(min_length=3,max_length=500)
 top_k:int=Field(default=4,ge=1,le=8)
class RepoRequest(BaseModel):
 owner:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.-]+$")
 repo:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.-]+$")
@app.get("/",include_in_schema=False)
def home():return FileResponse("app/static/index.html")
@app.get("/api/health")
def health():return {"status":"ok","indexed_sources":rag.collection.count() if rag else 0,"llm_enabled":bool(os.getenv("OPENAI_API_KEY","").strip())}
@app.get("/api/sources")
def sources():
 if rag is None:raise HTTPException(503,"Index is starting")
 return {"sources":rag.list_sources()}
@app.post("/api/ask")
def ask(payload:AskRequest):
 if rag is None:raise HTTPException(503,"Index is starting")
 return rag.answer(payload.question,payload.top_k)
@app.post("/api/index/github")
def index_github(payload:RepoRequest):
 if rag is None:raise HTTPException(503,"Index is starting")
 base="https://api.github.com/repos/"+payload.owner+"/"+payload.repo
 headers={"Accept":"application/vnd.github+json","User-Agent":"bug-archaeology-demo"}
 records=[]
 try:
  for endpoint,kind in [("commits","commit"),("issues?state=all&per_page=15","issue"),("pulls?state=all&per_page=15","pull_request")]:
   with urlopen(Request(base+"/"+endpoint,headers=headers),timeout=12) as response:items=json.loads(response.read().decode())
   for item in items[:15]:
    if kind=="commit":
     detail=item.get("commit",{});title=detail.get("message","Commit").splitlines()[0];text=detail.get("message",title);date=detail.get("author",{}).get("date","");url=item.get("html_url","");doc_id="gh-commit-"+item.get("sha","")[:12]
    else:
     if kind=="issue" and "pull_request" in item:continue
     title=item.get("title","Discussion");text=title+". "+(item.get("body") or "");date=item.get("created_at","");url=item.get("html_url","");doc_id="gh-"+kind+"-"+str(item.get("number",""))
    if text.strip():records.append({"id":doc_id,"type":kind,"title":title[:180],"date":date[:10],"url":url,"text":text[:6000]})
  return {"indexed":rag.add_records(records),"repository":payload.owner+"/"+payload.repo}
 except HTTPError as e:raise HTTPException(e.code,"GitHub could not return this repository history.")
 except (URLError,TimeoutError,json.JSONDecodeError):raise HTTPException(502,"Could not reach GitHub. Please try again.")
