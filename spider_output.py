import argparse
import json
import os
import sqlite3

from search_engine import SearchEngine
from stop_stem import StopStem


DB_NAME = "spider.db"
SPIDER_RESULT_FILE = "spider_result.txt"
TEST_RESULT_FILE = "test_result.txt"
MAX_PAGES = 300


def connect_db(db_name=DB_NAME):
    if not os.path.exists(db_name):
        raise FileNotFoundError(
            f"{db_name} does not exist. Run crawler.py before running this test program."
        )
    return sqlite3.connect(db_name)


def generate_spider_result(db_name=DB_NAME, output_file=SPIDER_RESULT_FILE):
    """Read indexed data from spider.db and generate spider_result.txt."""
    conn = connect_db(db_name)
    cursor = conn.cursor()

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            cursor.execute("""
                SELECT page_id, title, url, last_modified, size
                FROM page
                WHERE title IS NOT NULL
                ORDER BY page_id
            """)

            pages = cursor.fetchall()

            for i, page in enumerate(pages):
                page_id, title, url, last_modified, size = page

                if i > 0:
                    f.write("——————————————————————————————-\n")

                f.write(f"{title if title else 'No Title'}\n")
                f.write(f"{url}\n")
                f.write(
                    f"{last_modified if last_modified else 'Unknown'}, "
                    f"{size if size else 0} bytes\n"
                )

                cursor.execute("""
                    SELECT w.word, kf.freq
                    FROM keyword_freq kf
                    JOIN word w ON kf.word_id = w.word_id
                    WHERE kf.page_id = ?
                    ORDER BY kf.freq DESC
                    LIMIT 10
                """, (page_id,))

                keywords = cursor.fetchall()
                if keywords:
                    keyword_str = "; ".join([f"{word} {freq}" for word, freq in keywords])
                    f.write(f"{keyword_str}\n")
                else:
                    f.write("No keywords\n")

                cursor.execute("""
                    SELECT p.url
                    FROM link l
                    JOIN page p ON l.child_id = p.page_id
                    WHERE l.parent_id = ?
                    LIMIT 10
                """, (page_id,))

                child_links = cursor.fetchall()
                for link in child_links:
                    f.write(f"{link[0]}\n")

                if not child_links:
                    f.write("No child links\n")

        print(f"Successfully generated {output_file}, processed {len(pages)} pages")
        return len(pages)
    finally:
        conn.close()


def make_result(test_id, name, passed, purpose, expected, evidence):
    return {
        "id": test_id,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "purpose": purpose,
        "expected": expected,
        "evidence": evidence,
    }


def format_result(result):
    lines = [
        f"Test Case {result['id']}: {result['name']}",
        "-" * (len(result["id"]) + len(result["name"]) + 11),
        f"Status  : {result['status']}",
        f"Purpose : {result['purpose']}",
        f"Expected: {result['expected']}",
        "Observed Evidence:",
    ]
    lines.extend(f"  - {line}" for line in result["evidence"])
    return "\n".join(lines)


def test_bfs_and_page_limit(cursor):
    cursor.execute("SELECT COUNT(*) FROM page WHERE title IS NOT NULL")
    page_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM page WHERE title IS NOT NULL AND url IS NOT NULL")
    url_count = cursor.fetchone()[0]
    cursor.execute("""
        SELECT page_id, title, url
        FROM page
        WHERE title IS NOT NULL
        ORDER BY page_id
        LIMIT 5
    """)
    sample_pages = cursor.fetchall()

    return make_result(
        "1.1",
        "BFS and Page Limit",
        0 < page_count <= MAX_PAGES and page_count == url_count,
        "Verify that the crawler produced a bounded BFS crawl stored in the page table.",
        f"Fetched/indexed page count should be between 1 and {MAX_PAGES}, and every fetched page should have a URL.",
        [
            f"Indexed fetched pages: {page_count}",
            f"Fetched pages with URL: {url_count}",
            f"Configured max_pages: {MAX_PAGES}",
            "First five indexed pages by page_id:",
            *[f"page_id={pid}, title={title}, url={url}" for pid, title, url in sample_pages],
        ],
    )


def test_stop_word_and_stemming(cursor):
    stop_stem = StopStem("stopwords.txt")
    stem_examples = {
        "running": "run",
        "studies": "studi",
        "information": "inform",
    }
    stemming_ok = all(stop_stem.stem(word) == expected for word, expected in stem_examples.items())
    stop_word_examples = ["and", "about", "the"]
    stop_word_results = {word: stop_stem.is_stop_word(word) for word in stop_word_examples}
    stop_words_ok = all(stop_word_results.values())
    cursor.execute("""
        SELECT COUNT(*)
        FROM word
        WHERE word GLOB '*[^a-z]*' OR word != LOWER(word)
    """)
    non_normalized_terms = cursor.fetchone()[0]
    cursor.execute("SELECT word FROM word ORDER BY word LIMIT 10")
    sample_terms = [row[0] for row in cursor.fetchall()]

    return make_result(
        "1.2",
        "Stop Word & Stemming",
        stop_words_ok and stemming_ok and non_normalized_terms == 0,
        "Verify stop-word lookup, Porter stemming, and normalized indexed terms.",
        "Common stop words should be recognized, representative words should stem correctly, and indexed terms should be lowercase alphabetic tokens.",
        [
            "Stop-word lookup examples:",
            *[f"{word}: {value}" for word, value in stop_word_results.items()],
            "Porter stemming examples:",
            *[
                f"{word} -> {stop_stem.stem(word)} (expected {expected})"
                for word, expected in stem_examples.items()
            ],
            f"Non-normalized indexed terms: {non_normalized_terms}",
            f"Sample indexed terms: {', '.join(sample_terms)}",
        ],
    )


def test_link_extraction(cursor):
    cursor.execute("SELECT COUNT(*) FROM link")
    link_count = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*)
        FROM link l
        JOIN page parent ON l.parent_id = parent.page_id
        JOIN page child ON l.child_id = child.page_id
        WHERE child.url LIKE 'http%' AND child.url NOT LIKE '%#%'
    """)
    valid_link_count = cursor.fetchone()[0]
    cursor.execute("""
        SELECT parent.url, child.url
        FROM link l
        JOIN page parent ON l.parent_id = parent.page_id
        JOIN page child ON l.child_id = child.page_id
        LIMIT 5
    """)
    sample_links = cursor.fetchall()

    return make_result(
        "1.3",
        "Link Extraction",
        link_count > 0 and valid_link_count == link_count,
        "Verify extracted links are stored as parent-child pairs and normalized as HTTP(S) URLs without fragments.",
        "The link table should contain at least one link, and all child URLs should start with HTTP(S) and contain no fragment identifier.",
        [
            f"Total stored links: {link_count}",
            f"Valid HTTP(S), fragment-free links: {valid_link_count}",
            "Sample parent -> child links:",
            *[f"{parent} -> {child}" for parent, child in sample_links],
        ],
    )


def test_recrawling_metadata(cursor):
    cursor.execute("""
        SELECT COUNT(*)
        FROM page
        WHERE title IS NOT NULL
          AND last_modified IS NOT NULL
          AND size IS NOT NULL
    """)
    pages_with_metadata = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM page WHERE title IS NOT NULL")
    page_count = cursor.fetchone()[0]

    seed_url = None
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'settings'
    """)
    if cursor.fetchone():
        cursor.execute("SELECT value FROM settings WHERE key = 'seed_url'")
        seed_row = cursor.fetchone()
        seed_url = seed_row[0] if seed_row else None
    cursor.execute("""
        SELECT title, last_modified, size
        FROM page
        WHERE title IS NOT NULL
        ORDER BY page_id
        LIMIT 5
    """)
    sample_metadata = cursor.fetchall()

    return make_result(
        "1.4",
        "Re-crawling Robustness",
        page_count > 0 and pages_with_metadata == page_count,
        "Verify that fetched pages store metadata used by the re-crawl check.",
        "Every fetched page should have title, last_modified/date, and size metadata.",
        [
            f"Pages with metadata: {pages_with_metadata}/{page_count}",
            f"Stored seed URL: {seed_url or 'not stored in this DB'}",
            "Sample metadata rows:",
            *[
                f"title={title}, last_modified={last_modified}, size={size}"
                for title, last_modified, size in sample_metadata
            ],
        ],
    )


def test_basic_vector_query():
    engine = SearchEngine()
    query = "information retrieval"
    results = engine.search(query)
    fields_ok = all(
        {"score", "title", "url", "last_modified", "size", "keywords", "parent_links", "child_links"}
        <= set(result.keys())
        for result in results
    )
    top_results = results[:3]
    return make_result(
        "2.1",
        "Basic Vector Space Query",
        isinstance(results, list) and fields_ok,
        "Verify that a normal query is preprocessed, scored, and returned as ranked result objects.",
        "Search should return a list of result dictionaries with score, metadata, keywords, and link fields.",
        [
            f"Query: {query}",
            f"Returned results: {len(results)}",
            "Top result samples:",
            *[
                f"score={item['score']}, title={item['title']}, url={item['url']}"
                for item in top_results
            ],
            f"All result objects contain expected fields: {fields_ok}",
        ],
    )


def test_title_weight(cursor):
    cursor.execute("SELECT COUNT(*) FROM posting_title")
    title_postings = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM posting_body")
    body_postings = cursor.fetchone()[0]
    cursor.execute("""
        SELECT w.word, p.title, pt.freq
        FROM posting_title pt
        JOIN word w ON pt.word_id = w.word_id
        JOIN page p ON pt.page_id = p.page_id
        LIMIT 5
    """)
    sample_title_terms = cursor.fetchall()

    return make_result(
        "2.2",
        "Title Weight Verification",
        title_postings > 0 and body_postings > 0,
        "Verify that title postings exist separately from body postings for title weighting.",
        "Both posting_title and posting_body should contain rows; title terms are later weighted by TITLE_WEIGHT in search_engine.py.",
        [
            f"posting_title rows: {title_postings}",
            f"posting_body rows: {body_postings}",
            "Sample title posting rows:",
            *[
                f"word={word}, title={title}, title_freq={freq}"
                for word, title, freq in sample_title_terms
            ],
            "Ranking implementation uses TITLE_WEIGHT = 2.0 in search_engine.py.",
        ],
    )


def test_exact_phrase_search():
    engine = SearchEngine()
    query = 'information "hong kong"'
    free_terms, phrases = engine.parse_query(query)
    phrase_parsed = phrases == [["hong", "kong"]]
    results = engine.search(query)
    top_results = results[:3]

    return make_result(
        "2.3",
        "Exact Phrase Search",
        phrase_parsed and len(results) <= 50,
        "Verify that quoted phrases are parsed and filtered through positional indexes.",
        'The query should parse "hong kong" as one phrase, and returned results should respect the 50-result limit.',
        [
            f"Query: {query}",
            f"Parsed free terms: {free_terms}",
            f"Parsed phrases: {phrases}",
            f"Returned results: {len(results)}",
            "Top phrase-result samples:",
            *[
                f"score={item['score']}, title={item['title']}, url={item['url']}"
                for item in top_results
            ],
        ],
    )


def test_web_interface_formatting():
    from app import app

    query = 'information "hong kong"'
    with app.test_client() as client:
        response = client.post("/", data={"query": query})
        html = response.get_data(as_text=True)

    expected_fragments = [
        "COMP4321 Search Engine",
        "result-score",
        "result-title",
        "result-url",
        "result-keywords",
        "Parent Links",
        "Child Links",
    ]
    missing = [fragment for fragment in expected_fragments if fragment not in html]

    return make_result(
        "2.4",
        "Web Interface Formatting",
        response.status_code == 200 and not missing,
        "Verify that Flask accepts a query and renders the expected result-page fields.",
        "The response should be HTTP 200 and include CSS/template fragments for score, title, URL, keywords, parent links, and child links.",
        [
            f"POST / query: {query}",
            f"HTTP status code: {response.status_code}",
            f"Expected template fragments: {', '.join(expected_fragments)}",
            f"Missing fragments: {missing or 'none'}",
            f"HTML response length: {len(html)} characters",
        ],
    )


def test_max_results():
    engine = SearchEngine()
    query = "movie"
    results = engine.search(query)
    return make_result(
        "2.5",
        "Max Results",
        len(results) <= 50,
        "Verify that the search engine returns no more than 50 ranked documents.",
        "The result list length should be less than or equal to 50.",
        [
            f"Query: {query}",
            f"Returned results: {len(results)}",
            f"Limit respected: {len(results) <= 50}",
        ],
    )


def build_test_registry(cursor):
    return {
        "1.1": ("BFS and Page Limit", lambda: test_bfs_and_page_limit(cursor)),
        "1.2": ("Stop Word & Stemming", lambda: test_stop_word_and_stemming(cursor)),
        "1.3": ("Link Extraction", lambda: test_link_extraction(cursor)),
        "1.4": ("Re-crawling Robustness", lambda: test_recrawling_metadata(cursor)),
        "2.1": ("Basic Vector Space Query", test_basic_vector_query),
        "2.2": ("Title Weight Verification", lambda: test_title_weight(cursor)),
        "2.3": ("Exact Phrase Search", test_exact_phrase_search),
        "2.4": ("Web Interface Formatting", test_web_interface_formatting),
        "2.5": ("Max Results", test_max_results),
    }


def run_section_6_tests(selected=None, db_name=DB_NAME, output_file=TEST_RESULT_FILE):
    """Run one or more checks matching Section 6 of docs/document.tex."""
    conn = connect_db(db_name)
    cursor = conn.cursor()
    registry = build_test_registry(cursor)
    selected_ids = selected or list(registry.keys())
    invalid_ids = [test_id for test_id in selected_ids if test_id not in registry]
    if invalid_ids:
        raise ValueError(f"Unknown test case(s): {', '.join(invalid_ids)}")

    lines = ["COMP4321 Section 6 Test Report", "=" * 33, ""]
    passed = 0

    try:
        for test_id in selected_ids:
            _, test_func = registry[test_id]
            try:
                result = test_func()
            except Exception as exc:
                result = make_result(
                    test_id,
                    registry[test_id][0],
                    False,
                    "Execute the documented test case.",
                    "The test should run without exception.",
                    [f"{type(exc).__name__}: {exc}"],
                )

            if result["status"] == "PASS":
                passed += 1

            formatted = format_result(result)
            print(formatted)
            print()
            lines.append(formatted)
            lines.append("")

        lines.extend([
            f"Summary: {passed}/{len(selected_ids)} tests passed.",
            "",
            "Note: This program also generates spider_result.txt for the Phase 1 output format.",
        ])

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        print(f"Successfully generated {output_file}")
        return passed, len(selected_ids)
    finally:
        conn.close()


def list_tests():
    conn = connect_db()
    try:
        registry = build_test_registry(conn.cursor())
        print("Available Section 6 test cases:")
        for test_id, (name, _) in registry.items():
            print(f"  {test_id}: {name}")
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate spider_result.txt and run Section 6 test cases."
    )
    parser.add_argument(
        "--test",
        action="append",
        help="Run one test case by ID, e.g. --test 1.2. Can be provided multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all Section 6 test cases.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test case IDs.",
    )
    parser.add_argument(
        "--skip-spider-result",
        action="store_true",
        help="Do not regenerate spider_result.txt.",
    )
    parser.add_argument(
        "--output",
        default=TEST_RESULT_FILE,
        help=f"Write detailed test report to this file (default: {TEST_RESULT_FILE}).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.list:
        list_tests()
    else:
        if not args.skip_spider_result:
            generate_spider_result()

        selected_tests = args.test
        if args.all or not selected_tests:
            selected_tests = None

        run_section_6_tests(selected=selected_tests, output_file=args.output)