import argparse
import json
import os
import sqlite3

from search_engine import SearchEngine
from stop_stem import StopStem


DB_NAME = "spider.db"
SPIDER_RESULT_FILE = "spider_result.txt"
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

if __name__ == "__main__":
    generate_spider_result()