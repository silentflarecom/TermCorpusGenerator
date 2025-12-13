import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import wikipediaapi

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Wikipedia API
# User-Agent is required by Wikipedia API
wiki_en = wikipediaapi.Wikipedia(
    user_agent='TermCorpusGenerator/1.0 (contact@example.com)',
    language='en'
)

# Output directory
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class TermResponse(BaseModel):
    term: str
    en_summary: str
    en_url: str
    zh_summary: str
    zh_url: str

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
