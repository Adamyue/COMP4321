COMP4321 Phase 1 – readme.txt
==============================
Spider & Test Program: Build and Execution Instructions


FILES
-----
  crawler.py        Spider: BFS crawl, page fetch, link extraction, and indexing
  indexer.py        Database layer: SQLite schema creation and all CRUD operations
  stop_stem.py      Stop-word filtering and Porter stemming (via NLTK)
  spider_output.py  Test program: reads spider.db and writes spider_result.txt
  stopwords.txt     List of English stop words
  requirements.txt  Python package dependencies
  database_design.txt  Design document for the SQLite database schema
  spider_result.txt    Output file produced by spider_output.py

REQUIREMENTS
------------
  - Python 3.8 or higher
  - pip (Python package manager)
  - Internet access to reach:
      https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm
    (Backup: https://comp4321-hkust.github.io/testpages/testpage.htm)


STEP 1 – INSTALL DEPENDENCIES
-------------------------------
Run the following command from the project directory:

    pip install -r requirements.txt

This installs:
  - requests      (HTTP fetching)
  - beautifulsoup4 (HTML parsing)
  - nltk          (Porter stemmer)
  - pytest        (unit test runner)

One-time NLTK data download (required for the Porter stemmer):

    python -c "import nltk; nltk.download('punkt')"

No compilation or build step is needed; Python scripts run directly.


STEP 2 – RUN THE SPIDER
------------------------
Execute from the project directory:

    python crawler.py

What it does:
  1. Starts a breadth-first crawl from the seed URL:
         https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm
  2. Fetches up to 30 pages.
  3. For each page:
       - Extracts and indexes title and body text (stop words removed, Porter stemmed).
       - Records parent/child link relationships.
       - Skips re-fetching if Last-Modified is unchanged from a previous run.
  4. Writes all indexed data to spider.db (SQLite, created in the same directory).

Progress is printed to stdout, e.g.:
  [1/30] Crawling: https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm
  [2/30] Crawling: ...

To change the seed URL or page limit, edit the __main__ block at the bottom
of crawler.py:

    crawler = Crawler(
        seed_url="https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm",
        max_pages=30,
    )


STEP 3 – RUN THE TEST PROGRAM
-------------------------------
After the spider has finished (spider.db must exist), run:

    python spider_output.py

What it does:
  - Reads all indexed pages from spider.db.
  - Writes spider_result.txt in the same directory.

Each entry in spider_result.txt has the format:

    Page title
    URL
    Last modification date, size of page
    Keyword1 freq1; Keyword2 freq2; Keyword3 freq3; ...
    Child Link1
    Child Link2
    ...
    ——————————————————————————————-

  - Up to 10 keywords (stemmed, stop words excluded) with their frequencies.
  - Up to 10 child links per page.
  - Pages are separated by the dashed line shown above.

On success the program prints:
  Successfully generated spider_result.txt, processed 30 pages


RE-RUNNING THE SPIDER
----------------------
The spider can be run multiple times safely:
  - Pages whose Last-Modified header is unchanged are skipped (not re-indexed).
  - Pages that have been updated are re-indexed from scratch (stale postings
    are cleared before new ones are inserted).
  - Cyclic links are handled via a visited set; each URL is processed at most
    once per run.
  - To start a completely fresh crawl, delete spider.db before running
    crawler.py again.