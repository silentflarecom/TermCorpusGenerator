# Setup Instructions

## First-Time Setup

### 1. Install Dependencies

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Configure User-Agent

⚠️ **CRITICAL**: The application comes with a placeholder User-Agent. **You MUST configure your own User-Agent before starting any crawl tasks.**

Wikipedia's [User-Agent Policy](https://meta.wikimedia.org/wiki/User-Agent_policy) strictly requires all API clients to identify themselves.

**Steps to Configure:**

1. Start the application (see section 3 below).
2. Go to the **Manage** page in the web interface.
3. Locate the **User Agent Configuration** panel (look for the yellow warning box).
4. Enter a User-Agent string that identifies YOUR project.
   
   **Format:** `ProjectName/Version (Contact Information)`

   **Valid Examples:**
   - `MyResearchBot/1.0 (mailto:me@university.edu)`
   - `CorpusBuilder/2.0 (https://github.com/myusername/myproject)`
   - `WikiDataTool/1.0 (mailto:dev@company.com)`

5. Click **💾 Save Settings**.

> **Note:** The default User-Agent `TermCorpusBot/1.0 (...)` is a placeholder. Using it for heavy crawling may result in IP blocking by Wikipedia.

**Privacy Note:** Your User-Agent is only sent to Wikipedia servers with your API requests. It is stored locally in your `corpus.db` and is never sent to any other third party.

### 3. Running the Application

**Start Backend:**
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Start Frontend:**
```bash
cd frontend
npm run dev
```

**Access the application:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
WikipediaPython/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── database.py       # Database operations
│   ├── scheduler.py      # Batch crawling logic
│   ├── models.py         # Pydantic models
│   └── requirements.txt  # Python dependencies
├── frontend/
│   └── src/
│       ├── App.vue
│       └── components/
│           ├── BatchImport.vue
│           ├── TaskManager.vue
│           ├── ResultsTable.vue
│           └── ...
└── README.md
```

## Privacy & Data

- The database file (`corpus.db`) is gitignored by default
- No personal data is collected or transmitted
- All Wikipedia API requests use your configured User-Agent
- You can export and backup your data anytime via the Manage page

## Support

For issues or questions:
1. Check the [main README](README.md) for feature documentation
2. Review [Wikipedia's API documentation](https://www.mediawiki.org/wiki/API:Main_page)
3. Open an issue on GitHub

---

## Troubleshooting
 
 **1. `CORS` errors in browser console:**
 - Ensure the backend is running (`python -m uvicorn ...`).
 - Refresh the page. The backend might have been restarting.
 
 **2. Database locked errors:**
 - SQLite allows only one writer at a time. This usually resolves automatically.
 - If persistent, check if you have the database file open in another program (like a DB viewer).
 
 **3. "Term not found" errors:**
 - Check if the term exists on the selected language Wikipedia.
 - Verify your internet connection.
 - If crawling many terms, check if you've been rate-limited (slow down requests by increasing delay).
 - Verify your User-Agent is set correctly.
 
 ---
 
 **Note**: This is an educational project. Please use it responsibly and in compliance with Wikipedia's policies.
