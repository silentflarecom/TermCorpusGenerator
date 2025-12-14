import aiosqlite
import os
from datetime import datetime

DATABASE_FILE = "corpus.db"

async def init_database():
    """Initialize the database with required tables"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        # Create batch_tasks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS batch_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_terms INTEGER NOT NULL,
                completed_terms INTEGER DEFAULT 0,
                failed_terms INTEGER DEFAULT 0,
                crawl_interval INTEGER DEFAULT 3
            )
        """)
        
        # Create terms table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                term TEXT NOT NULL,
                status TEXT NOT NULL,
                en_summary TEXT,
                en_url TEXT,
                zh_summary TEXT,
                zh_url TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES batch_tasks(id)
            )
        """)
        
        # Create term_associations table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS term_associations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term_id INTEGER,
                target_term TEXT,
                association_type TEXT,
                weight REAL DEFAULT 1.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_term_id) REFERENCES terms(id)
            )
        """)

        # Add columns to existing tables if they don't exist
        # We use a helper to add columns safely
        await add_column_if_not_exists(db, "batch_tasks", "max_depth", "INTEGER DEFAULT 1")
        await add_column_if_not_exists(db, "terms", "depth_level", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(db, "terms", "source_term_id", "INTEGER")
        
        # Create indexes
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_id ON terms(task_id)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON terms(status)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_term ON term_associations(source_term_id)
        """)
        
        await db.commit()

async def add_column_if_not_exists(db, table, column, definition):
    """Helper to add a column if it doesn't already exist"""
    try:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Added column {column} to {table}")
    except Exception as e:
        # Ignore error if column already exists
        pass

async def create_batch_task(total_terms: int, crawl_interval: int = 3, max_depth: int = 1) -> int:
    """Create a new batch task and return its ID"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute("""
            INSERT INTO batch_tasks (status, total_terms, crawl_interval, max_depth)
            VALUES (?, ?, ?, ?)
        """, ("pending", total_terms, crawl_interval, max_depth))
        await db.commit()
        return cursor.lastrowid

async def add_terms_to_task(task_id: int, terms: list, depth_level: int = 0, source_term_id: int = None):
    """Add terms to a batch task"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.executemany("""
            INSERT INTO terms (task_id, term, status, depth_level, source_term_id)
            VALUES (?, ?, ?, ?, ?)
        """, [(task_id, term, "pending", depth_level, source_term_id) for term in terms])
        # Update total terms count in batch_tasks
        if depth_level > 0:
            await db.execute("""
                UPDATE batch_tasks 
                SET total_terms = total_terms + ? 
                WHERE id = ?
            """, (len(terms), task_id))
        await db.commit()

async def update_task_status(task_id: int, status: str):
    """Update the status of a batch task"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            UPDATE batch_tasks
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, task_id))
        await db.commit()

async def update_term_status(task_id: int, term: str, status: str, 
                            en_summary: str = None, en_url: str = None,
                            zh_summary: str = None, zh_url: str = None,
                            error_message: str = None):
    """Update the status and data of a term"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            UPDATE terms
            SET status = ?, en_summary = ?, en_url = ?, zh_summary = ?, zh_url = ?,
                error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ? AND term = ?
        """, (status, en_summary, en_url, zh_summary, zh_url, error_message, task_id, term))
        await db.commit()

async def update_task_counters(task_id: int):
    """Update completed and failed counters for a task"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM terms
            WHERE task_id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
        if row:
            await db.execute("""
                UPDATE batch_tasks
                SET completed_terms = ?, failed_terms = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (row[0], row[1], task_id))
            await db.commit()

async def get_task_status(task_id: int) -> dict:
    """Get the status of a batch task"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM batch_tasks WHERE id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
        if row:
            return dict(row)
        return None

async def get_task_terms(task_id: int, status_filter: str = None) -> list:
    """Get all terms for a task, optionally filtered by status"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        if status_filter:
            cursor = await db.execute("""
                SELECT * FROM terms WHERE task_id = ? AND status = ?
                ORDER BY id
            """, (task_id, status_filter))
        else:
            cursor = await db.execute("""
                SELECT * FROM terms WHERE task_id = ?
                ORDER BY id
            """, (task_id,))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_all_tasks() -> list:
    """Get all batch tasks"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM batch_tasks
            ORDER BY created_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_pending_terms(task_id: int) -> list:
    """Get all pending terms for a task"""
    return await get_task_terms(task_id, "pending")

async def get_failed_terms(task_id: int) -> list:
    """Get all failed terms for a task"""
    return await get_task_terms(task_id, "failed")

async def save_term_associations(source_term_id: int, associations: list):
    """Save associations for a term
    associations: list of dicts with keys 'target_term', 'association_type', 'weight'
    """
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.executemany("""
            INSERT INTO term_associations (source_term_id, target_term, association_type, weight)
            VALUES (?, ?, ?, ?)
        """, [(source_term_id, a['target_term'], a['association_type'], a.get('weight', 1.0)) for a in associations])
        await db.commit()

async def get_term_associations(term_id: int) -> list:
    """Get all associations for a term"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM term_associations WHERE source_term_id = ?
        """, (term_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def check_existing_terms(terms: list) -> dict:
    """Check which terms already exist in the database (across all tasks)
    Returns dict with 'existing' and 'new' term lists
    """
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        # Normalize terms for comparison (case-insensitive)
        terms_lower = [t.lower().strip() for t in terms]
        placeholders = ",".join(["?" for _ in terms_lower])
        
        cursor = await db.execute(f"""
            SELECT DISTINCT term FROM terms 
            WHERE LOWER(term) IN ({placeholders})
            AND status = 'completed'
        """, terms_lower)
        
        rows = await cursor.fetchall()
        existing_terms = [row['term'] for row in rows]
        existing_lower = [t.lower() for t in existing_terms]
        
        new_terms = [t for t in terms if t.lower().strip() not in existing_lower]
        
        return {
            "existing": existing_terms,
            "new": new_terms,
            "total_input": len(terms),
            "existing_count": len(existing_terms),
            "new_count": len(new_terms)
        }

async def delete_task(task_id: int) -> bool:
    """Delete a task and all its associated data"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        # First check if task exists
        cursor = await db.execute("SELECT id FROM batch_tasks WHERE id = ?", (task_id,))
        if not await cursor.fetchone():
            return False
        
        # Get all term IDs for this task
        cursor = await db.execute("SELECT id FROM terms WHERE task_id = ?", (task_id,))
        term_ids = [row[0] for row in await cursor.fetchall()]
        
        # Delete associations for these terms
        if term_ids:
            placeholders = ",".join(["?" for _ in term_ids])
            await db.execute(f"""
                DELETE FROM term_associations WHERE source_term_id IN ({placeholders})
            """, term_ids)
        
        # Delete terms
        await db.execute("DELETE FROM terms WHERE task_id = ?", (task_id,))
        
        # Delete task
        await db.execute("DELETE FROM batch_tasks WHERE id = ?", (task_id,))
        
        await db.commit()
        return True

async def reset_database() -> dict:
    """Reset database - delete all data but keep structure"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        # Get counts before deletion
        cursor = await db.execute("SELECT COUNT(*) FROM batch_tasks")
        task_count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM terms")
        term_count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM term_associations")
        assoc_count = (await cursor.fetchone())[0]
        
        # Delete all data
        await db.execute("DELETE FROM term_associations")
        await db.execute("DELETE FROM terms")
        await db.execute("DELETE FROM batch_tasks")
        
        # Reset auto-increment counters
        await db.execute("DELETE FROM sqlite_sequence WHERE name IN ('batch_tasks', 'terms', 'term_associations')")
        
        await db.commit()
        
        return {
            "deleted_tasks": task_count,
            "deleted_terms": term_count,
            "deleted_associations": assoc_count
        }

async def get_corpus_statistics() -> dict:
    """Get overall corpus statistics"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        stats = {}
        
        # Total tasks
        cursor = await db.execute("SELECT COUNT(*) FROM batch_tasks")
        stats['total_tasks'] = (await cursor.fetchone())[0]
        
        # Total terms and completed terms
        cursor = await db.execute("SELECT COUNT(*) FROM terms")
        stats['total_terms'] = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM terms WHERE status = 'completed'")
        stats['completed_terms'] = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM terms WHERE status = 'failed'")
        stats['failed_terms'] = (await cursor.fetchone())[0]
        
        # Bilingual pairs (have both en and zh)
        cursor = await db.execute("""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' AND en_summary IS NOT NULL AND zh_summary IS NOT NULL
            AND en_summary != '' AND zh_summary != ''
        """)
        stats['bilingual_pairs'] = (await cursor.fetchone())[0]
        
        # Total associations
        cursor = await db.execute("SELECT COUNT(*) FROM term_associations")
        stats['total_associations'] = (await cursor.fetchone())[0]
        
        # Database file size
        if os.path.exists(DATABASE_FILE):
            stats['db_size_bytes'] = os.path.getsize(DATABASE_FILE)
            stats['db_size_mb'] = round(stats['db_size_bytes'] / (1024 * 1024), 2)
        else:
            stats['db_size_bytes'] = 0
            stats['db_size_mb'] = 0
        
        return stats


async def analyze_data_quality(task_id: int = None, min_summary_length: int = 50) -> dict:
    """Analyze data quality for a specific task or all tasks
    
    Returns detailed quality metrics including:
    - Total terms analyzed
    - Complete bilingual pairs
    - Missing Chinese translations
    - Missing English content
    - Summary too short (below min_summary_length)
    - Failed terms
    - Terms with associations
    """
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        # Build WHERE clause based on task_id
        where_clause = f"WHERE task_id = {task_id}" if task_id else ""
        task_filter = f"AND task_id = {task_id}" if task_id else ""
        
        quality = {
            "task_id": task_id,
            "analyzed_at": datetime.now().isoformat(),
            "min_summary_length": min_summary_length
        }
        
        # Total terms
        cursor = await db.execute(f"SELECT COUNT(*) FROM terms {where_clause}")
        quality['total_terms'] = (await cursor.fetchone())[0]
        
        # Completed terms
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' {task_filter.replace('AND', 'AND' if task_id else '')}
        """.replace('AND  AND', 'AND'))
        quality['completed_terms'] = (await cursor.fetchone())[0]
        
        # Failed terms
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'failed' {task_filter.replace('AND', 'AND' if task_id else '')}
        """.replace('AND  AND', 'AND'))
        quality['failed_terms'] = (await cursor.fetchone())[0]
        
        # Pending terms
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'pending' {task_filter.replace('AND', 'AND' if task_id else '')}
        """.replace('AND  AND', 'AND'))
        quality['pending_terms'] = (await cursor.fetchone())[0]
        
        # Complete bilingual pairs (both EN and ZH present and non-empty)
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' 
            AND en_summary IS NOT NULL AND en_summary != ''
            AND zh_summary IS NOT NULL AND zh_summary != ''
            {task_filter}
        """)
        quality['complete_bilingual'] = (await cursor.fetchone())[0]
        
        # Missing Chinese translation
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' 
            AND en_summary IS NOT NULL AND en_summary != ''
            AND (zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.')
            {task_filter}
        """)
        quality['missing_chinese'] = (await cursor.fetchone())[0]
        
        # Missing English (should be rare, but check anyway)
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' 
            AND (en_summary IS NULL OR en_summary = '')
            {task_filter}
        """)
        quality['missing_english'] = (await cursor.fetchone())[0]
        
        # English summary too short
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' 
            AND en_summary IS NOT NULL 
            AND LENGTH(en_summary) < ?
            {task_filter}
        """, (min_summary_length,))
        quality['en_summary_too_short'] = (await cursor.fetchone())[0]
        
        # Chinese summary too short
        cursor = await db.execute(f"""
            SELECT COUNT(*) FROM terms 
            WHERE status = 'completed' 
            AND zh_summary IS NOT NULL AND zh_summary != '' 
            AND zh_summary != 'Translation not found.'
            AND LENGTH(zh_summary) < ?
            {task_filter}
        """, (min_summary_length,))
        quality['zh_summary_too_short'] = (await cursor.fetchone())[0]
        
        # Get list of problematic terms for detailed view
        cursor = await db.execute(f"""
            SELECT id, term, 
                CASE 
                    WHEN zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.' THEN 'missing_chinese'
                    WHEN LENGTH(en_summary) < ? THEN 'en_too_short'
                    WHEN LENGTH(zh_summary) < ? THEN 'zh_too_short'
                    ELSE 'unknown'
                END as issue_type
            FROM terms 
            WHERE status = 'completed' 
            AND (
                zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.'
                OR LENGTH(en_summary) < ?
                OR (zh_summary IS NOT NULL AND zh_summary != '' AND zh_summary != 'Translation not found.' AND LENGTH(zh_summary) < ?)
            )
            {task_filter}
            LIMIT 50
        """, (min_summary_length, min_summary_length, min_summary_length, min_summary_length))
        
        rows = await cursor.fetchall()
        quality['problematic_terms'] = [
            {"id": row['id'], "term": row['term'], "issue": row['issue_type']}
            for row in rows
        ]
        
        # Calculate quality score (0-100)
        if quality['completed_terms'] > 0:
            issues = quality['missing_chinese'] + quality['en_summary_too_short'] + quality['zh_summary_too_short']
            quality['quality_score'] = round(
                (quality['completed_terms'] - issues) / quality['completed_terms'] * 100, 1
            )
        else:
            quality['quality_score'] = 0
        
        return quality


async def clean_task_data(
    task_id: int = None,
    remove_failed: bool = True,
    remove_missing_chinese: bool = False,
    remove_short_summaries: bool = False,
    min_summary_length: int = 50
) -> dict:
    """Clean data by removing low-quality entries
    
    Returns count of removed items
    """
    async with aiosqlite.connect(DATABASE_FILE) as db:
        removed = {
            "failed_removed": 0,
            "missing_chinese_removed": 0,
            "short_summaries_removed": 0,
            "total_removed": 0,
            "associations_removed": 0
        }
        
        task_filter = f"AND task_id = {task_id}" if task_id else ""
        
        # Collect term IDs to delete
        term_ids_to_delete = []
        
        if remove_failed:
            cursor = await db.execute(f"""
                SELECT id FROM terms WHERE status = 'failed' {task_filter}
            """)
            failed_ids = [row[0] for row in await cursor.fetchall()]
            term_ids_to_delete.extend(failed_ids)
            removed['failed_removed'] = len(failed_ids)
        
        if remove_missing_chinese:
            cursor = await db.execute(f"""
                SELECT id FROM terms 
                WHERE status = 'completed' 
                AND (zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.')
                {task_filter}
            """)
            missing_ids = [row[0] for row in await cursor.fetchall()]
            # Don't double-count
            new_ids = [id for id in missing_ids if id not in term_ids_to_delete]
            term_ids_to_delete.extend(new_ids)
            removed['missing_chinese_removed'] = len(new_ids)
        
        if remove_short_summaries:
            cursor = await db.execute(f"""
                SELECT id FROM terms 
                WHERE status = 'completed' 
                AND (LENGTH(en_summary) < ? OR 
                     (zh_summary IS NOT NULL AND zh_summary != '' AND zh_summary != 'Translation not found.' AND LENGTH(zh_summary) < ?))
                {task_filter}
            """, (min_summary_length, min_summary_length))
            short_ids = [row[0] for row in await cursor.fetchall()]
            new_ids = [id for id in short_ids if id not in term_ids_to_delete]
            term_ids_to_delete.extend(new_ids)
            removed['short_summaries_removed'] = len(new_ids)
        
        # Delete associations for these terms
        if term_ids_to_delete:
            placeholders = ",".join(["?" for _ in term_ids_to_delete])
            
            # Count associations before deletion
            cursor = await db.execute(f"""
                SELECT COUNT(*) FROM term_associations 
                WHERE source_term_id IN ({placeholders})
            """, term_ids_to_delete)
            removed['associations_removed'] = (await cursor.fetchone())[0]
            
            # Delete associations
            await db.execute(f"""
                DELETE FROM term_associations WHERE source_term_id IN ({placeholders})
            """, term_ids_to_delete)
            
            # Delete terms
            await db.execute(f"""
                DELETE FROM terms WHERE id IN ({placeholders})
            """, term_ids_to_delete)
            
            await db.commit()
        
        removed['total_removed'] = len(term_ids_to_delete)
        
        # Update task counters if task_id specified
        if task_id:
            await update_task_counters(task_id)
        
        return removed


async def get_terms_by_quality_issue(task_id: int = None, issue_type: str = "all", limit: int = 100) -> list:
    """Get terms with specific quality issues
    
    issue_type can be: 'all', 'missing_chinese', 'short_en', 'short_zh', 'failed'
    """
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        task_filter = f"AND task_id = {task_id}" if task_id else ""
        
        if issue_type == "missing_chinese":
            query = f"""
                SELECT * FROM terms 
                WHERE status = 'completed' 
                AND (zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.')
                {task_filter}
                LIMIT ?
            """
        elif issue_type == "short_en":
            query = f"""
                SELECT * FROM terms 
                WHERE status = 'completed' 
                AND LENGTH(en_summary) < 50
                {task_filter}
                LIMIT ?
            """
        elif issue_type == "short_zh":
            query = f"""
                SELECT * FROM terms 
                WHERE status = 'completed' 
                AND zh_summary IS NOT NULL AND zh_summary != '' 
                AND zh_summary != 'Translation not found.'
                AND LENGTH(zh_summary) < 50
                {task_filter}
                LIMIT ?
            """
        elif issue_type == "failed":
            query = f"""
                SELECT * FROM terms 
                WHERE status = 'failed'
                {task_filter}
                LIMIT ?
            """
        else:  # 'all' - return all problematic terms
            query = f"""
                SELECT * FROM terms 
                WHERE (
                    status = 'failed'
                    OR (status = 'completed' AND (zh_summary IS NULL OR zh_summary = '' OR zh_summary = 'Translation not found.'))
                    OR (status = 'completed' AND LENGTH(en_summary) < 50)
                )
                {task_filter}
                LIMIT ?
            """
        
        cursor = await db.execute(query, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


