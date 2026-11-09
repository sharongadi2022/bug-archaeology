import os
from typing import Any
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from .sample_data import SAMPLE_RECORDS

class BugArchaeologyRAG:
 def __init__(self):
  self.client=chromadb.PersistentClient(path=os.getenv("CHROMA_PATH","./chroma_db"))
  self.collection=self.client.get_or_create_collection(name="repository_history",embedding_function=DefaultEmbeddingFunction(),metadata={"hnsw:space":"cosine"})
  existing=set(self.collection.get(include=[])["ids"])
  self.add_records([r for r in SAMPLE_RECORDS if r["id"] not in existing])
 def add_records(self,records:list[dict[str,Any]])->int:
  if not records:return 0
  self.collection.upsert(ids=[str(r["id"]) for r in records],documents=[r["text"] for r in records],metadatas=[{k:r.get(k,"") for k in ("type","title","date","url")} for r in records])
  return len(records)
 def retrieve(self,question:str,top_k:int=4)->list[dict[str,Any]]:
  count=self.collection.count()
  if not question.strip() or not count:return []
  result=self.collection.query(query_texts=[question],n_results=min(top_k,count),include=["documents","metadatas","distances"])
  docs,metas=result["documents"][0],result["metadatas"][0]
  return [{"id":i,"text":d,"type":m.get("type","document"),"title":m.get("title","Source"),"date":m.get("date",""),"url":m.get("url",""),"score":round(max(0,1-float(dist)),3)} for i,d,m,dist in zip(result["ids"][0],docs,metas,result["distances"][0])]
 def answer(self,question:str,top_k:int=4)->dict[str,Any]:
  sources=self.retrieve(question,top_k)
  if not sources:return {"answer":"I could not find relevant repository history. Try asking about a commit, PR, issue, retry or timeout.","sources":[]}
  chosen=sources[:2]
  answer="Here is what the repository history shows: "+" ".join(s["text"] for s in chosen)+" Retrieved evidence: "+", ".join("["+str(i+1)+"] "+s["title"] for i,s in enumerate(chosen))+". This answer is based on indexed records."
  key=os.getenv("OPENAI_API_KEY","").strip()
  if key:
   try:
    from openai import OpenAI
    evidence="\n\n".join("["+str(i+1)+"] "+s["title"]+": "+s["text"] for i,s in enumerate(sources))
    result=OpenAI(api_key=key).chat.completions.create(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),temperature=0.1,messages=[{"role":"system","content":"Answer only from supplied repository evidence. If evidence is insufficient, say so. Cite source numbers."},{"role":"user","content":"Question: "+question+"\n\nEvidence:\n"+evidence}])
    answer=result.choices[0].message.content or answer
   except Exception:pass
  return {"answer":answer,"sources":sources}
 def list_sources(self):
  result=self.collection.get(include=["metadatas"])
  return [{"id":i,**{k:m.get(k,"") for k in ("type","title","date","url")}} for i,m in zip(result["ids"],result["metadatas"])]
