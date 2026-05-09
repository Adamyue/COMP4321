from flask import Flask, render_template, request
from search_engine import SearchEngine

app = Flask(__name__)
engine = SearchEngine()


def print_station2_inspection(query, inspection):
    print("\n=== Station 2 Inspection ===")
    print(f"Query: {query}")
    print(f"Raw tokens: {inspection['raw_tokens'] or 'none'}")
    print(f"Search terms after stop-word removal/stemming: {inspection['free_terms'] or 'none'}")

    print("\nToken lookup:")
    for item in inspection["token_details"]:
        stem = item["stem"] if item["stem"] else "-"
        word_id = item["word_id"] if item["word_id"] else "-"
        stop_word = "yes" if item["stop_word"] else "no"
        print(
            f"  token={item['token']}, stop_word={stop_word}, stem={stem}, "
            f"word_id={word_id}, body_docs={item['body_docs']}, "
            f"title_docs={item['title_docs']}"
        )

    print(f"\nCandidate documents before phrase filtering: {inspection['candidate_doc_count']}")
    print(f"Valid documents after phrase filtering: {inspection['valid_doc_count']}")
    print(f"Title weight: {inspection['title_weight']}")

    if inspection["phrases"]:
        print("\nPhrase checks:")
        for phrase_info in inspection["phrase_matches"]:
            print(f"  phrase=\"{phrase_info['phrase']}\"")
            if not phrase_info["matched_pages"]:
                print("    no phrase match found in inspected candidates")
            for page in phrase_info["matched_pages"]:
                print(f"    {page['location']} match: {page['title']} | {page['url']}")

    print("============================\n")


@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    error = None
    title_boost = True

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        title_boost = request.form.get("title_boost") == "on"
        if query:
            try:
                inspection = engine.explain_query(query)
                print_station2_inspection(query, inspection)
                results = engine.search(query)
            except Exception as e:
                error = str(e)

    return render_template(
        "index.html",
        results=results,
        query=query,
        error=error,
        title_boost=title_boost,
    )


if __name__ == "__main__":
    app.run(debug=True)
