import argparse
import json
import os
import sqlite3
import time

from crawler import Crawler
from stop_stem import StopStem


DEFAULT_DB = "spider.db"


def connect_db(db_name=DEFAULT_DB):
    if not os.path.exists(db_name):
        raise FileNotFoundError(f"{db_name} does not exist. Run crawler.py or station2_demo.py reindex first.")
    return sqlite3.connect(db_name)


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def get_word_id(cursor, stem):
    cursor.execute("SELECT word_id FROM word WHERE word = ?", (stem,))
    row = cursor.fetchone()
    return row[0] if row else None


def print_postings(cursor, word_id, table_name, limit):
    cursor.execute(
        f"""
        SELECT p.page_id, p.title, p.url, posting.freq, posting.positions
        FROM {table_name} posting
        JOIN page p ON posting.page_id = p.page_id
        WHERE posting.word_id = ?
        ORDER BY posting.freq DESC, p.page_id ASC
        LIMIT ?
        """,
        (word_id, limit),
    )
    rows = cursor.fetchall()

    print(f"\n{table_name}")
    print("-" * len(table_name))
    if not rows:
        print("not found")
        return

    for page_id, title, url, freq, positions_json in rows:
        positions = json.loads(positions_json)
        preview = positions[:10]
        suffix = "..." if len(positions) > 10 else ""
        print(f"page_id={page_id}")
        print(f"title={title}")
        print(f"url={url}")
        print(f"freq={freq}")
        print(f"positions={preview}{suffix}")
        print()


def inspect_term(args):
    stop_stem = StopStem("stopwords.txt")
    raw = args.term.lower()

    print(f"Input term: {args.term}")
    if stop_stem.is_stop_word(raw):
        print(f"Result: not found because '{raw}' is a stop word and is not indexed.")
        return

    stem = stop_stem.stem(raw)
    print(f"Stemmed lookup term: {stem}")

    conn = connect_db(args.db)
    cursor = conn.cursor()
    try:
        word_id = get_word_id(cursor, stem)
        if word_id is None:
            print("Result: not found in word table.")
            return

        print(f"word_id={word_id}")
        print_postings(cursor, word_id, "posting_title", args.limit)
        print_postings(cursor, word_id, "posting_body", args.limit)
    finally:
        conn.close()


def compare_terms(args):
    stop_stem = StopStem("stopwords.txt")
    terms = [args.term1.lower(), args.term2.lower()]
    stems = [stop_stem.stem(term) if not stop_stem.is_stop_word(term) else None for term in terms]

    print(f"{args.term1} -> {stems[0] if stems[0] else 'STOP_WORD'}")
    print(f"{args.term2} -> {stems[1] if stems[1] else 'STOP_WORD'}")

    if stems[0] is None or stems[1] is None:
        print("At least one term is a stop word and is not indexed.")
        return

    conn = connect_db(args.db)
    cursor = conn.cursor()
    try:
        ids = [get_word_id(cursor, stem) for stem in stems]
        print(f"word_id({stems[0]})={ids[0]}")
        print(f"word_id({stems[1]})={ids[1]}")
        print(f"Same stem: {stems[0] == stems[1]}")
        print(f"Same word_id: {ids[0] == ids[1]}")
    finally:
        conn.close()


def show_schema(args):
    conn = connect_db(args.db)
    cursor = conn.cursor()
    try:
        tables = [
            "page",
            "word",
            "posting_body",
            "posting_title",
            "link",
            "keyword_freq",
            "settings",
        ]
        print("SQLite DB schema tour")
        print("=====================")
        for table in tables:
            if not table_exists(cursor, table):
                print(f"\n{table}: missing")
                continue

            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            print(f"\n{table} ({count} rows)")
            for _, name, col_type, not_null, default, pk in columns:
                pk_text = " PRIMARY KEY" if pk else ""
                print(f"  {name} {col_type}{pk_text}")

        print("\nImportant design evidence:")
        print("  posting_body and posting_title are separate inverted indexes.")
        print("  both posting tables include freq and positions.")
        print("  positions is a JSON list used for exact phrase search.")
    finally:
        conn.close()


def reindex(args):
    if args.fresh and os.path.exists(args.db):
        os.remove(args.db)
        print(f"Deleted old DB: {args.db}")

    start = time.perf_counter()
    crawler = Crawler(args.seed_url, max_pages=args.max_pages, db_name=args.db)
    crawler.crawl()
    crawler.indexer.close()
    elapsed = time.perf_counter() - start

    conn = connect_db(args.db)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM page WHERE title IS NOT NULL")
        page_count = cursor.fetchone()[0]
    finally:
        conn.close()

    print(f"Fresh re-index finished: pages={page_count}, elapsed={elapsed:.2f}s, db={args.db}")


def parse_args():
    parser = argparse.ArgumentParser(description="Station 2 Indexing & DB demo utility.")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite DB file. Default: spider.db")

    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect posting lists for a term/stem.")
    inspect_parser.add_argument("term", help="Raw term or stem, e.g. movie, the, running")
    inspect_parser.add_argument("--limit", type=int, default=5, help="Rows to print per posting table.")
    inspect_parser.set_defaults(func=inspect_term)

    compare_parser = subparsers.add_parser("compare", help="Compare stemming/word_id for two terms.")
    compare_parser.add_argument("term1")
    compare_parser.add_argument("term2")
    compare_parser.set_defaults(func=compare_terms)

    schema_parser = subparsers.add_parser("schema", help="Print DB schema tour.")
    schema_parser.set_defaults(func=show_schema)

    reindex_parser = subparsers.add_parser("reindex", help="Fresh crawl/re-index from a seed URL.")
    reindex_parser.add_argument("seed_url")
    reindex_parser.add_argument("-n", "--max-pages", type=int, default=30)
    reindex_parser.add_argument("--fresh", action="store_true", help="Delete DB before re-indexing.")
    reindex_parser.set_defaults(func=reindex)

    return parser.parse_args()


if __name__ == "__main__":
    parsed_args = parse_args()
    parsed_args.func(parsed_args)
