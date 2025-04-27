import os
import platform
import subprocess
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from typing import List, Dict
import scrapy
from scrapy.crawler import CrawlerProcess
import json
from datetime import datetime
from googlesearch import search
import re
from bs4 import BeautifulSoup
import sqlite3
import logging
from urllib.parse import urlparse, urljoin
import random
import time
import webbrowser
import requests
from twisted.internet.error import DNSLookupError, TimeoutError


from proxy_cheaker import proxy_cheaker

# Add parent directory to path for imports

# User agents for rotation
USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]


# Create logs directory if it doesn't exist
os.makedirs("database/logs", exist_ok=True)

# Format timestamp for Windows compatibility
timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f"database/logs/scraperdata_logs_{timestamp}.log"),
        logging.StreamHandler()
    ]
)

class WebScraperError(Exception):
    """Custom exception for web scraper errors"""
    pass

def get_random_headers():
    """Return random headers for requests"""
    return {
        'User-Agent': random.choice(USER_AGENTS_LIST),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
    }


def extract_main_words(query):
    """Extract significant words from a query without external libraries."""
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'by', 'for', 'from', 
        'has', 'in', 'is', 'it', 'of', 'on', 'that', 'the', 'to', 'was', 'when', 
        'where', 'will', 'with'
    }
    # Split query into words and filter
    words = query.lower().split()
    main_words = [word for word in words if word.isalpha() and word not in stop_words]
    return main_words

def searchec(query, num_results=10):
    """Enhanced search function with better error handling"""
    urls = []
    try:
        for result in search(
            query,
            sleep_interval=5,
            num_results=num_results,
            lang='en',
            advanced=True,
            safe=None,
            unique=True
        ):
            url = getattr(result, 'url', result) if hasattr(result, 'url') else result
            if isinstance(url, str) and url.startswith("http"):
                urls.append(url)

        # Load existing data
        os.makedirs("database", exist_ok=True)
        try:
            with open("database/output.json", "r") as json_file:
                data = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"urls": []}

        # Add new URLs with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for url in urls:
            data["urls"].insert(0, {"url": url, "timestamp": timestamp})

        with open("database/output.json", "w") as json_file:
            json.dump(data, json_file, indent=4)
            logging.info(f"URLs added successfully at {timestamp}")
        print(urls)
        return urls

    except Exception as e:
        logging.error(f"Search error for query '{query}': {str(e)}")
        return []


def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    boilerplate = [
        r'Skip to main content', r'Sign In', r'Subscribe', r'Log In', r'Privacy Policy',
        r'© \\d{4}', r'Search', r'Home', r'About', r'Contact', r'More', r'Follow us',
        r'Terms of Use', r'Cookie Preferences', r'Netflix Shop', r'Top 10', r'Trending'
    ]
    for pattern in boilerplate:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()

def init_database():
    """Initialize SQLite database with error handling"""
    try:
        os.makedirs("database", exist_ok=True)
        conn = sqlite3.connect("database/scraped_data.db", timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                body_content TEXT,
                meta_description TEXT,
                meta_keywords TEXT,
                images TEXT,
                videos TEXT,
                audio TEXT,
                links TEXT,
                social_media TEXT,
                files TEXT,
                og_title TEXT,
                og_description TEXT,
                og_image TEXT,
                twitter_card TEXT,
                twitter_title TEXT,
                twitter_description TEXT,
                twitter_image TEXT,
                canonical_url TEXT,
                robots TEXT,
                author TEXT,
                published_date TEXT,
                modified_date TEXT,
                timestamp TEXT
            )
        """)

        conn.commit()
        logging.info("Database initialized successfully")
    except sqlite3.Error as e:
        logging.error(f"Database initialization error: {str(e)}")
        raise WebScraperError(f"Failed to initialize database: {str(e)}")
    finally:
        conn.close()


def is_downloadable(content_type):
    downloadable_types = [
        'application/pdf', 'application/msword', 'application/vnd.ms-excel',
        'application/zip', 'application/x-rar-compressed', 'application/octet-stream'
    ]
    return any(dtype in content_type.lower() for dtype in downloadable_types)

def make_absolute_url(base_url, rel_url):
    if not isinstance(rel_url, str) or not rel_url:
        return ""
    try:
        return urljoin(base_url, rel_url) if not rel_url.startswith(('http://', 'https://')) else rel_url
    except Exception as e:
        logging.warning(f"URL joining error: {e}")
        return ""

class EnhancedContentSpider(scrapy.Spider):
    name = "enhanced_content_spider"
    custom_settings = {
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429],
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    def __init__(self, urls=None, proxies=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = urls or []
        self.proxies = proxies or []

    def start_requests(self):
        """Start requests with proxy rotation"""
        for url in self.start_urls:
            proxy = random.choice(self.proxies) if self.proxies and not url.startswith('https://') else None
            yield scrapy.Request(
                url=url,
                meta={'proxy': proxy} if proxy else None,
                callback=self.parse,
                errback=self.errback,
                headers=get_random_headers()
            )

    def parse(self, response):
        """Parse response with improved error handling"""
        try:
            if response.status != 200:
                logging.error(f"Non-200 status code ({response.status}) for {response.url}")
                return {'url': response.url, 'error': f'Status code: {response.status}'}
                
            if not response.body:
                logging.error(f"Empty response body for {response.url}")
                return {'url': response.url, 'error': 'Empty response'}
                
            content_type = response.headers.get('content-type', b'').decode().lower()
            if 'text/html' not in content_type:
                logging.error(f"Non-HTML content type ({content_type}) for {response.url}")
                return {'url': response.url, 'error': f'Invalid content type: {content_type}'}

            # if not any(t in content_type for t in ['text/html', 'application/pdf']):
            #     logging.warning(f"Non-supported content type: {content_type}")
            #     return
            
            # if 'application/pdf' in content_type:
            #     filename = response.url.split('/')[-1]
            #     with open(f"downloads/{filename}", 'wb') as f:
            #         f.write(response.body)

            
            soup = BeautifulSoup(response.body, 'html.parser')
            # Extract pdf
                # Look for embedded viewers
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src', '')
                if '.pdf' in src:
                    files.append({
                        'url': make_absolute_url(response.url, src),
                        'title': 'Embedded PDF'
                    })
                    logging.info(f"Found embedded PDF: {src}")

            # Extract images
            images = []
            for img in soup.find_all('img'):
                if img.get('src'):
                    images.append({
                        'src': make_absolute_url(response.url, img.get('src')),
                        'alt': img.get('alt', ''),
                        'title': img.get('title', '')
                    })
            # Extract videos (including iframes for YouTube/Vimeo)
            videos = []
            for video in soup.find_all(['video', 'iframe']):
                src = video.get('src') or next((source.get('src') for source in video.find_all('source')), None)
                if src:
                    videos.append({
                        'src': make_absolute_url(response.url, src),
                        'type': video.get('type', ''),
                        'title': video.get('title', '')
                    })
            # Extract audio
            audio = []
            for audio_tag in soup.find_all(['audio']):
                src = audio_tag.get('src') or next((source.get('src') for source in audio_tag.find_all('source')), None)
                if src:
                    audio.append({
                        'src': make_absolute_url(response.url, src),
                        'type': audio_tag.get('type', '')
                    })
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                href = make_absolute_url(response.url, link['href'])
                if href:
                    links.append({
                        'url': href,
                        'text': link.get_text(strip=True),
                        'title': link.get('title', '')
                    })

            # Extract social media links
            social_media = []
            social_patterns = ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com', 'youtube.com']
            for link in links:
                if any(pattern in link['url'].lower() for pattern in social_patterns):
                    social_media.append(link)

            # Extract downloadable files
            files = []
            file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.zip', '.rar']
            for link in soup.find_all('a', href=True):
                href = make_absolute_url(response.url, link['href'])
                if href and any(href.lower().endswith(ext) for ext in file_extensions):
                    try:
                        head = requests.head(href, headers=get_random_headers(), timeout=5, allow_redirects=True)
                        if is_downloadable(head.headers.get('content-type', '')):
                            files.append({
                                'url': href,
                                'title': link.get('title', '') or link.get_text(strip=True)
                            })
                    except Exception as e:
                        logging.warning(f"Failed to HEAD-check file link: {href} – {str(e)}")

            
            page_data = {
                'title': response.css('title::text').get(default=''),
                'body_content': clean_text(soup.get_text(separator=' ', strip=True)),
                'meta_description': response.css('meta[name="description"]::attr(content)').get(default=''),
                'meta_keywords': response.css('meta[name="keywords"]::attr(content)').get(default=''),
                'images': json.dumps(images),
                'videos': json.dumps(videos),
                'audio': json.dumps(audio),
                'links': json.dumps(links),
                'social_media': json.dumps(social_media),
                'files': json.dumps(files),
                'og_title': response.css('meta[property="og:title"]::attr(content)').get(default=''),
                'og_description': response.css('meta[property="og:description"]::attr(content)').get(default=''),
                'og_image': response.css('meta[property="og:image"]::attr(content)').get(default=''),
                'twitter_card': response.css('meta[name="twitter:card"]::attr(content)').get(default=''),
                'twitter_title': response.css('meta[name="twitter:title"]::attr(content)').get(default=''),
                'twitter_description': response.css('meta[name="twitter:description"]::attr(content)').get(default=''),
                'twitter_image': response.css('meta[name="twitter:image"]::attr(content)').get(default=''),
                'canonical_url': response.css('link[rel="canonical"]::attr(href)').get(default=''),
                'robots': response.css('meta[name="robots"]::attr(content)').get(default=''),
                'author': response.css('meta[name="author"]::attr(content)').get(default=''),
                'published_date': response.css('meta[property="article:published_time"]::attr(content)').get(default=''),
                'modified_date': response.css('meta[property="article:modified_time"]::attr(content)').get(default=''),
                
                # Add other metadata extractions
            }

            # Store data
            self.store_data(response.url, page_data)
            
            yield {
                'url': response.url,
                'title': page_data['title'],
                'content_length': len(page_data['body_content']),
                'content_summary': {
                    'images_count': len(images),
                    'videos_count': len(videos),
                    'audio_count': len(audio),
                    'links_count': len(links),
                    'social_media_count': len(social_media),
                    'files_count': len(files)
                }
                    
                
            }


        except Exception as e:
            logging.error(f"Parse error for {response.url}: {str(e)}")
            yield {'url': response.url, 'error': str(e)}

    def store_data(self, url, page_data):
        """Store data in database with transaction handling"""
        conn = sqlite3.connect("database/scraped_data.db", timeout=10)
        cursor = conn.cursor()
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT OR REPLACE INTO pages (
                    url, title, body_content, meta_description, meta_keywords,
                    images, videos, audio, links, social_media, files,
                    og_title, og_description, og_image,
                    twitter_card, twitter_title, twitter_description, twitter_image,
                    canonical_url, robots, author, published_date, modified_date,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
                url,
                page_data.get('title', ''),
                page_data.get('body_content', ''),
                page_data.get('meta_description', ''),
                page_data.get('meta_keywords', ''),
                page_data.get('images', '[]'),
                page_data.get('videos', '[]'),
                page_data.get('audio', '[]'),
                page_data.get('links', '[]'),
                page_data.get('social_media', '[]'),
                page_data.get('files', '[]'),
                page_data.get('og_title', ''),
                page_data.get('og_description', ''),
                page_data.get('og_image', ''),
                page_data.get('twitter_card', ''),
                page_data.get('twitter_title', ''),
                page_data.get('twitter_description', ''),
                page_data.get('twitter_image', ''),
                page_data.get('canonical_url', ''),
                page_data.get('robots', ''),
                page_data.get('author', ''),
                page_data.get('published_date', ''),
                page_data.get('modified_date', ''),
                timestamp
            ))
            conn.commit()
            logging.info(f"Successfully stored data for {url}")
            open_close_url(url)  # Open the URL in a web browser
            
        except sqlite3.Error as e:
            conn.rollback()
            logging.error(f"Database store error for {url}: {str(e)}")
        finally:
            conn.close()

    def errback(self, failure):
        """Handle request failures"""
        
        url = failure.request.url
        logging.error(f"Request failed for {url}")
        logging.error(f"Failure type: {type(failure)}")
        logging.error(f"Failure value: {failure.value}")
        logging.error(f"Traceback: {failure.getTraceback()}")
        # Handle specific errors if needed
        if failure.check(DNSLookupError):
            error = "DNS lookup failed"
        elif failure.check(TimeoutError):
            error = "Request timeout"
        else:
            error = str(failure.value) or "Unknown error"
            
        logging.error(f"Error details: {error}")
        logging.error(f"Request failed for {url}: {error}")
        self.store_data(url, {'title': 'Error', 'body_content': f"Failed: {error}"})

def scrape_urls(query=None, urls=None, max_retries=3):
    """Main scraping function with improved reliability"""
    try:
        init_database()
        
        if query and not urls:
            urls = searchec(query)
        
        if not urls:
            logging.warning("No URLs to scrape")
            return False

        raw_proxies = proxy_cheaker() if 'proxy_cheaker' in globals() else []
        working_proxies = ['http://' + proxy if not proxy.startswith(('http://', 'https://')) else proxy for proxy in raw_proxies]
        logging.info(f"Formatted proxies: {working_proxies}")
        
        process = CrawlerProcess({
            'USER_AGENT': random.choice(USER_AGENTS_LIST),
            'ROBOTSTXT_OBEY': False,
            'DOWNLOAD_TIMEOUT': 30,
            'AUTOTHROTTLE_ENABLED': True,
            'AUTOTHROTTLE_START_DELAY': 1,
            'AUTOTHROTTLE_MAX_DELAY': 5,
            'CONCURRENT_REQUESTS': 8,
            'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
            'DOWNLOADER_MIDDLEWARES': {
                'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550,
            },
            'ROTATING_PROXY_LIST': working_proxies,
            'LOG_LEVEL': 'INFO',
            'FEED_FORMAT': 'json',
            'FEED_URI': 'database/scraped_data.json',
            'FEED_EXPORT_ENCODING': 'utf-8',
        })

        for attempt in range(max_retries):
            try:
                process.crawl(EnhancedContentSpider, urls=urls, proxies=working_proxies)
                process.start()
                logging.info(f"Scraping completed for {len(urls)} URLs")
                return True
            except Exception as e:
                logging.error(f"Scraping attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise WebScraperError(f"Scraping failed after {max_retries} attempts")
                time.sleep(5)

    except Exception as e:
        logging.error(f"Scraping error: {str(e)}")
        return False

def query_database(search_terms=None, limit=10, content_type=None):
    """Enhanced database query function with better relevance scoring"""
    conn = sqlite3.connect("database/scraped_data.db", timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Standardize search terms if present
        if not search_terms:
            search_terms = []
        elif isinstance(search_terms, str):
            search_terms = search_terms.split()
            
        logging.info(f"Searching with terms: {search_terms}")
        
        # For relevance scoring, we'll use SQLite's CASE expressions
        if search_terms:
            # Build the base query with relevance scoring
            title_conditions = []
            body_conditions = []
            meta_conditions = []
            relevance_factors = []
            params = []
            
            # Add scoring for each search term
            for i, term in enumerate(search_terms):
                term_param = f'%{term}%'
                
                # Add relevance factors with different weights per field
                relevance_factors.append(f"(CASE WHEN title LIKE ? THEN 10 ELSE 0 END)")
                relevance_factors.append(f"(CASE WHEN meta_description LIKE ? THEN 5 ELSE 0 END)")
                relevance_factors.append(f"(CASE WHEN body_content LIKE ? THEN 1 ELSE 0 END)")
                
                # Add parameters for the CASE statements
                params.extend([term_param, term_param, term_param])
                
                # Add conditions for WHERE clause
                title_conditions.append(f"title LIKE ?")
                meta_conditions.append(f"meta_description LIKE ?")
                body_conditions.append(f"body_content LIKE ?")
            
            # Combine all conditions for WHERE clause
            combined_conditions = []
            for term_idx in range(len(search_terms)):
                combined_conditions.append(
                    f"({title_conditions[term_idx]} OR {meta_conditions[term_idx]} OR {body_conditions[term_idx]})"
                )
                
                # Add parameters for the WHERE clause - need to duplicate the parameters
                params.extend([f'%{search_terms[term_idx]}%'] * 3)
            
            # Build the relevance score expression
            relevance_score = " + ".join(relevance_factors)
            
            # Start building the query
            query = f"""
                SELECT *, ({relevance_score}) AS relevance 
                FROM pages
                WHERE {" AND ".join(combined_conditions)}
            """
        else:
            # No search terms, just get all pages
            query = "SELECT *, 0 AS relevance FROM pages WHERE 1=1"
            params = []
        
        # Add content type filtering
        if content_type:
            if isinstance(content_type, list) and content_type:
                content_conditions = []
                for ctype in content_type:
                    # Skip invalid content types
                    if ctype not in ['images', 'videos', 'files', 'links', 'text']:
                        continue
                        
                    if ctype == 'text':
                        # Text is a special case - pages that primarily contain text
                        content_conditions.append(
                            "(JSON_ARRAY_LENGTH(images) < 3 AND JSON_ARRAY_LENGTH(videos) < 2 AND body_content IS NOT NULL AND LENGTH(body_content) > 100)"
                        )
                    else:
                        content_conditions.append(
                            f"{ctype} IS NOT NULL AND {ctype} != '[]' AND JSON_ARRAY_LENGTH({ctype}) > 0"
                        )
                
                if content_conditions:
                    query += " AND (" + " OR ".join(content_conditions) + ")"
            elif isinstance(content_type, str) and content_type:
                if content_type == 'text':
                    query += " AND (JSON_ARRAY_LENGTH(images) < 3 AND JSON_ARRAY_LENGTH(videos) < 2 AND body_content IS NOT NULL AND LENGTH(body_content) > 100)"
                else:
                    query += f" AND {content_type} IS NOT NULL AND {content_type} != '[]' AND JSON_ARRAY_LENGTH({content_type}) > 0"
        
        # Add sorting - prioritize relevance score, then recency
        if search_terms:
            query += " ORDER BY relevance DESC, timestamp DESC"
        else:
            query += " ORDER BY timestamp DESC"
            
        # Add limit
        if limit:
            query += f" LIMIT {limit}"
        
        # Log the query for debugging
        logging.info(f"SQL Query: {query}")
        logging.info(f"Parameters: {params}")
        
        # Save the query for debugging
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        
        # Create a valid filename
        search_terms_str = "_".join(search_terms) if search_terms else "all"
        filename = f"{search_terms_str}__{timestamp}.txt"
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)  # Remove invalid characters
        
        results_dir = os.path.join("database", "scraped_results")
        os.makedirs(results_dir, exist_ok=True)
        result_file = os.path.join(results_dir, filename)
        
        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Save to file and prepare results
        results = []
        with open(result_file, "a", encoding="utf-8") as f:
            f.write(f"Query: {search_terms}\nTimestamp: {timestamp}\n")
            f.write("-" * 80 + "\n\n")
            
            for idx, row in enumerate(rows, 1):
                row_dict = dict(row)
                results.append(row_dict)
                
                f.write(f"Result #{idx}:\n")
                for k, v in row_dict.items():
                    f.write(f"  {k}: {v}\n")
                f.write("-" * 80 + "\n\n")
                
            f.write(f"\nTotal results: {len(results)}\n")
            logging.info(f"Results written to {result_file}")
        
        logging.info(f"Found {len(results)} results for search terms: {search_terms}")
        return results

    except sqlite3.Error as e:
        logging.error(f"Database query error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Error in query_database: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return []
    finally:
        conn.close()
        
def open_close_url(url, timeout=5, opened_urls=None):
    """
    Open a URL in a web browser, wait for the specified time, and then close the browser tab.
    Ensures that the same URL is not opened multiple times.
    
    Parameters:
    - url: URL string to open
    - timeout: Time in seconds to wait before closing (default: 5)
    - opened_urls: Optional list to track opened URLs across multiple calls
    
    Returns:
    - bool: True if URL was successfully opened and closed, False otherwise
    """
    # Initialize tracking list if not provided
    if opened_urls is None:
        opened_urls = []
    
    try:
        # Validate URL format
        if not isinstance(url, str):
            logging.warning(f"Invalid URL type: {type(url).__name__}. Expected string.")
            return False
        
        # More thorough URL validation
        url = url.strip()
        if not url:
            logging.warning("Empty URL provided")
            return False
        
        # Ensure URL has http/https scheme
        if not url.startswith(("http://", "https://")):
            # Try to fix URL by adding https:// prefix
            logging.info(f"Adding https:// prefix to URL: {url}")
            url = "https://" + url
        
        # Check URL format using regex (basic check)
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?'  # domain
            r'(/[^\s]*)?$'  # optional path
        )
        
        if not url_pattern.match(url):
            logging.warning(f"Invalid URL format: {url}")
            return False
            
        # Parse URL to check components
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            logging.warning(f"URL missing required components: {url}")
            return False
        
        # Check for duplicates
        if url in opened_urls:
            logging.warning(f"Skipping duplicate URL: {url}")
            return False
        
        # Open the URL in the default web browser
        success = webbrowser.open(url)
        if not success:
            logging.error(f"Failed to open URL: {url}")
            return False
            
        logging.info(f"Opened URL: {url}")
        opened_urls.append(url)
        
        # Wait for specified timeout
        logging.info(f"Waiting {timeout} seconds before closing...")
        time.sleep(timeout)
        
        # Attempt to close the browser tab based on operating system
        system = platform.system()
        
        try:
            if system == "Windows":
                # Send keyboard shortcut to close tab (Ctrl+W)
                subprocess.run(['powershell', '-command', 
                              '$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys("^w")'])
            elif system == "Darwin":  # macOS
                # Send Command+W to close the active tab
                subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke "w" using command down'])
            elif system == "Linux":
                # Send Ctrl+W using xdotool if available
                if subprocess.run(['which', 'xdotool'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                    subprocess.run(['xdotool', 'key', 'ctrl+w'])
                else:
                    logging.warning("Cannot close tab: xdotool not installed on Linux")
            
            logging.info(f"Attempted to close URL: {url}")
            return True
            
        except Exception as e:
            logging.error(f"Error while trying to close tab: {str(e)}")
            return False
            
    except Exception as e:
        logging.error(f"Error processing URL: {str(e)}")
        return False

        
if __name__ == "__main__":
    # Example usage
    query = "best laptop to buy"
    print(f"[+] Scraping for: {query}")
    # scrape_urls(query=query, max_retries=3)

    # Example database query
    search_terms = extract_main_words(query)
    print(f"Extracted search terms: {query}")
    results = query_database(search_terms=query, limit=50, content_type='images')
   
   
    # # for result in results:
    # #     print(result)
    # # write_results(results=results)
    # data = ""
    # if results:
    #     resultnum = len(results)
        
    #     for i, item in enumerate(results, 1):
    #         data += f"\n\n\n === Scraped Results ==="
    #         data += f"\nResult {i}:"
    #         data += f"\nTitle: {item['title']}"
    #         data += f"\nURL: {item['url']}"
    #         # Truncate body content for readability (e.g., first 200 characters)
    #         body_preview = item['body_content'][:2000] + "..." if len(item['body_content']) > 200 else item['body_content']
    #         data += f"\nBody: {body_preview}"
    #         data += f"\nImages: {json.loads(item['images'])}"
    #         data += f"\nVideos: {json.loads(item['videos'])}"
    #         data += f"\nAudio: {json.loads(item['audio'])}"
    #         data += f"\nLinks: {json.loads(item['links'])}"
    #         data += f"\nSocial Media: {json.loads(item['social_media'])}"
    #         data += f"\nFiles: {json.loads(item['files'])}"
    #         data += f"\nTimestamp: {item['timestamp']}"
    #     # Write results to a file
    #     os.makedirs("database/scraped_results", exist_ok=True)
    #     query = query.replace(" ", "_").replace(":", "").replace("/", "_").replace("?", "").replace("!", "").replace(",", "").replace(".", "").replace("'", "").replace('"', "")
    #     # Remove special characters from query string
    #     query = re.sub(r'[<>:"/\\|?*]', '', query)
    #     with open(f"database/scraped_results/{query}__{timestamp}.txt", "w", encoding="utf-8") as f:
    #         f.write(data)
    #         print(f"Results written database/scraped_results/{query}__{resultnum}__{timestamp}.txt")
            
        
    # else:
    #     print("No results retrieved from the database.")