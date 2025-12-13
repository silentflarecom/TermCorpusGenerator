# Term Corpus Generator

A lightweight, full-stack web application designed to generate bilingual (English & Chinese) corpus data for economic and general terms. Built with **FastAPI** and **Vue 3**.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Vue](https://img.shields.io/badge/vue-3.x-green.svg)

## 🚀 Features

- **Instant Bilingual Search**: Input a term (e.g., "Inflation") and retrieve its summary in both English and Chinese simultaneously.
- **Wikipedia Integration**: Automatically fetches data from Wikipedia using the `wikipedia-api` library, leveraging language links for accurate cross-lingual mapping.
- **Dual-View Interface**: Clean, modern UI displaying English and Chinese definitions side-by-side.
- **Auto-Save to Markdown**: Every search result is automatically saved as a Markdown file in the backend's `output/` directory.
- **JSON Export**: One-click export of current search results to a JSON file from the frontend.

### ⚡ New Features (v2.0)

- **📚 Batch Import & Automation**: Crawl hundreds of terms automatically via text input or file upload (CSV/TXT).
- **🇨🇳 Smart Chinese Conversion**: Automatically converts Traditional Chinese (Wikipedia default) to Simplified Chinese using `zhconv`.
- **📊 Real-time Monitoring**: Dashboard to track crawling progress, success/failure rates, and current status.
- **💾 Database Persistence**: Uses SQLite to store crawl history, allowing you to resume tasks or export data anytime.
- **📥 Robust Export**: Download results as valid JSON files or UTF-8 encoded CSVs (Excel compatible).

### 🌐 New Features (v2.1 - Intelligent Association Crawling)

- **🕸️ Knowledge Graph Visualization**: Interactive D3.js force-directed graph showing term relationships.
- **🎯 Depth-Controlled Crawling**: Configure crawl depth (1-3 levels) to automatically discover related terms from "See Also" and internal links.
- **📊 Association Tracking**: Stores term relationships (links, categories) in database for graph generation.
- **�️ Multi-Format Export**: Export knowledge graphs as PNG (high-res), SVG (editable), or JSON (data).
- **🎯 Smart Label Display**: Only shows labels for root and first-layer nodes to reduce visual clutter.

## �🛠️ Tech Stack

### Backend
- **FastAPI**: High-performance web framework.
- **SQLite + aiosqlite**: Async database for managing batch tasks.
- **Wikipedia-API**: Official MediaWiki API wrapper.
- **zhconv**: Advanced Traditional-to-Simplified Chinese conversion.
- **Pydantic**: Data validation.

### Frontend
- **Vue 3 + Vite**: Lightning fast frontend.
- **TailwindCSS**: Utility-first styling.
- **D3.js**: Knowledge graph visualization.
- **Axios**: HTTP client.

## ⚖️ Compliance & Best Practices

This tool is designed to strictly adhere to [Wikipedia's User-Agent Policy](https://meta.wikimedia.org/wiki/User-Agent_policy) and API Usage Guidelines:
 
1.  **Official API**: Uses the standard MediaWiki API endpoints, not screen scraping.
2.  **User-Agent**: Sends a strict, transparent header (`WikipediaTermCorpusGenerator/1.0 (Student Project; contact@silentflare.com)`) to identify the traffic source.
3.  **Rate Limiting**: Enforces a configurable delay (default 3s) between requests used in batch mode to prevent server overload.
4.  **Sequential Processing**: Batch tasks are processed serially to maintain a low concurrency footprint.

## 🗺️ Advanced Automation Roadmap

### 🎯 Planned Features

#### **Phase 1: Batch Import & Automated Crawling** ✅ COMPLETED
- **Batch Input Methods**: 
  - Paste multiple terms (one per line) ✅
  - Upload CSV/TXT files ✅
- **Automation Controls**:
  - Concurrent crawling with rate limiting ✅
  - Real-time progress monitoring ✅
  - Automatic retry mechanism ✅
- **Results Management**:
  - Batch export to JSON/CSV (Simplified Chinese support) ✅
  - Database persistence ✅

#### **Phase 2: Intelligent Association Crawling** ✅ COMPLETED
- **Link Discovery Strategies**:
  - "See also" sections from Wikipedia pages ✅
  - High-frequency internal links (via Associations) ✅
  - Category tags exploration ✅
  - Cross-language related articles (via langlinks) ✅
- **Crawl Depth Control**:
  - Configurable depth levels (1-3 layers) ✅
  - Maximum terms per layer ✅
  - Blacklist filtering for irrelevant terms (Basic filtering implemented) ✅
- **Knowledge Graph Visualization**:
  - Force-directed graph of term relationships ✅
  - Topic clustering display (via Force Layout) ✅
  - **Multi-format export: PNG, SVG, JSON** ✅
  - Smart full-graph capture (ignores zoom state) ✅

#### **Phase 3: Scheduled & Incremental Updates**
- **Scheduling Options**:
  - Daily/Weekly/Monthly automatic updates
  - Priority-based update queue
  - Monitor Wikipedia revision history API for changes
- **Version Control**:
  - Historical version tracking
  - Diff comparison between versions
  - Change notifications (email/webhook)

#### **Phase 4: Multi-Source Data Aggregation**
- **Extended Data Sources**:
  - Wikidata (structured knowledge base)
  - Baidu Baike (Chinese encyclopedia)
  - Britannica Encyclopedia
  - Academic paper abstracts (Google Scholar/arXiv)
  - Real-time financial data for economic terms
- **Data Fusion**:
  - Intelligent deduplication and merging
  - Source attribution and credibility scoring
  - Cross-source validation

#### **Phase 5: AI-Enhanced Corpus Generation**
- **AI Augmentation**:
  - Automatic summary optimization
  - Term definition standardization
  - Named entity recognition and tagging
  - Semantic relationship generation between terms
  - Multi-language translation quality checking
- **Intelligent Recommendations**:
  - Suggest missing terms based on existing corpus
  - Identify coverage gaps in the knowledge base

#### **Phase 6: Distributed Crawling Architecture** (For Large-Scale)
- **Distributed Components**:
  - Task queue: RabbitMQ + Celery
  - Distributed storage: MongoDB/PostgreSQL
  - Cache layer: Redis
  - Load balancing across worker nodes
- **Monitoring Dashboard**:
  - Real-time crawl status monitoring
  - Resource usage metrics
  - Error log aggregation

### 🏗️ Technical Architecture (Phase 1 Preview)

**Backend Enhancements**:
```
backend/
├── main.py              # Existing FastAPI main file
├── worker.py            # New: Background task worker (Celery/RQ)
├── models.py            # New: Database models
├── scheduler.py         # New: Batch crawl scheduler
├── database.py          # New: Database connection
└── utils/
    ├── rate_limiter.py  # Rate limiting control
    └── retry.py         # Retry logic
```

**Frontend Enhancements**:
```
frontend/src/
├── App.vue                    # Existing main component
└── components/
    ├── BatchImport.vue        # Batch import interface
    ├── ProgressMonitor.vue    # Progress tracking
    └── ResultsTable.vue       # Results data table
```

**Database Schema** (SQLite for Phase 1):
```sql
-- Batch tasks tracking
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    status TEXT,
    created_at TIMESTAMP,
    total_terms INTEGER,
    completed INTEGER
);

-- Individual terms
CREATE TABLE terms (
    id INTEGER PRIMARY KEY,
    task_id INTEGER,
    term TEXT,
    status TEXT,
    en_summary TEXT,
    zh_summary TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 📈 Implementation Priority

1. **Immediate** (Phase 1): Batch crawling - 10x efficiency boost with minimal complexity
2. **Short-term** (Phases 2-3): Intelligent crawling and scheduling - transform into self-growing knowledge base
3. **Mid-term** (Phases 4-5): Multi-source and AI enhancement - professional-grade corpus quality
4. **Long-term** (Phase 6): Distributed architecture - only when corpus exceeds 10,000+ terms

---

*This roadmap reflects the evolution from a simple search tool to an enterprise-grade knowledge corpus management system.*
