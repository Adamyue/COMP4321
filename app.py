from flask import Flask, render_template, request
from search_engine import SearchEngine

app = Flask(__name__)
engine = SearchEngine()


@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    error = None

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            try:
                results = engine.search(query)
            except Exception as e:
                error = str(e)

    return render_template("index.html", results=results, query=query, error=error)


if __name__ == "__main__":
    app.run(debug=True)
