import asyncio
import wikipediaapi
from typing import Dict, Callable
from database import (
    update_task_status, 
    update_term_status, 
    update_task_counters,
    get_pending_terms,
    get_task_status,
    get_task_terms,
    save_term_associations,
    add_terms_to_task
)

# Global dictionary to track running tasks
running_tasks: Dict[int, asyncio.Task] = {}

class BatchCrawler:
    def __init__(self, task_id: int, crawl_interval: int = 3, max_depth: int = 1):
        self.task_id = task_id
        self.crawl_interval = crawl_interval
        self.max_depth = max_depth
        self.should_stop = False
        
        # User-Agent is explicitly set to comply with Wikimedia User-Agent Policy
        USER_AGENT = 'WikipediaTermCorpusGenerator/1.0 (Student Project; contact@silentflare.com; https://github.com/silentflarecom/WikipediaPython)'
        
        # Initialize Wikipedia API instances
        self.wiki_en = wikipediaapi.Wikipedia(
            user_agent=USER_AGENT,
            language='en'
        )
        self.wiki_zh = wikipediaapi.Wikipedia(
            user_agent=USER_AGENT,
            language='zh'  # Chinese Wikipedia (content is usually in Simplified Chinese)
        )
    
    async def crawl_single_term(self, term_record: Dict) -> Dict:
        """Crawl a single term from Wikipedia"""
        term = term_record['term']
        term_id = term_record['id']
        try:
            # Mark as crawling
            await update_term_status(self.task_id, term, "crawling")
            
            # Get English page (synchronous call, but shouldn't block too long)
            await asyncio.sleep(0)  # Yield control
            page_en = self.wiki_en.page(term)
            
            if not page_en.exists():
                raise Exception(f"Term '{term}' not found in English Wikipedia")
            
            # Get English data
            en_summary = page_en.summary[0:1000] + "..." if len(page_en.summary) > 1000 else page_en.summary
            en_url = page_en.fullurl
            
            # Get Chinese data via langlinks
            zh_summary = "Translation not found."
            zh_url = ""
            
            langlinks = page_en.langlinks
            langlinks = page_en.langlinks
            if 'zh' in langlinks:
                zh_title = langlinks['zh'].title
                page_zh = self.wiki_zh.page(zh_title)
                
                if page_zh.exists():
                    raw_zh_summary = page_zh.summary[0:1000] + "..." if len(page_zh.summary) > 1000 else page_zh.summary
                    # Convert to Simplified Chinese
                    try:
                        import zhconv
                        zh_summary = zhconv.convert(raw_zh_summary, 'zh-cn')
                    except ImportError:
                        zh_summary = raw_zh_summary
                    zh_url = page_zh.fullurl
            
            # Extract Associations
            associations = []
            
            # 1. See Also Section
            see_also_section = page_en.section_by_title("See also")
            if see_also_section:
                # Naive link extraction from text might be hard with just section text
                # wikipedia-api doesn't expose links per section easily without parsing
                # But we can check if any of page.links contain the text in section?
                # Actually, filtering page.links is easier.
                pass
            
            # Use all links for now, filtered by some heuristics?
            # Or just take categories
            
            # Categories
            for cat_title in page_en.categories:
                if not cat_title.startswith("Category:All articles") and \
                   not cat_title.startswith("Category:Articles") and \
                   not cat_title.startswith("Category:Webarchive") and \
                   not cat_title.startswith("Category:CS1"):
                    clean_cat = cat_title.replace("Category:", "")
                    associations.append({
                        "target_term": clean_cat,
                        "association_type": "category",
                        "weight": 0.5
                    })

            # Links (Limit to top 20 to avoid spam)
            link_count = 0
            for title in page_en.links:
                if link_count >= 20: break
                # Skip namespaces
                if ":" not in title: 
                    associations.append({
                        "target_term": title,
                        "association_type": "link",
                        "weight": 1.0
                    })
                    link_count += 1

            if associations:
                await save_term_associations(term_id, associations)
                
            result = {
                "term": term,
                "en_summary": en_summary,
                "en_url": en_url,
                "zh_summary": zh_summary,
                "zh_url": zh_url,
                "associations": associations
            }
            
            # Save to Markdown
            await self.save_to_markdown(result)
            
            # Update database with success
            await update_term_status(
                self.task_id, term, "completed",
                en_summary, en_url, zh_summary, zh_url
            )
            
            return result
            
        except Exception as e:
            # Update database with failure
            error_msg = str(e)
            await update_term_status(
                self.task_id, term, "failed",
                error_message=error_msg
            )
            raise e
    
    async def save_to_markdown(self, result: Dict):
        """Save result to Markdown file"""
        import os
        
        OUTPUT_DIR = "output"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        filename = f"{result['term'].replace(' ', '_')}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {result['term']}\n\n")
                f.write(f"## English\n{result['en_summary']}\n\n[Link]({result['en_url']})\n\n")
                f.write(f"## Chinese\n{result['zh_summary']}\n\n")
                if result['zh_url']:
                    f.write(f"[Link]({result['zh_url']})\n")
        except Exception as e:
            print(f"Error saving Markdown file: {e}")
    
    async def run(self):
        """Run the batch crawling process"""
        try:
            # Update task status to running
            await update_task_status(self.task_id, "running")
            
            # Load task config if not set
            task_info = await get_task_status(self.task_id)
            if task_info and 'max_depth' in task_info:
                self.max_depth = task_info['max_depth'] or 1
            
            while not self.should_stop:
                # Get all pending terms
                # We fetch inside the loop to catch new terms added during crawling (depth > 1)
                pending_terms = await get_pending_terms(self.task_id)
                
                if not pending_terms:
                    break
                
                # Check cancellation again
                if (await get_task_status(self.task_id))['status'] == 'cancelled':
                     self.should_stop = True
                     break

                processed_in_this_batch = 0
                
                for term_record in pending_terms:
                    if self.should_stop:
                        await update_task_status(self.task_id, "cancelled")
                        break
                    
                    term = term_record['term']
                    current_depth = term_record.get('depth_level', 0)
                    
                    try:
                        result = await self.crawl_single_term(term_record)
                        print(f"✓ Successfully crawled: {term} (Depth: {current_depth})")
                        
                        # Handle Depth Crawling
                        # Only add new terms if we haven't reached max depth yet
                        # max_depth=1 means only root terms (no associations)
                        # max_depth=2 means root + 1 layer of associations
                        # max_depth=3 means root + 2 layers of associations
                        next_depth = current_depth + 1
                        if next_depth < self.max_depth and result.get('associations'):
                            new_terms = []
                            # Filter associations
                            existing_terms_in_task = await get_task_terms(self.task_id)
                            existing_set = {t['term'].lower() for t in existing_terms_in_task}
                            
                            for assoc in result['associations']:
                                target = assoc['target_term']
                                if target.lower() not in existing_set and assoc['association_type'] == 'link':
                                    new_terms.append(target)
                                    existing_set.add(target.lower())
                            
                            # Limit new terms per source
                            new_terms = new_terms[:10]
                            
                            if new_terms:
                                print(f"  -> Discovered {len(new_terms)} new terms from {term} (will be depth {next_depth})")
                                await add_terms_to_task(self.task_id, new_terms, next_depth, term_record['id'])
                        
                    except Exception as e:
                        print(f"✗ Failed to crawl {term}: {str(e)}")
                    
                    # Update task counters
                    await update_task_counters(self.task_id)
                    
                    processed_in_this_batch += 1
                    
                    # Wait for the specified interval before next request
                    await asyncio.sleep(self.crawl_interval)
                
                # If we processed terms, check again. If pending_terms was empty, we broke out earlier.
                # Use a small sleep to avoid tight loop if something is weird
                if processed_in_this_batch == 0:
                   break
            
            # Mark task as completed if not cancelled and no more pending terms
            if not self.should_stop and not await get_pending_terms(self.task_id):
                await update_task_status(self.task_id, "completed")
                print(f"✓ Task {self.task_id} completed successfully")
        
        except Exception as e:
            print(f"✗ Error in batch crawler: {str(e)}")
            await update_task_status(self.task_id, "failed")
        
        finally:
            # Remove from running tasks
            if self.task_id in running_tasks:
                del running_tasks[self.task_id]
    
    def stop(self):
        """Signal the crawler to stop"""
        self.should_stop = True


async def start_batch_crawl(task_id: int, crawl_interval: int = 3):
    """Start a batch crawl task in the background"""
    if task_id in running_tasks:
        raise Exception(f"Task {task_id} is already running")
    
    # We pass raw params here. run() fetches max_depth from DB
    crawler = BatchCrawler(task_id, crawl_interval)
    task = asyncio.create_task(crawler.run())
    running_tasks[task_id] = task
    
    return crawler


async def cancel_batch_crawl(task_id: int):
    """Cancel a running batch crawl task"""
    if task_id not in running_tasks:
        raise Exception(f"Task {task_id} is not running")
    
    task = running_tasks[task_id]
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    await update_task_status(task_id, "cancelled")


async def retry_failed_terms(task_id: int, crawl_interval: int = 3):
    """Retry all failed terms in a task"""
    # Reset failed terms to pending
    from database import get_failed_terms
    import aiosqlite
    
    failed_terms = await get_failed_terms(task_id)
    
    if not failed_terms:
        return 0
    
    async with aiosqlite.connect("corpus.db") as db:
        for term_record in failed_terms:
            await db.execute("""
                UPDATE terms
                SET status = 'pending', error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (term_record['id'],))
        await db.commit()
    
    # Start crawling again
    await start_batch_crawl(task_id, crawl_interval)
    
    return len(failed_terms)
