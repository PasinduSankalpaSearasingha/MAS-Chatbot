import os
import threading
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Import logic from scraper_v2
from scraper_v2 import process_urls, extract_article_links

app = FastAPI(title="MAS ChatBot Scraper API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Templates & Static Files ---

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Models ---

class ScrapeRequest(BaseModel):
    urls: List[str]

class StatusResponse(BaseModel):
    status: str
    message: str
    logs: List[str]

# --- Global State ---

# In a real app, we'd use a database or a more robust task queue (Redis/Celery)
# but for this local tool, a simple memory store and threading will suffice.
task_status = {
    "is_running": False,
    "current_task": None,
    "logs": []
}

def log_to_task(message: str):
    """Callback for scraper to pipe logs to memory store."""
    task_status["logs"].append(message)
    print(f"WEB-LOG: {message}")

# --- Background Work ---

def background_scrape(urls: List[str]):
    task_status["is_running"] = True
    task_status["logs"] = []
    task_status["logs"].append(f"Starting scraping for {len(urls)} URLs...")
    
    try:
        process_urls(urls, log_fn=log_to_task)
        task_status["logs"].append("Scraping and ingestion finished successfully.")
    except Exception as e:
        task_status["logs"].append(f"Critical Error: {str(e)}")
    finally:
        task_status["is_running"] = False

# --- UI Routes ---

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- Endpoints ---

@app.post("/api/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    if task_status["is_running"]:
        raise HTTPException(status_code=400, detail="A scraping task is already in progress.")
    
    background_tasks.add_task(background_scrape, request.urls)
    return {"message": "Scraping task started.", "urls": request.urls}

@app.get("/api/status")
async def get_status():
    return {
        "is_running": task_status["is_running"],
        "logs": task_status["logs"][-50:] # Return last 50 logs
    }

@app.get("/api/search")
async def search_links(url: str):
    """
    Helper to extract links and next_link for paginated sources.
    """
    try:
        links, next_link = extract_article_links(url)
        return {
            "links": links,
            "next_link": next_link
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
