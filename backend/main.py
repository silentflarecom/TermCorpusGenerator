import os
import json
import csv
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import wikipediaapi
from typing import List

# Import new modules
from models import (
    TermResponse, BatchTaskCreate, BatchTaskResponse,
    TaskStatus, TermDetail, TaskListItem
)
from database import (
    init_database, create_batch_task, add_terms_to_task,
    get_task_status, get_task_terms, get_all_tasks,
    update_task_counters, get_term_associations,
    check_existing_terms, delete_task, reset_database, get_corpus_statistics,
    analyze_data_quality, clean_task_data, get_terms_by_quality_issue
)
from scheduler import start_batch_crawl, cancel_batch_crawl, retry_failed_terms
from models import Association

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()
    print("✓ Database initialized")
    yield
    # Shutdown (if needed)

app = FastAPI(lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Wikipedia API
# User-Agent is explicitly set to comply with Wikimedia User-Agent Policy
# https://meta.wikimedia.org/wiki/User-Agent_policy
USER_AGENT = 'WikipediaTermCorpusGenerator/1.0 (Student Project; contact@silentflare.com; https://github.com/silentflarecom/WikipediaPython)'

wiki_en = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT,
    language='en'
)

# Output directory
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== Single Search Endpoint (Existing) ==========

@app.get("/search", response_model=TermResponse)
def search_term(term: str):
    page_en = wiki_en.page(term)

    if not page_en.exists():
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found in English Wikipedia.")

    # Get English data
    en_summary = page_en.summary[0:1000] + "..." if len(page_en.summary) > 1000 else page_en.summary
    en_url = page_en.fullurl

    # Get Chinese data via langlinks
    langlinks = page_en.langlinks
    zh_summary = "Translation not found."
    zh_url = ""

    if 'zh' in langlinks:
        # We need to initialize a Chinese wikipedia object to correctly fetch the summary
        wiki_zh = wikipediaapi.Wikipedia(
             user_agent='TermCorpusGenerator/1.0 (contact@example.com)',
             language='zh'
        )
        # Get the title from the langlink and fetch the page
        zh_title = langlinks['zh'].title
        page_zh = wiki_zh.page(zh_title)
        
        if page_zh.exists():
            zh_summary = page_zh.summary[0:1000] + "..." if len(page_zh.summary) > 1000 else page_zh.summary
            zh_url = page_zh.fullurl

    result = {
        "term": term,
        "en_summary": en_summary,
        "en_url": en_url,
        "zh_summary": zh_summary,
        "zh_url": zh_url
    }

    # Save to Markdown
    filename = f"{term.replace(' ', '_')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {term}\n\n")
            f.write(f"## English\n{en_summary}\n\n[Link]({en_url})\n\n")
            f.write(f"## Chinese\n{zh_summary}\n\n[Link]({zh_url})\n")
    except Exception as e:
        print(f"Error saving file: {e}")

    return result


# ========== Batch Processing Endpoints (New) ==========

@app.post("/api/batch/create", response_model=BatchTaskResponse)
async def create_batch(batch_data: BatchTaskCreate):
    """Create a new batch crawling task"""
    if not batch_data.terms:
        raise HTTPException(status_code=400, detail="Terms list cannot be empty")
    
    # Remove duplicates and empty strings
    unique_terms = list(dict.fromkeys([t.strip() for t in batch_data.terms if t.strip()]))
    
    if not unique_terms:
        raise HTTPException(status_code=400, detail="No valid terms provided")
    
    # Create task
    task_id = await create_batch_task(len(unique_terms), batch_data.crawl_interval, batch_data.max_depth)
    
    # Add terms to task
    await add_terms_to_task(task_id, unique_terms)
    
    return BatchTaskResponse(
        task_id=task_id,
        total_terms=len(unique_terms),
        message=f"Batch task created with {len(unique_terms)} terms (Depth: {batch_data.max_depth})"
    )


@app.post("/api/batch/upload", response_model=BatchTaskResponse)
async def upload_batch_file(file: UploadFile = File(...), crawl_interval: int = 3, max_depth: int = 1):
    """Upload a file (TXT or CSV) containing terms"""
    if not file.filename.endswith(('.txt', '.csv')):
        raise HTTPException(status_code=400, detail="Only .txt and .csv files are supported")
    
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        
        terms = []
        if file.filename.endswith('.txt'):
            # Parse TXT file (one term per line)
            terms = [line.strip() for line in text_content.split('\n') if line.strip()]
        else:
            # Parse CSV file
            csv_reader = csv.reader(io.StringIO(text_content))
            for row in csv_reader:
                if row and row[0].strip():
                    terms.append(row[0].strip())
        
        if not terms:
            raise HTTPException(status_code=400, detail="No valid terms found in file")
        
        # Remove duplicates
        unique_terms = list(dict.fromkeys(terms))
        
        # Create task
        task_id = await create_batch_task(len(unique_terms), crawl_interval, max_depth)
        await add_terms_to_task(task_id, unique_terms)
        
        return BatchTaskResponse(
            task_id=task_id,
            total_terms=len(unique_terms),
            message=f"File uploaded successfully with {len(unique_terms)} terms (Depth: {max_depth})"
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.post("/api/batch/{task_id}/start")
async def start_task(task_id: int):
    """Start a batch crawling task"""
    task = await get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task['status'] not in ['pending', 'failed', 'cancelled']:
        raise HTTPException(status_code=400, detail=f"Task is already {task['status']}")
    
    try:
        await start_batch_crawl(task_id, task['crawl_interval'])
        return {"message": "Task started successfully", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/batch/{task_id}/status", response_model=TaskStatus)
async def get_status(task_id: int):
    """Get the status of a batch task"""
    task = await get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update counters
    await update_task_counters(task_id)
    task = await get_task_status(task_id)
    
    progress = 0.0
    if task['total_terms'] > 0:
        progress = round((task['completed_terms'] + task['failed_terms']) / task['total_terms'] * 100, 2)
    
    return TaskStatus(
        task_id=task['id'],
        status=task['status'],
        total_terms=task['total_terms'],
        completed_terms=task['completed_terms'],
        failed_terms=task['failed_terms'],
        progress_percent=progress,
        max_depth=task.get('max_depth', 1),
        created_at=task['created_at'],
        updated_at=task['updated_at']
    )


@app.get("/api/batch/{task_id}/terms", response_model=List[TermDetail])
async def get_terms(task_id: int, status: str = None):
    """Get all terms for a task, optionally filtered by status"""
    terms = await get_task_terms(task_id, status)
    return terms


@app.get("/api/batch/tasks", response_model=List[TaskListItem])
async def get_tasks():
    """Get all batch tasks"""
    tasks = await get_all_tasks()
    return tasks


@app.post("/api/batch/{task_id}/cancel")
async def cancel_task(task_id: int):
    """Cancel a running batch task"""
    try:
        await cancel_batch_crawl(task_id)
        return {"message": "Task cancelled successfully", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/batch/{task_id}/retry-failed")
async def retry_failed(task_id: int):
    """Retry all failed terms in a task"""
    task = await get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        count = await retry_failed_terms(task_id, task['crawl_interval'])
        return {
            "message": f"Retrying {count} failed terms",
            "failed_count": count,
            "task_id": task_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/batch/{task_id}/export")
async def export_results(task_id: int, format: str = "json"):
    """Export task results as JSON or CSV"""
    terms = await get_task_terms(task_id, "completed")
    
    if not terms:
        raise HTTPException(status_code=404, detail="No completed terms found")
    
    if format == "json":
        # Create JSON file for download
        json_content = json.dumps(terms, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([json_content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=task_{task_id}_results.json"}
        )
    
    elif format == "csv":
        # Use UTF-8 BOM for proper Chinese display in Excel
        output = io.BytesIO()
        # Write UTF-8 BOM
        output.write(b'\xef\xbb\xbf')
        
        # Create CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        
        # Write header
        writer.writerow(['Term', 'English Summary', 'English URL', 'Chinese Summary', 'Chinese URL'])
        
        # Write data
        for term in terms:
            writer.writerow([
                term['term'],
                term['en_summary'] or '',
                term['en_url'] or '',
                term['zh_summary'] or '',
                term['zh_url'] or ''
            ])
        
        # Encode to UTF-8 and write to output
        output.write(csv_content.getvalue().encode('utf-8'))
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=task_{task_id}_results.csv"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")





@app.get("/api/batch/{task_id}/graph")
async def get_task_graph(task_id: int):
    """Get the knowledge graph (nodes and edges) for a task"""
    terms = await get_task_terms(task_id)
    
    nodes = []
    edges = []
    
    term_map = {t['term'].lower(): t['id'] for t in terms}
    
    for term in terms:
        nodes.append({
            "id": term['id'],
            "label": term['term'],
            "status": term['status'],
            "depth": term['depth_level'],
            "group": term['depth_level'] # Use depth for coloring
        })
        
        # Get associations
        assocs = await get_term_associations(term['id'])
        for assoc in assocs:
            target_lower = assoc['target_term'].lower()
            if target_lower in term_map:
                edges.append({
                    "from": term['id'],
                    "to": term_map[target_lower],
                    "type": assoc['association_type'],
                    "value": assoc['weight']
                })
            # Else: we could add external nodes if we want to visualize uncrawled associations
    
    return {
        "nodes": nodes,
        "edges": edges
    }


# ========== New Phase 3 Endpoints: Corpus Quality & Data Management ==========

class DuplicateCheckRequest(BaseModel):
    terms: List[str]

@app.post("/api/corpus/check-duplicates")
async def check_duplicates(request: DuplicateCheckRequest):
    """Check which terms already exist in the corpus"""
    if not request.terms:
        return {"existing": [], "new": [], "total_input": 0, "existing_count": 0, "new_count": 0}
    
    result = await check_existing_terms(request.terms)
    return result


@app.delete("/api/batch/{task_id}")
async def delete_batch_task(task_id: int):
    """Delete a batch task and all its data"""
    success = await delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": f"Task {task_id} deleted successfully", "task_id": task_id}


@app.post("/api/system/reset")
async def reset_all_data(confirm: bool = False):
    """Reset all data in the database. Requires confirm=true"""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Must set confirm=true to reset all data. This action cannot be undone!"
        )
    
    result = await reset_database()
    return {
        "message": "Database reset successfully",
        **result
    }


@app.get("/api/corpus/statistics")
async def get_statistics():
    """Get overall corpus statistics"""
    stats = await get_corpus_statistics()
    return stats


@app.get("/api/system/backup")
async def backup_database():
    """Download the database file as backup"""
    from fastapi.responses import FileResponse
    db_path = "corpus.db"
    
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")
    
    return FileResponse(
        path=db_path,
        filename="corpus_backup.db",
        media_type="application/octet-stream"
    )


# ========== Sprint 2: Data Quality Control ==========

class CleanDataRequest(BaseModel):
    task_id: int | None = None
    remove_failed: bool = True
    remove_missing_chinese: bool = False
    remove_short_summaries: bool = False
    min_summary_length: int = 50

@app.get("/api/quality/analyze")
async def analyze_quality(task_id: int = None, min_summary_length: int = 50):
    """Analyze data quality for a specific task or all tasks
    
    Returns detailed quality metrics including:
    - Total terms analyzed
    - Complete bilingual pairs
    - Missing Chinese translations
    - English/Chinese summaries that are too short
    - Quality score (0-100)
    - List of problematic terms
    """
    quality = await analyze_data_quality(task_id, min_summary_length)
    return quality


@app.post("/api/quality/clean")
async def clean_data(request: CleanDataRequest):
    """Clean data by removing low-quality entries
    
    Options:
    - remove_failed: Remove all failed terms
    - remove_missing_chinese: Remove terms without Chinese translation
    - remove_short_summaries: Remove terms with summaries shorter than min_summary_length
    """
    if not (request.remove_failed or request.remove_missing_chinese or request.remove_short_summaries):
        raise HTTPException(
            status_code=400,
            detail="At least one removal option must be enabled"
        )
    
    result = await clean_task_data(
        task_id=request.task_id,
        remove_failed=request.remove_failed,
        remove_missing_chinese=request.remove_missing_chinese,
        remove_short_summaries=request.remove_short_summaries,
        min_summary_length=request.min_summary_length
    )
    return {
        "message": f"Cleaned {result['total_removed']} entries",
        **result
    }


@app.get("/api/quality/issues")
async def get_quality_issues(task_id: int = None, issue_type: str = "all", limit: int = 100):
    """Get terms with specific quality issues
    
    issue_type options:
    - 'all': All problematic terms
    - 'missing_chinese': Terms without Chinese translation
    - 'short_en': English summary too short
    - 'short_zh': Chinese summary too short
    - 'failed': Failed terms
    """
    if issue_type not in ['all', 'missing_chinese', 'short_en', 'short_zh', 'failed']:
        raise HTTPException(
            status_code=400,
            detail="Invalid issue_type. Must be one of: all, missing_chinese, short_en, short_zh, failed"
        )
    
    terms = await get_terms_by_quality_issue(task_id, issue_type, limit)
    return {
        "issue_type": issue_type,
        "task_id": task_id,
        "count": len(terms),
        "terms": terms
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

