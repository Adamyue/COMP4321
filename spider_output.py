import sqlite3

def generate_spider_result():
    """Read data from spider.db and generate spider_result.txt file"""
    
    # Connect to database
    conn = sqlite3.connect('spider.db')
    cursor = conn.cursor()
    
    try:
        # Open output file
        with open('spider_result.txt', 'w', encoding='utf-8') as f:
            
            # Get all page information
            cursor.execute("""
                SELECT page_id, title, url, last_modified, size 
                FROM page 
                ORDER BY page_id
            """)
            
            pages = cursor.fetchall()
            
            for i, page in enumerate(pages):
                page_id, title, url, last_modified, size = page
                
                # Write separator (no newline before or after)
                if i > 0:
                    f.write("——————————————————————————————-\n")
                
                # Write page title
                f.write(f"{title if title else 'No Title'}\n")
                
                # Write URL
                f.write(f"{url}\n")
                
                # Write last modification date and page size
                f.write(f"{last_modified if last_modified else 'Unknown'}, {size if size else 0} bytes\n")
                
                # Get keyword frequencies (max 10)
                cursor.execute("""
                    SELECT w.word, kf.freq 
                    FROM keyword_freq kf 
                    JOIN word w ON kf.word_id = w.word_id 
                    WHERE kf.page_id = ? 
                    LIMIT 10
                """, (page_id,))
                
                keywords = cursor.fetchall()
                
                # Format keyword output
                if keywords:
                    keyword_str = "; ".join([f"{word} {freq}" for word, freq in keywords])
                    f.write(f"{keyword_str}\n")
                else:
                    f.write("No keywords\n")
                
                # Get child links (max 10)
                cursor.execute("""
                    SELECT p.url 
                    FROM link l 
                    JOIN page p ON l.child_id = p.page_id 
                    WHERE l.parent_id = ? 
                    LIMIT 10
                """, (page_id,))
                
                child_links = cursor.fetchall()
                
                # Write child links
                for link in child_links:
                    f.write(f"{link[0]}\n")
                
                # If no child links
                if not child_links:
                    f.write("No child links\n")
        
        print(f"Successfully generated spider_result.txt, processed {len(pages)} pages")
        
    except Exception as e:
        print(f"Error generating file: {e}")
        
    finally:
        # Close database connection
        conn.close()

if __name__ == "__main__":
    generate_spider_result()