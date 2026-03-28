import re
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from indexer import Indexer
from stop_stem import StopStem


class Crawler:
    def __init__(self, seed_url, max_pages=300, db_name="spider.db"):
        self.seed_url = seed_url
        self.max_pages = max_pages
        self.indexer = Indexer(db_name)
        self.stop_stem = StopStem("stopwords.txt")

    def fetch_page(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return response, soup
        except requests.RequestException:
            return None, None

    def get_last_modified(self, response):
        return response.headers.get("Last-Modified") or response.headers.get("Date", "")

    def should_recrawl(self, page_id, last_modified):
        info = self.indexer.get_page_info(page_id)
        if info is None or info[0] is None:
            return True
        stored_last_modified = info[1]
        return stored_last_modified != last_modified

    def tokenize(self, text):
        tokens = re.findall(r"[a-zA-Z]+", text.lower())
        result = []
        for token in tokens:
            if not self.stop_stem.is_stop_word(token):
                result.append(self.stop_stem.stem(token))
        return result

    def index_text(self, page_id, text, is_title=False):
        tokens = self.tokenize(text)

        word_positions = {}
        for position, token in enumerate(tokens):
            word_id = self.indexer.get_word_id(token)
            word_positions.setdefault(word_id, []).append(position)

        for word_id, positions in word_positions.items():
            for pos in positions:
                self.indexer.add_posting(is_title, page_id, word_id, pos)
            if not is_title:
                self.indexer.add_keyword_freq(page_id, word_id, len(positions))

    def extract_links(self, soup, base_url):
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme in ("http", "https"):
                clean = parsed._replace(fragment="").geturl()
                links.append(clean)
        return links

    def crawl(self):
        visited = set()
        queue = deque([self.seed_url])

        while queue and len(visited) < self.max_pages:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            print(f"[{len(visited)}/{self.max_pages}] Crawling: {url}")
            page_id = self.indexer.get_page_id(url)

            response, soup = self.fetch_page(url)
            if soup is None:
                continue

            last_modified = self.get_last_modified(response)

            if self.should_recrawl(page_id, last_modified):
                title = (
                    soup.title.string.strip()
                    if soup.title and soup.title.string
                    else url
                )
                body_text = soup.get_text(separator=" ")
                size = len(response.content)

                # Clear stale index data before re-indexing so postings don't accumulate
                self.indexer.clear_page_index(page_id)
                self.indexer.add_page_info(page_id, title, last_modified, size)
                self.index_text(page_id, title, is_title=True)
                self.index_text(page_id, body_text, is_title=False)

            child_links = self.extract_links(soup, url)
            for child_url in child_links:
                child_id = self.indexer.get_page_id(child_url)
                self.indexer.add_link(page_id, child_id)
                if child_url not in visited:
                    queue.append(child_url)

            self.indexer.commit()


if __name__ == "__main__":
    crawler = Crawler(
        seed_url="https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm",
        max_pages=300,
    )
    crawler.crawl()
    crawler.indexer.close()
