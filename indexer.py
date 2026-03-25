import sqlite3
import json

class Indexer:
    def __init__(self, db_name="spider.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS page (
                page_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                last_modified TEXT,
                size INTEGER
            );
            CREATE TABLE IF NOT EXISTS link (
                parent_id INTEGER,
                child_id INTEGER,
                PRIMARY KEY (parent_id, child_id)
            );
            CREATE TABLE IF NOT EXISTS word (
                word_id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS posting_body (
                word_id INTEGER,
                page_id INTEGER,
                freq INTEGER,
                positions TEXT,
                PRIMARY KEY (word_id, page_id)
            );
            CREATE TABLE IF NOT EXISTS posting_title (
                word_id INTEGER,
                page_id INTEGER,
                freq INTEGER,
                positions TEXT,
                PRIMARY KEY (word_id, page_id)
            );
            CREATE TABLE IF NOT EXISTS keyword_freq (
                page_id INTEGER,
                word_id INTEGER,
                freq INTEGER,
                PRIMARY KEY (page_id, word_id)
            );
        ''')
        self.conn.commit()

    def get_page_id(self, url):
        self.cursor.execute("SELECT page_id FROM page WHERE url = ?", (url,))
        res = self.cursor.fetchone()
        if res:
            return res[0]
        self.cursor.execute("INSERT INTO page (url) VALUES (?)", (url,))
        return self.cursor.lastrowid

    def get_url(self, page_id):
        self.cursor.execute("SELECT url FROM page WHERE page_id = ?", (page_id,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def add_page_info(self, page_id, title, last_modified, size):
        self.cursor.execute("""
            UPDATE page 
            SET title = ?, last_modified = ?, size = ? 
            WHERE page_id = ?
        """, (title, last_modified, size, page_id))

    def get_page_info(self, page_id):
        self.cursor.execute("SELECT title, last_modified, size FROM page WHERE page_id = ?", (page_id,))
        return self.cursor.fetchone()

    def get_word_id(self, word):
        self.cursor.execute("SELECT word_id FROM word WHERE word = ?", (word,))
        res = self.cursor.fetchone()
        if res:
            return res[0]
        self.cursor.execute("INSERT INTO word (word) VALUES (?)", (word,))
        return self.cursor.lastrowid

    def get_word(self, word_id):
        self.cursor.execute("SELECT word FROM word WHERE word_id = ?", (word_id,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def add_link(self, parent_id, child_id):
        self.cursor.execute("INSERT OR IGNORE INTO link (parent_id, child_id) VALUES (?, ?)", (parent_id, child_id))

    def get_child_links(self, page_id):
        self.cursor.execute("SELECT child_id FROM link WHERE parent_id = ?", (page_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def add_posting(self, is_title, page_id, word_id, position):
        table = "posting_title" if is_title else "posting_body"
        self.cursor.execute(f"SELECT freq, positions FROM {table} WHERE word_id = ? AND page_id = ?", (word_id, page_id))
        res = self.cursor.fetchone()
        if res:
            freq = res[0] + 1
            positions = json.loads(res[1])
            positions.append(position)
            self.cursor.execute(f"UPDATE {table} SET freq = ?, positions = ? WHERE word_id = ? AND page_id = ?",
                                (freq, json.dumps(positions), word_id, page_id))
        else:
            self.cursor.execute(f"INSERT INTO {table} (word_id, page_id, freq, positions) VALUES (?, ?, ?, ?)",
                                (word_id, page_id, 1, json.dumps([position])))

    def add_keyword_freq(self, page_id, word_id, freq):
        self.cursor.execute("INSERT OR IGNORE INTO keyword_freq (page_id, word_id, freq) VALUES (?, ?, ?)", (page_id, word_id, freq))

    def get_keyword_freqs(self, page_id, limit=10):
        self.cursor.execute("""
            SELECT word_id, freq FROM keyword_freq 
            WHERE page_id = ? 
            ORDER BY freq DESC 
            LIMIT ?
        """, (page_id, limit))
        return self.cursor.fetchall()

    def get_all_page_ids(self):
        self.cursor.execute("SELECT page_id FROM page WHERE title IS NOT NULL")
        return [row[0] for row in self.cursor.fetchall()]

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()