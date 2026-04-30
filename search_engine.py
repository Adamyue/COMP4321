import sqlite3
import math
import json
import re
from stop_stem import StopStem
from collections import defaultdict

class SearchEngine:
    def __init__(self, db_name="spider.db", stopwords_file="stopwords.txt"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.stop_stem = StopStem(stopwords_file)
        
        # Precompute total number of pages for IDF
        self.cursor.execute("SELECT COUNT(*) FROM page WHERE title IS NOT NULL")
        self.total_docs = self.cursor.fetchone()[0]

    def parse_query(self, query):
        """Extracts exact phrases (in quotes) and individual keywords."""
        phrases = re.findall(r'"([^"]*)"', query)
        # Remove the phrases from the query to get individual terms
        remainder = re.sub(r'"([^"]*)"', " ", query)
        
        # Tokenize and stem terms
        free_terms = self._tokenize(remainder)
        
        # Tokenize and stem phrases
        stemmed_phrases = []
        for phrase in phrases:
            ptokens = self._tokenize(phrase)
            if len(ptokens) > 0:
                stemmed_phrases.append(ptokens)
                
        return free_terms, stemmed_phrases

    def _tokenize(self, text):
        tokens = re.findall(r"[a-zA-Z]+", text.lower())
        result = []
        for token in tokens:
            if not self.stop_stem.is_stop_word(token):
                result.append(self.stop_stem.stem(token))
        return result

    def get_document_max_tf(self, page_id):
        """Gets max(tf) for a given document for the tf/max(tf) formula."""
        self.cursor.execute("SELECT MAX(freq) FROM posting_body WHERE page_id = ?", (page_id,))
        res = self.cursor.fetchone()
        return res[0] if res and res[0] else 1

    def get_idf(self, word_id):
        """Calculates IDF = log2(N / df) for a given word."""
        if self.total_docs == 0:
            return 0
        self.cursor.execute("SELECT COUNT(DISTINCT page_id) FROM posting_body WHERE word_id = ?", (word_id,))
        df = self.cursor.fetchone()[0]
        if df == 0:
            return 0
        return math.log2(self.total_docs / df)

    def check_phrase_in_doc(self, page_id, phrase_tokens, table="posting_body"):
        """Checks if a sequence of tokens appears adjacently in a document's body or title."""
        if not phrase_tokens:
            return False
            
        word_ids = []
        for token in phrase_tokens:
            self.cursor.execute("SELECT word_id FROM word WHERE word = ?", (token,))
            res = self.cursor.fetchone()
            if not res:
                return False  # Phrase contains a word not in DB
            word_ids.append(res[0])
            
        # Get positions for all words in the document
        positions_list = []
        for wid in word_ids:
            self.cursor.execute(f"SELECT positions FROM {table} WHERE word_id = ? AND page_id = ?", (wid, page_id))
            res = self.cursor.fetchone()
            if not res:
                return False
            positions_list.append(json.loads(res[0]))
            
        # Check if they are sequential
        # positions_list is a list of lists. E.g., [[2, 10], [3, 20]]
        first_word_pos = positions_list[0]
        for pos in first_word_pos:
            valid = True
            for i in range(1, len(word_ids)):
                if (pos + i) not in positions_list[i]:
                    valid = False
                    break
            if valid:
                return True
                
        return False

    def search(self, query):
        """
        Executes a search query and returns the top 50 ranked documents.
        Ranking uses Cosine Similarity with TF-IDF: tf * idf / max(tf).
        """
        free_terms, phrases = self.parse_query(query)
        
        # Extract all unique query tokens (free terms + tokens inside phrases)
        all_query_tokens = list(free_terms)
        for p in phrases:
            all_query_tokens.extend(p)
            
        if not all_query_tokens:
            return []
            
        # Count query term frequencies
        query_tfs = defaultdict(int)
        for token in all_query_tokens:
            query_tfs[token] += 1
            
        query_max_tf = max(query_tfs.values()) if query_tfs else 1
        
        # Compute Query Vector
        query_vector = {}
        for token, tf in query_tfs.items():
            self.cursor.execute("SELECT word_id FROM word WHERE word = ?", (token,))
            res = self.cursor.fetchone()
            if res:
                word_id = res[0]
                idf = self.get_idf(word_id)
                # tf/max(tf) * idf
                weight = (tf / query_max_tf) * idf
                query_vector[word_id] = weight
                
        if not query_vector:
            return [] # No words found in the database
            
        # Find candidate documents (documents containing at least one query term)
        candidate_docs = set()
        for word_id in query_vector.keys():
            self.cursor.execute("SELECT page_id FROM posting_body WHERE word_id = ?", (word_id,))
            for row in self.cursor.fetchall():
                candidate_docs.add(row[0])
            self.cursor.execute("SELECT page_id FROM posting_title WHERE word_id = ?", (word_id,))
            for row in self.cursor.fetchall():
                candidate_docs.add(row[0])

        # Filter out candidate docs that do NOT contain the exact phrases required
        valid_docs = []
        for page_id in candidate_docs:
            has_all_phrases = True
            for phrase in phrases:
                in_body = self.check_phrase_in_doc(page_id, phrase, "posting_body")
                in_title = self.check_phrase_in_doc(page_id, phrase, "posting_title")
                if not (in_body or in_title):
                    has_all_phrases = False
                    break
            if has_all_phrases:
                valid_docs.append(page_id)
                
        # Compute Document Vectors and Cosine Similarity
        scores = []
        for page_id in valid_docs:
            doc_max_tf = self.get_document_max_tf(page_id)
            
            dot_product = 0.0
            doc_vector_sq_sum = 0.0
            
            # Note: For exact cosine similarity, |D| should consider all terms in the document.
            # To avoid huge overhead, we can approximate |D| or calculate it precisely.
            # For this project, we calculate the magnitude only on query terms, or fetch all terms for the document.
            # We'll calculate the true document length using all its terms to be accurate.
            self.cursor.execute("SELECT word_id, freq FROM posting_body WHERE page_id = ?", (page_id,))
            doc_terms = self.cursor.fetchall()
            
            doc_weights = {}
            for wid, freq in doc_terms:
                idf = self.get_idf(wid)
                w = (freq / doc_max_tf) * idf
                doc_weights[wid] = w
                doc_vector_sq_sum += w * w
                
            for word_id, q_weight in query_vector.items():
                d_weight = doc_weights.get(word_id, 0.0)
                dot_product += q_weight * d_weight
                
            query_vector_sq_sum = sum(w * w for w in query_vector.values())
            
            if doc_vector_sq_sum == 0 or query_vector_sq_sum == 0:
                continue
                
            similarity = dot_product / (math.sqrt(query_vector_sq_sum) * math.sqrt(doc_vector_sq_sum))
            
            # Title Boost
            title_boost = 1.0
            for word_id in query_vector.keys():
                self.cursor.execute("SELECT 1 FROM posting_title WHERE word_id = ? AND page_id = ?", (word_id, page_id))
                if self.cursor.fetchone():
                    # Massive boost if the term appears in the title
                    title_boost += 0.5 
                    
            final_score = similarity * title_boost
            scores.append((final_score, page_id))
            
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        top_50 = scores[:50]
        
        # Prepare Result metadata exactly as required by Role 3 Web Frontend
        results = []
        for score, page_id in top_50:
            self.cursor.execute("SELECT url, title, last_modified, size FROM page WHERE page_id = ?", (page_id,))
            url, title, last_modified, size = self.cursor.fetchone()
            
            # Top 5 keywords
            self.cursor.execute("""
                SELECT w.word, kf.freq 
                FROM keyword_freq kf 
                JOIN word w ON kf.word_id = w.word_id 
                WHERE kf.page_id = ? 
                ORDER BY kf.freq DESC LIMIT 5
            """, (page_id,))
            keywords = [{"word": row[0], "freq": row[1]} for row in self.cursor.fetchall()]
            
            # Child links
            self.cursor.execute("""
                SELECT p.url FROM link l
                JOIN page p ON l.child_id = p.page_id
                WHERE l.parent_id = ?
            """, (page_id,))
            child_links = [row[0] for row in self.cursor.fetchall()]
            
            # Parent links
            self.cursor.execute("""
                SELECT p.url FROM link l
                JOIN page p ON l.parent_id = p.page_id
                WHERE l.child_id = ?
            """, (page_id,))
            parent_links = [row[0] for row in self.cursor.fetchall()]
            
            results.append({
                "score": round(score, 4),
                "title": title if title else "No Title",
                "url": url,
                "last_modified": last_modified if last_modified else "Unknown",
                "size": size if size else 0,
                "keywords": keywords,
                "parent_links": parent_links,
                "child_links": child_links
            })
            
        return results

if __name__ == "__main__":
    # Quick test
    engine = SearchEngine()
    query = 'information "hong kong"'
    print(f"Testing Query: {query}")
    res = engine.search(query)
    for i, doc in enumerate(res[:5]):
        print(f"[{i+1}] Score: {doc['score']} | {doc['title']} | {doc['url']}")
