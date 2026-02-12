import os
import json
import requests
import threading
import queue


from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# LangChain components for robust vector store handling
from langchain_openai import AzureOpenAIEmbeddings
from langchain_astradb import AstraDBVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# --- Configuration & Utility Functions ---

def _ensure_user_agent():
    if not os.getenv("USER_AGENT"):
        os.environ["USER_AGENT"] = "MAS-ChatBot-UnifiedScraper/1.0"

def _load_json_data(json_path):
    """Loads the main data store from JSON."""
    if not os.path.exists(json_path):
        return {"articles": [], "next_link": None}
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        # Handle cases where JSON might just be a list
        if isinstance(data, list):
            return {"articles": data, "next_link": None}
        return data
    except Exception:
        return {"articles": [], "next_link": None}

def _save_json_data(json_path, data):
    """Saves the main data store to JSON."""
    try:
        abs_path = os.path.abspath(json_path)
        temp_path = abs_path + ".tmp"
        
        # Write to temp file first
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            
        # Atomic replace
        if os.path.exists(abs_path):
            os.remove(abs_path)
        os.rename(temp_path, abs_path)
        
    except Exception as e:
        print(f"DEBUG: Failed to save JSON: {e}")
        raise e

# --- Scraping Logic ---

def extract_article_links(list_url):
    """
    Extracts article links from a list/category page.
    Specially handles pagination links (Next/Page X).
    """
    _ensure_user_agent()
    headers = {"User-Agent": os.environ["USER_AGENT"]}
    try:
        response = requests.get(list_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        # Identifying article links based on common MAS/Island patterns
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Heuristic for article links
            is_article = any(term in href.lower() for term in ['/article/', '/news/'])
            # Additional heuristic for Island.lk (usually domain.lk/slug/)
            if 'island.lk' in href.lower() and href.count('/') == 3:
                # Basic check to avoid homepage, category, or search pages again
                if not any(x in href.lower() for x in ['/category/', '/page/', '?s=']):
                    is_article = True

            if is_article:
                if not href.startswith('http'):
                    href = requests.compat.urljoin(list_url, href)
                # Filter to relevant domains and ensure MAS is mentioned if it's a search result
                domain_match = 'wtin.com' in href or 'island.lk' in href or 'mas' in href.lower()
                if href not in links and domain_match:
                    links.append(href)
        
        # Find "Next" link for pagination
        next_link = None
        next_tag = soup.find('a', string=lambda s: s and ('Next' in s or '›' in s))
        if not next_tag:
            next_tag = soup.find('a', rel='next')
            
        if next_tag and next_tag.has_attr('href'):
            next_link = requests.compat.urljoin(list_url, next_tag['href'])
            
        return links, next_link
    except Exception as e:
        print(f"Failed to extract links from {list_url}: {e}")
        return [], None

def scrape_article_content(url):
    """
    Scrapes the content of a single article.
    Targets main text areas while excluding nav/footers.
    """
    headers = {"User-Agent": os.environ.get("USER_AGENT", "MAS-ChatBot-UnifiedScraper/1.0")}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find(['h1', 'title'])
        title = title_tag.get_text().strip() if title_tag else "Unknown Title"
        
        # Target common content wrappers
        content_div = soup.find('article') or soup.find('main') or soup.find('div', class_='entry-content') or soup.find('body')
        if content_div:
            # Extract paragraphs
            p_tags = content_div.find_all(['p', 'h2', 'h3'])
            combined_text = "\n\n".join(p.get_text().strip() for p in p_tags if p.get_text().strip())
        else:
            combined_text = ""
        
        if not combined_text:
            return None
                
        return {
            "url": url,
            "title": title,
            "text": combined_text,
            "success": True,
            "extracted_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Failed to scrape article {url}: {e}")
        return None

# --- Ingestion & Vector Store Logic ---

def ingest_data_to_astra(articles, log_fn=print):
    """
    Takes a list of article objects, chunks them, and uploads to Astra DB.
    Uses LangChain for robust embedding and storage.
    """
    if not articles:
        log_fn("No new articles to ingest.")
        return

    log_fn(f"Preparing {len(articles)} articles for Astra DB ingestion...")
    
    # Convert to LangChain Documents
    documents = []
    for art in articles:
        documents.append(Document(
            page_content=art['text'],
            metadata={"source": art['url'], "title": art['title'], "extracted_at": art['extracted_at']}
        ))

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=150
    )
    final_chunks = text_splitter.split_documents(documents)
    log_fn(f"Created {len(final_chunks)} chunks from extraction.")

    # Setup Azure OpenAI Embeddings
    try:
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
        )

        # Connect to AstraDB
        vstore = AstraDBVectorStore(
            embedding=embeddings,
            collection_name=os.getenv("ASTRA_DB_COLLECTION"),
            token=os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
            api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
        )

        log_fn("Uploading chunks to Astra DB...")
        vstore.add_documents(final_chunks)
        log_fn("Successfully updated Astra DB Vector Store.")
    except Exception as exc:
        log_fn(f"Astra DB ingestion failed: {exc}")

# --- Integrated Workflow --

def process_urls(urls, log_fn=print, json_path="pr_articles_extracted.json"):
    """
    Core workflow: Scrape -> Save to JSON -> Ingest to Astra DB.
    """
    abs_json_path = os.path.abspath(json_path)
    log_fn(f"Processing using JSON file at: {abs_json_path}")

    data_store = _load_json_data(json_path)
    initial_count = len(data_store.get("articles", []))
    log_fn(f"Initial articles in DB: {initial_count}")

    # Normalize URLs for duplicate checking (strip http/https and trailing slashes)
    def normalize(u):
        return u.replace("https://", "").replace("http://", "").rstrip("/")
    
    existing_normalized = {normalize(a.get("url")) for a in data_store["articles"] if a.get("url")}
    
    new_articles = []
    
    for url in urls:
        norm_url = normalize(url)
        if norm_url in existing_normalized:
            log_fn(f"SKIPPING DUPLICATE: {url}")
            continue
            
        log_fn(f"SCRAPING: {url}")
        content = scrape_article_content(url)
        if content:
            # Append locally
            data_store["articles"].append(content)
            new_articles.append(content)
            existing_normalized.add(norm_url)
            
            # Persist immediately
            try:
                _save_json_data(json_path, data_store)
                log_fn(f"SUCCESS: Saved article '{content['title']}' to JSON.")
                log_fn(f"STATS: Total articles now: {len(data_store['articles'])}")
            except Exception as e:
                log_fn(f"ERROR: Could not save to JSON file: {e}")
        else:
            log_fn(f"FAILURE: Could not extract content from: {url}")
            
    if new_articles:
        ingest_data_to_astra(new_articles, log_fn=log_fn)
    else:
        log_fn("INFO: No new articles were scraped.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # CLI Mode
        start_url = sys.argv[1]
        if "island.lk" in start_url and "?s=" in start_url:
            # Paginated extraction
            print(f"Paginated extraction started for: {start_url}")
            links, next_link = extract_article_links(start_url)
            print(f"Found {len(links)} links. Next page: {next_link}")
            
            # Update next_link in JSON
            data_store = _load_json_data("pr_articles_extracted.json")
            data_store["next_link"] = next_link
            _save_json_data("pr_articles_extracted.json", data_store)
            
            process_urls(links)
            if next_link:
                print(f"NEXT LINK available: {next_link}")
                print("Suggestion: Run the script again with the NEXT LINK to continue.")
        else:
            # Single URL or manual list
            process_urls(sys.argv[1:])
    else:
        print("Usage: python scraper_v2.py <url> OR run server.py for Web UI")
