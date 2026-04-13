"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
import re
import zipfile
import numpy as np
from collections import defaultdict
from pathlib import Path
from flask import send_from_directory, request, jsonify
from emotions import evaluate

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR   = Path(__file__).parent / "data"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

def _normalize(title):
    t = title.lower().replace("-", " ")
    return re.sub(r'\s+\d{4}$', '', t).strip()

# service number → source name
SERVICE_SOURCE = {1: "rottentomatoes", 2: "letterboxd", 3: "imdb"}

# Load metadata for enrichment and filtering
movie_meta = {}  # normalized_key -> metadata dict
tconst_to_key = {}  # tconst -> normalized_key
meta_path = DATA_DIR / "final_movies.json"
if meta_path.exists():
    for film in json.loads(meta_path.read_text()):
        key = _normalize(film["title"])
        movie_meta[key] = film
        tconst_to_key[film["tconst"]] = key

# Build summed emotion vectors from reviews.zip
# Structure: normalized_key -> {source -> summed np.array}
movies = {}  # normalized_key -> (display_title, source, summed_vector)
reviews_zip = ASSETS_DIR / "reviews.zip"
if reviews_zip.exists():
    _sums = defaultdict(lambda: defaultdict(lambda: np.zeros(28, dtype=np.float32)))
    with zipfile.ZipFile(reviews_zip) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            tconst = Path(name).stem
            norm_key = tconst_to_key.get(tconst)
            if norm_key is None:
                continue
            with zf.open(name) as f:
                reviews = json.load(f)
            for r in reviews:
                src = SERVICE_SOURCE.get(r["service"])
                if src is None:
                    continue
                _sums[norm_key][src] += np.array(r["emotions"], dtype=np.float32)
    for norm_key, src_vecs in _sums.items():
        meta = movie_meta.get(norm_key, {})
        display_title = meta.get("title", norm_key)
        for src, vec in src_vecs.items():
            # Use a composite key when a movie has reviews from multiple sources
            entry_key = f"{norm_key}___{src}"
            movies[entry_key] = (display_title, src, vec)

POOL_SOURCES = {
    "all": {"imdb", "rottentomatoes", "letterboxd"},
    "top1000": {"rottentomatoes", "letterboxd"},
    "top250": {"letterboxd"},
}

SOURCE_MAP = {"rt": "rottentomatoes", "imdb": "imdb", "letterboxd": "letterboxd"}

def _format_title(raw_title):
    ignored_words = {'the', 'and', 'a', 'of', 'in', 'at', 'to', 'by', 'for', 'an', 'on'}
    words = raw_title.split()
    out = []
    for i, word in enumerate(words):
        if i == len(words) - 1 and word.isdigit():
            out.append('(' + word + ')')
        elif i == 0 or word not in ignored_words:
            out.append(word.capitalize())
        else:
            out.append(word)
    return ' '.join(out)

def cosine_search(query_vec, top_k=200, pool="all"):
    q = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    allowed = POOL_SOURCES.get(pool, POOL_SOURCES["all"])
    results = []
    for entry_key, (display_title, source, vec) in movies.items():
        if source not in allowed:
            continue
        norm_key = entry_key.split("___")[0]
        score = float(np.dot(q, vec) / (q_norm * np.linalg.norm(vec) + 1e-9))
        results.append({
            "title": _format_title(display_title),
            "source": source,
            "score": score,
            "norm_key": norm_key,
        })
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

    @app.route("/api/poster/<tconst>")
    def poster(tconst):
        poster_dir = str(ASSETS_DIR / "posters")
        return send_from_directory(poster_dir, f"{tconst}.jpg")

    @app.route("/api/movies")
    def movie_search():
        text = request.args.get("title", "")
        pool = request.args.get("pool", "all")

        source_filters = set(request.args.getlist("source"))
        genre_filters  = set(request.args.getlist("genre"))

        year_min    = request.args.get("yearMin",    type=int)
        year_max    = request.args.get("yearMax",    type=int)
        runtime_min = request.args.get("runtimeMin", type=int)
        runtime_max = request.args.get("runtimeMax", type=int)
        rt_min      = request.args.get("rtMin",      type=float)
        imdb_min    = request.args.get("imdbMin",    type=float)

        allowed_sources = {SOURCE_MAP.get(s, s) for s in source_filters} if source_filters else None

        emotions = emotion_query(text)
        query_vec = [e["strength"] for e in emotions]
        candidates = cosine_search(query_vec, pool=pool)

        results = []
        for r in candidates:
            if allowed_sources and r["source"] not in allowed_sources:
                continue

            meta = movie_meta.get(r["norm_key"])
            if meta is None:
                continue

            genres  = meta.get("genres", "")
            runtime = int(meta.get("runtime") or 0)
            year    = int(meta.get("year") or 0)
            imdb    = meta.get("imdb_avg")
            rt      = meta.get("tomatometer")

            if genre_filters and not any(g.lower() in genres.lower() for g in genre_filters):
                continue
            if year_min is not None and year < year_min:
                continue
            if year_max is not None and year > year_max:
                continue
            if runtime_min is not None and runtime < runtime_min:
                continue
            if runtime_max is not None and runtime > runtime_max:
                continue
            if imdb_min is not None and (imdb is None or imdb < imdb_min):
                continue
            if rt_min is not None and (rt is None or rt < rt_min):
                continue

            results.append({
                "title":       r["title"],
                "source":      r["source"],
                "score":       r["score"],
                "tconst":      meta.get("tconst", ""),
                "genre":       genres,
                "runtime":     runtime,
                "imdbScore":   imdb,
                "rtScore":     rt,
                "releaseYear": year,
            })

            if len(results) == 10:
                break

        return jsonify(results)

    # if USE_LLM:
    #    from llm_routes import register_chat_route
    #    register_chat_route(app, json_search)
