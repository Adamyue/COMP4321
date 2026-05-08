from flask import Flask, render_template, request
from search_engine import SearchEngine

app = Flask(__name__)
engine = SearchEngine()


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
                results = engine.search(query, title_boost=title_boost)
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
