import asyncio
import json
import wikipediaapi
from typing import Dict, Callable, List
from database import (
    update_task_status, 
    update_term_status, 
    update_task_counters,
    get_pending_terms,
    get_task_status,
    get_task_terms,
    save_term_associations,
    add_terms_to_task,
    get_system_setting
)

# Global dictionary to track running tasks
running_tasks: Dict[int, asyncio.Task] = {}

# Common Wikipedia languages with their native names
# Order: English first, then Traditional Chinese, Simplified Chinese, then alphabetically by code
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'zh-tw': '繁體中文 (Traditional Chinese)',
    'zh': '简体中文 (Simplified Chinese)',
    'ja': '日本語 (Japanese)',
    'ko': '한국어 (Korean)',
    'es': 'Español (Spanish)',
    'fr': 'Français (French)',
    'de': 'Deutsch (German)',
    'ru': 'Русский (Russian)',
    'pt': 'Português (Portuguese)',
    'it': 'Italiano (Italian)',
    'ar': 'العربية (Arabic)',
    'hi': 'हिन्दी (Hindi)',
    'vi': 'Tiếng Việt (Vietnamese)',
    'th': 'ไทย (Thai)',
    'id': 'Bahasa Indonesia',
    'tr': 'Türkçe (Turkish)',
    'pl': 'Polski (Polish)',
    'nl': 'Nederlands (Dutch)',
    'sv': 'Svenska (Swedish)',
    'uk': 'Українська (Ukrainian)',
}

class BatchCrawler:
    def __init__(self, task_id: int, crawl_interval: int = 3, max_depth: int = 1, target_languages: List[str] = None, user_agent: str = None):
        self.task_id = task_id
        self.crawl_interval = crawl_interval
        self.max_depth = max_depth
        self.target_languages = target_languages or ['en', 'zh']
        self.should_stop = False
        
        # User-Agent is explicitly set to comply with Wikimedia User-Agent Policy
        # Use provided user_agent or fallback to default
        default_ua = 'WikipediaTermCorpusGenerator/2.0 (Student Project; contact@silentflare.com; https://github.com/silentflarecom/WikipediaPython)'
        self.USER_AGENT = user_agent or default_ua
        
        # Initialize Wikipedia API instances dynamically for each language
        self.wiki_instances = {}
        for lang in self.target_languages:
            self.wiki_instances[lang] = wikipediaapi.Wikipedia(
                user_agent=self.USER_AGENT,
                language=lang
            )
    
    def get_wiki_instance(self, lang: str):
        """Get or create a Wikipedia instance for a language"""
        if lang not in self.wiki_instances:
            self.wiki_instances[lang] = wikipediaapi.Wikipedia(
                user_agent=self.USER_AGENT,
                language=lang
            )
        return self.wiki_instances[lang]
    
    async def crawl_single_term(self, term_record: Dict) -> Dict:
        """Crawl a single term from Wikipedia in multiple languages"""
        term = term_record['term']
        term_id = term_record['id']
        try:
            # Mark as crawling
            await update_term_status(self.task_id, term, "crawling")
            
            # Always start with English to get the base page
            await asyncio.sleep(0)  # Yield control
            wiki_en = self.get_wiki_instance('en')
            page_en = wiki_en.page(term)
            
            if not page_en.exists():
                raise Exception(f"Term '{term}' not found in English Wikipedia")
            
            # Get English data first (always needed for associations and as base)
            en_summary = page_en.summary[0:1000] + "..." if len(page_en.summary) > 1000 else page_en.summary
            en_url = page_en.fullurl
            
            # Get langlinks for other languages
            langlinks = page_en.langlinks
            
            # Build translations dictionary for all target languages
            translations = {}
            for lang in self.target_languages:
                if lang == 'en':
                    translations['en'] = {
                        'summary': en_summary,
                        'url': en_url
                    }
                elif lang in ['zh', 'zh-tw']:
                    # Both simplified and traditional Chinese use 'zh' langlink
                    # We then convert based on the target variant
                    if 'zh' in langlinks:
                        zh_title = langlinks['zh'].title
                        wiki_zh = self.get_wiki_instance('zh')
                        page_zh = wiki_zh.page(zh_title)
                        
                        if page_zh.exists():
                            raw_summary = page_zh.summary[0:1000] + "..." if len(page_zh.summary) > 1000 else page_zh.summary
                            
                            # Convert based on target variant
                            try:
                                import zhconv
                                if lang == 'zh':
                                    # Simplified Chinese
                                    raw_summary = zhconv.convert(raw_summary, 'zh-cn')
                                else:
                                    # Traditional Chinese (zh-tw)
                                    raw_summary = zhconv.convert(raw_summary, 'zh-tw')
                            except ImportError:
                                pass
                            
                            translations[lang] = {
                                'summary': raw_summary,
                                'url': page_zh.fullurl
                            }
                        else:
                            translations[lang] = {
                                'summary': 'Translation not found.',
                                'url': ''
                            }
                    else:
                        translations[lang] = {
                            'summary': 'Translation not found.',
                            'url': ''
                        }
                elif lang in langlinks:
                    # Get translated page for other languages
                    lang_title = langlinks[lang].title
                    wiki_lang = self.get_wiki_instance(lang)
                    page_lang = wiki_lang.page(lang_title)
                    
                    if page_lang.exists():
                        raw_summary = page_lang.summary[0:1000] + "..." if len(page_lang.summary) > 1000 else page_lang.summary
                        
                        translations[lang] = {
                            'summary': raw_summary,
                            'url': page_lang.fullurl
                        }
                    else:
                        translations[lang] = {
                            'summary': 'Translation not found.',
                            'url': ''
                        }
                else:
                    translations[lang] = {
                        'summary': 'Translation not found.',
                        'url': ''
                    }
            
            # Extract backward-compatible en/zh fields
            zh_summary = translations.get('zh', {}).get('summary', 'Translation not found.')
            zh_url = translations.get('zh', {}).get('url', '')
            
            # Extract Associations (from English page)
            associations = []
            
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
                "translations": translations,
                "associations": associations
            }
            
            # Save to Markdown
            await self.save_to_markdown(result)
            
            # Update database with success - include translations JSON
            translations_json = json.dumps(translations, ensure_ascii=False)
            await update_term_status(
                self.task_id, term, "completed",
                en_summary, en_url, zh_summary, zh_url,
                translations=translations_json
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
        
        filename = f"{result['term'].replace(' ', '_').replace('/', '_')}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {result['term']}\n\n")
                
                # Write all translations
                for lang, data in result.get('translations', {}).items():
                    lang_name = SUPPORTED_LANGUAGES.get(lang, lang.upper())
                    f.write(f"## {lang_name}\n")
                    f.write(f"{data.get('summary', 'N/A')}\n\n")
                    if data.get('url'):
                        f.write(f"[Link]({data['url']})\n\n")
                    
        except Exception as e:
            print(f"Error saving Markdown file: {e}")
    
    async def run(self):
        """Run the batch crawling process"""
        try:
            # Update task status to running
            await update_task_status(self.task_id, "running")
            
            # Load task config if not set
            task_info = await get_task_status(self.task_id)
            if task_info:
                if 'max_depth' in task_info:
                    self.max_depth = task_info['max_depth'] or 1
                if 'target_languages' in task_info and task_info['target_languages']:
                    self.target_languages = task_info['target_languages'].split(',')
                    # Reinitialize wiki instances with correct languages
                    self.wiki_instances = {}
                    for lang in self.target_languages:
                        self.wiki_instances[lang] = wikipediaapi.Wikipedia(
                            user_agent=self.USER_AGENT,
                            language=lang
                        )
            
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
                        langs_found = [k for k, v in result.get('translations', {}).items() if v.get('summary') and v.get('summary') != 'Translation not found.']
                        print(f"✓ Successfully crawled: {term} (Depth: {current_depth}, Languages: {', '.join(langs_found)})")
                        
                        # Handle Depth Crawling
                        next_depth = current_depth + 1
                        if next_depth < self.max_depth and result.get('associations'):
                            new_terms = []
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
    
    # Get user agent settings
    user_agent = await get_system_setting('user_agent')
    
    # We pass raw params here. run() fetches max_depth and target_languages from DB
    crawler = BatchCrawler(task_id, crawl_interval, user_agent=user_agent)
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


def get_supported_languages():
    """Return list of supported Wikipedia languages"""
    return SUPPORTED_LANGUAGES
