import numpy as np
from flask import jsonify
from emotions import evaluate, EMOTION_LABELS
from svd import svd_search
import json
import os

# Format the lowercased title of a film
def _format_title(raw_title):
    ignored_words = {'the', 'and', 'a', 'of', 'in', 'at', 'to', 'by', 'for', 'an', 'on'}
    words = raw_title.split()
    out = []
    for i, word in enumerate(words):
        if i == 0 or word not in ignored_words:
            out.append(word.capitalize())
        else:
            out.append(word)
    return ' '.join(out)

# Perform a cosine search over all films. 'em' is True if searching the emotion embeddings and False if searching the svd embeddings.
# query_vec must be a PRE-NORMALIZED numpy array of length 21
def cosine_search(films, em, query_vec, top_k=200):    
    results = []
    for tconst, film in films.items():
        if em:
            film_vec = film["emotions"]
        else:
            film_vec = film["svd_embedding"]
        d = np.dot(query_vec, film_vec)
        results.append({
            "title": _format_title(film["title"]),
            "tconst": tconst,
            "score": d
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return {x["tconst"]: (x["title"], x["score"]) for x in results[:top_k]}

# Safety wrapper around the emotions model to catch empty strings
def emotion_query(query_text):
    if query_text.strip() == "":
        query_text = "A terrifying nightmare that leaves you shaking."
    return evaluate(query_text)

# Search the reviews for a film by emotion and svd vectors
def reviews_search(tconst, em, svd, data_dir, rel_weight=0.5):
    with open(os.path.join(data_dir, 'reviews', tconst + ".json"), "r", encoding="utf-8") as f:
        reviews = json.load(f)
    results = []
    if em is not None and svd is not None:
        results = [(r["t"], rel_weight * np.dot(em, r["v"]) + (1 - rel_weight) * np.dot(svd, r["svd"])) for r in reviews]
    elif em is not None:
        results = [(r["t"], np.dot(em, r["v"])) for r in reviews]
    else:
        results = [(r["t"], np.dot(svd, r["v"])) for r in reviews]
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:10]

# Search the films using a text, topic, and filters. Films should be a dictionary keyed by tconst.
def movie_search_(films, request, data_dir):
    text  = request.args.get("title", "").strip()   # emotion / mood query
    topic = request.args.get("topic", "").strip()   # SVD / topic query

    genre_filters  = set(request.args.getlist("genre"))
    year_min    = request.args.get("yearMin",    type=int)
    year_max    = request.args.get("yearMax",    type=int)
    runtime_min = request.args.get("runtimeMin", type=int)
    runtime_max = request.args.get("runtimeMax", type=int)
    rt_min      = request.args.get("rtMin",      type=float)
    imdb_min    = request.args.get("imdbMin",    type=float)

    emotions = emotion_query(text) if text else None
    q_emb = svd_search(topic) if topic else None

    if text and topic:
        # ── Combined: emotion + LSA ──────────────────────────────────────
        e_cands   = cosine_search(films, True, emotions, top_k=200)

        svd_cands = cosine_search(films, False, q_emb, top_k=200)

        union_keys = set(e_cands.keys()).union(set(svd_cands.keys()))
        
        def combine_scores(em_score, svd_score, rel_weight=0.5):
            return rel_weight * em_score + (1 - rel_weight) * svd_score
        
        combined = []
        for key in union_keys:
            e_score = e_cands[key][1] if key in e_cands else 0
            svd_score = svd_cands[key][1] if key in svd_cands else 0
            title = e_cands[key][0] if key in e_cands else svd_cands[key][0]
            combined.append((key,title, combine_scores(e_score, svd_score)))

        combined.sort(key=lambda x: x[2], reverse=True)
        candidates = {x[0]: (x[1], x[2]) for x in combined}

    elif topic:
        # ── LSA only ─────────────────────────────────────────────────────
        candidates = cosine_search(films, False, q_emb, top_k=200)

    else:
        # ── Emotion only (original behaviour) ────────────────────────────
        candidates = cosine_search(films, True, emotions)

    # Label the emotion vector for the response
    query_emotions_out = []
    if text:
        query_emotions_out = [{"label": EMOTION_LABELS[i], "score": e} for i, e in enumerate(emotions)]

    query_svd_out = []
    if topic:
        query_svd_out = q_emb.tolist()

    results = []
    for r_tconst, r in candidates.items():
        genres  = films[r_tconst]["genres"]
        runtime = films[r_tconst]["runtime"]
        year    = films[r_tconst]["year"]
        imdb    = films[r_tconst]["imdb_avg"]
        rt      = films[r_tconst]["tomatometer"]

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

        raw_emo = films[r_tconst]["emotions"]
        emotion_scores = [{"label": EMOTION_LABELS[i], "score": e} for i, e in enumerate(raw_emo)]
        
        top_matching_reviews = reviews_search(r_tconst, emotions, q_emb, data_dir)

        results.append({
            "title":       r[0],
            "source":      "imdb",
            "score":       r[1],
            "tconst":      r_tconst,
            "genre":       genres,
            "runtime":     runtime,
            "imdbScore":   imdb,
            "rtScore":     rt,
            "releaseYear": year,
            "plot":        films[r_tconst]["plot"],
            "director":    films[r_tconst]["director"],
            "actors":      films[r_tconst]["actors"],
            "emotions":    emotion_scores,
            "reviews":     top_matching_reviews
        })

        if len(results) == 10:
            break

    return jsonify({"results": results, "queryEmotions": query_emotions_out, "query_svd_out": query_svd_out})