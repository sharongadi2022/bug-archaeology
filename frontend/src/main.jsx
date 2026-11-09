import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, ArrowUpRight, BookOpen, Bot, Braces, Check, ChevronRight, CircleHelp, Clock3, Code2, Database, Github, GitCommitHorizontal, GitPullRequest, Layers3, MessageSquare, Network, Search, Send, ShieldCheck, Sparkles, Terminal, Zap } from "lucide-react";
import "./styles.css";

const API = "http://localhost:8000";
const examples = ["Why was the payment retry limit reduced?", "Has the checkout timeout bug happened before?", "Why does the profile endpoint clear its cache?"];
const sample = {
  "Why was the payment retry limit reduced?": {
    answer: "The retry limit was reduced from 10 to 3 because repeated payment-provider failures were keeping checkout requests open for too long. The team saw rate-limit responses (429s), which could block a request worker. PR #142 introduced a bounded retry count with exponential backoff; the related issue documents the original checkout hang.",
    sources: [
      {kind:"pull request",title:"PR #142 · Make payment retries bounded",date:"Feb 17, 2024",excerpt:"The team agreed to cap retries at 3 and use exponential backoff. This keeps the user request bounded.",url:"https://github.com/example/shop/pull/142",score:.94},
      {kind:"issue",title:"Issue #88 · Checkout hangs after repeated payment failures",date:"Feb 14, 2024",excerpt:"Checkout spun for a long time when the payment API was unavailable or rate limited.",url:"https://github.com/example/shop/issues/88",score:.88},
      {kind:"commit",title:"Reduce payment retry limit to prevent request lockups",date:"Feb 18, 2024",excerpt:"Changed retry_limit from 10 to 3 after repeated provider throttling.",url:"https://github.com/example/shop/commit/a1",score:.84}
    ]
  },
  "Has the checkout timeout bug happened before?": {
    answer: "Yes. The sample repository history contains Issue #88, where checkout requests remained open after repeated payment API failures. The investigation connected the delay to retries without an effective upper bound. PR #142 then capped retries at 3 and added exponential backoff.",
    sources: [
      {kind:"issue",title:"Issue #88 · Checkout hangs after repeated payment failures",date:"Feb 14, 2024",excerpt:"Users reported checkout spinning when the payment API was unavailable or rate limited.",url:"https://github.com/example/shop/issues/88",score:.96},
      {kind:"pull request",title:"PR #142 · Make payment retries bounded",date:"Feb 17, 2024",excerpt:"Cap retries at 3 and use exponential backoff.",url:"https://github.com/example/shop/pull/142",score:.91}
    ]
  },
  "Why does the profile endpoint clear its cache?": {
    answer: "The cache is cleared after a successful profile update to avoid returning stale data. Issue #103 described a case where the database write succeeded but the profile endpoint continued returning the previous display name until the cache TTL expired. The follow-up commit added explicit invalidation.",
    sources: [
      {kind:"issue",title:"Issue #103 · Updated profile still shows old values",date:"Mar 1, 2024",excerpt:"The database write succeeds; the cached response is not refreshed.",url:"https://github.com/example/shop/issues/103",score:.93},
      {kind:"commit",title:"Add cache invalidation after profile update",date:"Mar 3, 2024",excerpt:"Clear the profile cache after a successful profile write.",url:"https://github.com/example/shop/commit/b7",score:.89}
    ]
  }
};

function App() {
  const [question,setQuestion] = useState(examples[0]);
  const [result,setResult] = useState(sample[examples[0]]);
  const [loading,setLoading] = useState(false);
  const [apiMode,setApiMode] = useState("Sample workspace");
  const [active,setActive] = useState("Overview");
  const [apiStatus,setApiStatus] = useState("Checking");
  React.useEffect(()=>{fetch(API+"/health").then(r=>r.json()).then(d=>{setApiStatus("Connected");setApiMode(d.mode==="github"?"GitHub repository":"Local sample data");}).catch(()=>setApiStatus("Sample mode"));},[]);
  async function ask(q=question) {
    setQuestion(q); setLoading(true);
    try {
      const res=await fetch(API+"/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});
      if(!res.ok) throw new Error("API unavailable");
      const data=await res.json(); setResult({answer:data.answer,sources:data.sources});
      setApiMode(data.mode==="github"?"GitHub repository":"Local sample data");
    } catch {
      const key=Object.keys(sample).find(k=>k.toLowerCase()===q.toLowerCase()) || Object.keys(sample).find(k=>q.toLowerCase().split(" ").some(w=>w.length>4&&k.toLowerCase().includes(w)));
      setResult(sample[key] || {answer:"I couldn't find a matching example in the local demo. Start the FastAPI backend and ingest a repository to search its history. Try one of the suggested questions to explore the sample evidence.",sources:[]});
      setApiMode("Local sample data");
    }
    setLoading(false);
  }
  const nav=[["Overview",Activity],["Ask history",MessageSquare],["Architecture",Network],["Data sources",Database]];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Layers3 size={19}/></div><div><b>bug archaeology</b><small>REPOSITORY INTELLIGENCE</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      {nav.map(([label,Icon])=><button key={label} className={"nav-item "+(active===label?"selected":"")} onClick={()=>{setActive(label);if(label==="Ask history")document.getElementById("ask")?.scrollIntoView({behavior:"smooth"});if(label==="Architecture")document.getElementById("architecture")?.scrollIntoView({behavior:"smooth"});if(label==="Data sources")document.getElementById("sources")?.scrollIntoView({behavior:"smooth"});}}><Icon size={17}/>{label}{label==="Ask history"&&<span className="nav-dot"/>}</button>)}
      <div className="sidebar-bottom"><div className="status-card"><span className="status-led"/><div><b>System operational</b><small>{apiStatus==="Connected"?"API connected":"Demo available offline"}</small></div></div><div className="profile"><div className="avatar">SG</div><div><b>Sharon Gadi</b><small>Developer workspace</small></div><ChevronRight size={15}/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <ChevronRight size={14}/> <b>Overview</b></div><div className="top-actions"><span className="connection"><i/> {apiStatus==="Connected"?"API connected":"Demo mode"}</span><a className="github-link" href="https://github.com/sharongadi2022/bug-archaeology" target="_blank"><Github size={16}/> View repository <ArrowUpRight size={13}/></a></div></header>
      <div className="content">
        <div className="eyebrow"><span className="eyebrow-line"/> AI-POWERED CODEBASE MEMORY</div>
        <section className="hero"><div><h1>Understand the <em>why</em><br/>behind your code.</h1><p>Search the history behind every decision. Ask questions across commits, pull requests, issues and code — get answers grounded in evidence.</p><div className="hero-tags"><span><Sparkles size={13}/> Retrieval augmented generation</span><span><ShieldCheck size={13}/> Source-backed answers</span></div></div><div className="hero-art"><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="core"><Braces size={34}/></div><div className="float-node node-one"><GitCommitHorizontal size={16}/></div><div className="float-node node-two"><GitPullRequest size={16}/></div><div className="float-node node-three"><MessageSquare size={16}/></div><div className="art-caption">REPOSITORY MEMORY <span>● LIVE</span></div></div></section>
        <div className="metrics"><Metric icon={<Database/>} label="Indexed records" value="06" sub="Sample repository"/> <Metric icon={<Layers3/>} label="Source categories" value="04" sub="Commits · PRs · Issues · Code"/> <Metric icon={<Zap/>} label="Retrieval mode" value="RAG" sub={apiMode}/><Metric icon={<Clock3/>} label="Response style" value="Cited" sub="Evidence first"/></div>
        <section className="section" id="ask"><div className="section-head"><div><div className="eyebrow">INTERACTIVE PLAYGROUND</div><h2>Ask your repository</h2><p>Ask a question. The retriever finds relevant history and returns the evidence.</p></div><span className="demo-pill"><span/> LIVE DEMO</span></div>
          <div className="ask-panel"><div className="ask-top"><div className="ask-label"><Bot size={17}/> <b>Repository assistant</b><span className="model-tag">RAG ENGINE</span></div><span className="sample-label">● {apiMode}</span></div><div className="question-box"><Search size={18}/><input value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>e.key==="Enter"&&ask()} placeholder="Ask why a change was made..."/><button onClick={()=>ask()} disabled={loading}>{loading?"Searching":<>Ask <Send size={14}/></>}</button></div><div className="suggestions"><span>TRY ASKING</span>{examples.map(q=><button key={q} onClick={()=>ask(q)}>{q}</button>)}</div>
            <div className="answer-wrap"><div className="answer-heading"><div className="ai-icon"><Sparkles size={15}/></div><div><b>Generated insight</b><small>Grounded in retrieved repository context</small></div><span className="grounded"><Check size={12}/> EVIDENCE LINKED</span></div><p className="answer-text">{loading?"Searching repository history and ranking relevant evidence…":result.answer}</p>
              <div className="source-heading"><span>RETRIEVED SOURCES</span><span>{result.sources?.length||0} MATCHES</span></div>
              <div className="source-list">{(result.sources||[]).map((s,i)=><a className="source-row" key={s.title+i} href={s.url||"#"} target="_blank"><div className={"source-icon "+s.kind.replace(" ","-")}>{s.kind==="commit"?<GitCommitHorizontal/>:s.kind==="pull request"?<GitPullRequest/>:s.kind==="issue"?<CircleHelp/>:<Code2/>}</div><div className="source-info"><b>{s.title}</b><small>{s.kind} {s.date&&"· "+s.date}</small><p>{s.excerpt}</p></div><div className="score"><b>{Math.round((s.score||0)*100)}%</b><small>match</small></div><ArrowUpRight size={14} className="source-arrow"/></a>)}{!result.sources?.length&&<div className="empty-sources">Run a suggested question to see its evidence.</div>}</div>
            </div>
          </div>
        </section>
        <section className="section" id="architecture"><div className="eyebrow">UNDER THE HOOD</div><h2>How the system works</h2><p className="section-sub">Two simple flows: index repository knowledge once, then retrieve it whenever a developer asks.</p>
          <div className="architecture"><div className="flow-label">01 / INDEXING · RUN ONCE, UPDATE WHEN REPO CHANGES</div><div className="flow-row"><Flow icon={<Github/>} title="GitHub API" text="Commits · PRs · issues · code"/><ChevronRight/><Flow icon={<Braces/>} title="Chunking" text="Split by source type"/><ChevronRight/><Flow icon={<Sparkles/>} title="Embeddings" text="Text → vectors"/><ChevronRight/><Flow icon={<Database/>} title="Vector store" text="ChromaDB"/></div><div className="flow-divider"><span>STORED KNOWLEDGE</span></div><div className="flow-label">02 / QUESTION ANSWERING · EVERY USER QUERY</div><div className="flow-row second"><Flow icon={<MessageSquare/>} title="Question" text="Developer asks"/><ChevronRight/><Flow icon={<Search/>} title="Retriever" text="Top matching chunks"/><ChevronRight/><Flow icon={<Bot/>} title="LLM" text="Grounded response"/><ChevronRight/><Flow icon={<BookOpen/>} title="Citations" text="Answer + sources"/></div></div>
          <div className="concept-grid"><Concept icon={<Layers3/>} title="Source-aware chunking" text="Code is split around functions; commits stay compact; long discussions are split into smaller passages."/><Concept icon={<Network/>} title="Semantic retrieval" text="Embeddings represent meaning, helping similar ideas match even when wording differs."/><Concept icon={<ShieldCheck/>} title="Grounded generation" text="The answer is based on retrieved context, and every result links back to its original source." /></div>
        </section>
        <section className="section" id="sources"><div className="eyebrow">KNOWLEDGE BASE</div><h2>What gets indexed</h2><p className="section-sub">A repository's reasoning is spread across more than source code.</p><div className="data-grid"><DataCard icon={<GitCommitHorizontal/>} title="Commits" count="Change history" text="What changed and the message attached to it."/><DataCard icon={<GitPullRequest/>} title="Pull requests" count="Design discussions" text="Trade-offs, reviews and why a change was accepted."/><DataCard icon={<CircleHelp/>} title="Issues" count="Bug reports" text="Symptoms, reproduction steps and prior fixes."/><DataCard icon={<Code2/>} title="Source code" count="Current implementation" text="Functions and classes connected to the discussion." /></div></section>
        <footer><div className="brand-mini"><div className="brand-mark"><Layers3 size={14}/></div><b>bug archaeology</b></div><span>Built to make repository knowledge easier to find.</span><a href="https://github.com/sharongadi2022/bug-archaeology" target="_blank">Source code <ArrowUpRight size={12}/></a></footer>
      </div>
    </main>
  </div>;
}
function Metric({icon,label,value,sub}){return <div className="metric"><div className="metric-top"><span>{icon}</span><small>{label}</small></div><strong>{value}</strong><p>{sub}</p></div>}
function Flow({icon,title,text}){return <div className="flow-node"><div>{icon}</div><b>{title}</b><small>{text}</small></div>}
function Concept({icon,title,text}){return <div className="concept"><div className="concept-icon">{icon}</div><b>{title}</b><p>{text}</p></div>}
function DataCard({icon,title,count,text}){return <div className="data-card"><div className="data-icon">{icon}</div><div><b>{title}</b><small>{count}</small><p>{text}</p></div><ArrowUpRight size={14}/></div>}
createRoot(document.getElementById("root")).render(<App/>);
