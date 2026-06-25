import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

# Import internal modules
from backend.crawler import WebCrawler
from backend.ingest import process_documents
from backend.vector_store import VectorStore
from backend.pinecone_store import upsert_chunks, search_chunks
from backend.models import get_embeddings_batch, get_query_embedding, generate_answer

# Load initial environment
load_dotenv()

app = FastAPI(title="RAG-Powered Website Chatbot API")

# Initialize global VectorStore
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(DATA_DIR, exist_ok=True)
vector_db = VectorStore()
vector_db.load(DATA_DIR)

# Global crawl state
crawl_state = {
    "status": "idle",
    "current_url": "",
    "pages_crawled": 0,
    "queue_size": 0,
    "message": "",
    "total_chunks": 0
}

# Request/Response schemas
class SettingsRequest(BaseModel):
    groq_api_key: str

class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 30
    depth_limit: int = 2
    chunk_size: int = 600
    chunk_overlap: int = 100

class QueryRequest(BaseModel):
    query: str
    top_k: int = 8

def get_api_key() -> str:
    """Helper to retrieve active Groq API key."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=400, detail="Groq API Key is not configured. Please add it in Settings.")
    return key

# Background worker for web crawl and embedding ingestion (Completely Local)
def run_crawl_and_ingest_task(url: str, max_pages: int, depth_limit: int, chunk_size: int, chunk_overlap: int):
    global crawl_state
    
    crawl_state["status"] = "crawling"
    crawl_state["pages_crawled"] = 0
    crawl_state["queue_size"] = 0
    crawl_state["message"] = "Initializing local web scraper..."

    # 1. Start Crawler
    crawler = WebCrawler(max_pages=max_pages, depth_limit=depth_limit)
    
    def on_progress(msg: str, count: int, q_size: int):
        crawl_state["current_url"] = msg
        crawl_state["pages_crawled"] = count
        crawl_state["queue_size"] = q_size
        crawl_state["message"] = f"Scraping... ({count} pages completed)"

    documents = crawler.crawl(url, progress_callback=on_progress)
    
    if not documents:
        crawl_state["status"] = "failed"
        crawl_state["message"] = "Scraping completed but no text pages were extracted."
        return

    # 2. Text Chunking
    crawl_state["status"] = "indexing"
    crawl_state["message"] = "Splitting scraped pages into chunks..."
    chunks = process_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    if not chunks:
        crawl_state["status"] = "failed"
        crawl_state["message"] = "Text chunking produced zero segments."
        return

    # 3. Generate Embeddings & Index (Locally using SentenceTransformers)
    crawl_state["message"] = f"Generating local vector embeddings for {len(chunks)} chunks..."
    try:
       texts_to_embed = [chunk["text"] for chunk in chunks]
       embeddings = get_embeddings_batch(texts_to_embed)

    # Add to vector store
       vector_db.add_chunks(chunks, embeddings)
       vector_db.save(DATA_DIR)

    # Pinecone storage
       upsert_chunks(chunks, embeddings)

       crawl_state["status"] = "completed"
       crawl_state["message"] = (
           f"Successfully crawled {len(documents)} pages "
           f"and indexed {len(chunks)} text chunks."
       )
       crawl_state["total_chunks"] = vector_db.get_chunk_count()

    except Exception as e:
          crawl_state["status"] = "failed"
          crawl_state["message"] = (
                  f"Error during local embedding generation: {str(e)}"
          )
# Endpoints
@app.get("/api/settings")
def get_settings():
    key = os.environ.get("GROQ_API_KEY", "")
    has_key = len(key) > 0
    # Return masked version if present
    masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****" if has_key else ""
    return {"has_key": has_key, "masked_key": masked_key}

@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    key = req.groq_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key cannot be empty.")
    
    # Save to local .env in root directory
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    set_key(env_path, "GROQ_API_KEY", key)
    os.environ["GROQ_API_KEY"] = key
    return {"status": "success", "message": "Groq API key updated successfully."}

@app.post("/api/crawl")
def start_crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    global crawl_state
    
    # Simple URL verification
    if not req.url.startswith("http://") and not req.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")
        
    if crawl_state["status"] in ["crawling", "indexing"]:
        raise HTTPException(status_code=400, detail="A crawl job is already in progress.")

    # Queue background task (No API Key needed for local crawl)
    background_tasks.add_task(
        run_crawl_and_ingest_task,
        url=req.url,
        max_pages=req.max_pages,
        depth_limit=req.depth_limit,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap
    )
    
    # Reset state
    crawl_state = {
        "status": "crawling",
        "current_url": req.url,
        "pages_crawled": 0,
        "queue_size": 0,
        "message": "Initiating local crawl job in the background...",
        "total_chunks": vector_db.get_chunk_count()
    }
    
    return {"status": "success", "message": "Crawling started in background."}

@app.get("/api/crawl/status")
def get_crawl_status():
    global crawl_state
    crawl_state["total_chunks"] = vector_db.get_chunk_count()
    return crawl_state

@app.post("/api/query")
def run_query(req: QueryRequest):
    # Requires Groq key for LLM generation
    api_key = get_api_key()
    
    if vector_db.get_chunk_count() == 0:
        raise HTTPException(status_code=400, detail="The vector index is empty. Please crawl a website first.")
        
    try:
        # Embed query locally
        q_emb = get_query_embedding(req.query)
        
        # Search
        results = search_chunks(
             q_emb,
             req.top_k
        )
        
        if not results:
            return {"answer": "No relevant website content matched your query.", "sources": []}
            
        # Parse context chunks and unique sources
        context_chunks = [item[0] for item in results]
        sources = []
        seen_urls = set()
        
        for item, score in results:
            url = item.get("url")
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append({
                    "url": url,
                    "title": item.get("title", "Untitled Page"),
                    "score": score
                })
                
        # Generate Answer using Groq API
        answer = generate_answer(req.query, context_chunks, api_key)
        
        return {
            "answer": answer,
            "sources": sources,
            "chunks": [{"url": c.get("url"), "title": c.get("title"), "text": c.get("text")} for c in context_chunks]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")

@app.get("/api/sources")
def get_sources():
    unique_sources = {}
    for item in vector_db.metadata:
        url = item.get("url")
        if url and url not in unique_sources:
            unique_sources[url] = {
                "url": url,
                "title": item.get("title", "Untitled Page"),
                "chunk_count": sum(1 for x in vector_db.metadata if x.get("url") == url)
            }
    return {
        "sources": list(unique_sources.values()),
        "total_documents": len(unique_sources),
        "total_chunks": vector_db.get_chunk_count()
    }

@app.post("/api/sources/clear")
def clear_sources():
    vector_db.clear()
    vector_db.save(DATA_DIR)
    
    global crawl_state
    crawl_state = {
        "status": "idle",
        "current_url": "",
        "pages_crawled": 0,
        "queue_size": 0,
        "message": "Index cleared.",
        "total_chunks": 0
    }
    return {"status": "success", "message": "Index cleared successfully."}

# Mount static frontend directory
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

# Serve frontend assets
@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend files not found."}

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
