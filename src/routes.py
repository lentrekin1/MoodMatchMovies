"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
import re
import numpy as np
from pathlib import Path
from flask import send_from_directory, request, jsonify
from emotions import evaluate

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"

def _normalize(title):
    t = title.lower().replace("-", " ")
    return re.sub(r'\s+\d{4}$', '', t).strip()

movies = {}  # normalized_key -> (display_title, source, vector)
for fname, source in [
    ("imdb_summed_vectors.json", "imdb"),
    ("rt_summed_vectors.json", "rottentomatoes"),
    ("letterboxd_250_summed_vectors.json", "letterboxd"),
]:
    path = DATA_DIR / fname
    if path.exists():
        data = json.loads(path.read_text())
        for title, vec in data.items():
            movies[_normalize(title)] = (title, source, np.array(vec, dtype=np.float32))

POOL_SOURCES = {
    "all": {"imdb", "rottentomatoes", "letterboxd"},
    "top1000": {"rottentomatoes", "letterboxd"},
    "top250": {"letterboxd"},
}

def cosine_search(query_vec, top_k=10, pool="all"):
    q = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    allowed = POOL_SOURCES.get(pool, POOL_SOURCES["all"])
    results = []
    for title, source, vec in movies.values():
        if source not in allowed:
            continue
        score = float(np.dot(q, vec) / (q_norm * np.linalg.norm(vec) + 1e-9))
        if source == "letterboxd":            
            title_words = title.split('-')
        else:
            title_words = title.split(' ')
        ignored_words = ['the', 'and', 'a', 'of', 'in', 'at', 'to', 'by', 'for', 'an', 'on']
        new_title = []
        for i, word in enumerate(title_words):
            if i == len(title_words) - 1 and word.isdigit():
                new_title.append('(' + word + ')')
            elif i == 0 or word not in ignored_words:
                new_title.append(word.capitalize())
            else:
                new_title.append(word)
        title = ' '.join(new_title)
        results.append({"title": title, "source": source, "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def emotion_query(query):
    if not query or not query.strip():
        query = "A terrifying nightmare that leaves you shivering."
    return evaluate(text=query)

def register_routes(app):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route("/api/config")
    def config():
        return jsonify({"use_llm": USE_LLM})

    @app.route("/api/movies")
    def movie_search():
        text = request.args.get("title", "")
        pool = request.args.get("pool", "all")
        emotions = emotion_query(text)
        query_vec = [e["strength"] for e in emotions]
        return jsonify(cosine_search(query_vec, pool=pool))

    # if USE_LLM:
    #    from llm_routes import register_chat_route
    #    register_chat_route(app, json_search)
