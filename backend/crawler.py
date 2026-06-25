import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Set, Any

class WebCrawler:
    def __init__(self, max_pages: int = 50, depth_limit: int = 2, delay: float = 0.2):
        self.max_pages = max_pages
        self.depth_limit = depth_limit
        self.delay = delay
        self.visited_urls: Set[str] = set()

    def clean_url(self, url: str) -> str:
        """Strip fragments and query params from URL for standardisation."""
        parsed = urlparse(url)
        # Reconstruct URL without fragment
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def is_same_domain(self, url: str, base_domain: str) -> bool:
        """Check if target URL belongs to the same domain as starting page."""
        parsed_url = urlparse(url)
        return parsed_url.netloc.replace('www.', '') == base_domain.replace('www.', '')

    def is_valid_page(self, url: str) -> bool:
        """Ensure we are requesting HTML pages, not media assets or files."""
        path = urlparse(url).path.lower()
        invalid_extensions = [
            '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar', 
            '.gz', '.mp4', '.mp3', '.css', '.js', '.xml', '.json',
            '.docx', '.xlsx', '.pptx', '.exe', '.dmg', '.csv'
        ]
        return not any(path.endswith(ext) for ext in invalid_extensions)

    def extract_text_and_links(self, html_content: str, current_url: str) -> tuple[str, str, List[str]]:
        """Extract title, clean text body, and all absolute internal links."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled Page"
        
        # Decompose non-content nodes
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()
            
        # Get readable text
        text = soup.get_text(separator=' ')
        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)

        # Extract links
        links = []
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            absolute_url = urljoin(current_url, href)
            cleaned_url = self.clean_url(absolute_url)
            links.append(cleaned_url)

        return title, cleaned_text, links

    def crawl(self, start_url: str, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Recursively crawl starting from start_url.
        progress_callback can be a function that accepts (msg: str, current_count: int, queue_size: int).
        """
        self.visited_urls.clear()
        start_url = self.clean_url(start_url)
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc
        
        # Queue format: (url, current_depth)
        queue: List[tuple[str, int]] = [(start_url, 0)]
        results: List[Dict[str, Any]] = []

        headers = {
            'User-Agent': 'AntigravityRAGBot/1.0 (+https://google-deepmind.github.io/antigravity)'
        }

        while queue and len(self.visited_urls) < self.max_pages:
            url, depth = queue.pop(0)

            if url in self.visited_urls:
                continue

            self.visited_urls.add(url)

            if progress_callback:
                progress_callback(f"Crawling: {url} (Depth {depth})", len(self.visited_urls), len(queue))

            try:
                # Politeness delay
                if len(self.visited_urls) > 1:
                    time.sleep(self.delay)

                response = requests.get(url, headers=headers, timeout=10)
                
                # Verify HTML response
                content_type = response.headers.get('Content-Type', '')
                if response.status_code != 200 or 'text/html' not in content_type:
                    if progress_callback:
                        progress_callback(f"Skipped (Non-HTML or error {response.status_code}): {url}", len(self.visited_urls), len(queue))
                    continue

                title, text, links = self.extract_text_and_links(response.text, url)
                
                if len(text.strip()) > 50:  # Only save pages with actual content
                    results.append({
                        "url": url,
                        "title": title,
                        "text": text
                    })

                # If we haven't reached depth limit, explore child links
                if depth < self.depth_limit:
                    for link in links:
                        if (link not in self.visited_urls and 
                                self.is_same_domain(link, base_domain) and 
                                self.is_valid_page(link) and
                                link not in [q[0] for q in queue]):
                            queue.append((link, depth + 1))

            except Exception as e:
                if progress_callback:
                    progress_callback(f"Failed to crawl {url}: {str(e)}", len(self.visited_urls), len(queue))
                continue

        if progress_callback:
            progress_callback(f"Finished crawling. Crawled {len(results)} pages successfully.", len(self.visited_urls), 0)

        return results
