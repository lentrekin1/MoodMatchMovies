"""
Routes: React app serving and episode search API.

To enable AI-augmented search, set USE_LLM = True below.
Requires SPARK_API_KEY in .env.
"""
import json
import os
import re
import zipfile
import numpy as np
from collections import defaultdict
from pathlib import Path
from flask import send_from_directory, request, jsonify
from emotions import evaluate, EMOTION_LABELS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize as sk_normalize

# ── AI toggle ────────────────────────────────────────────────────────────────
# USE_LLM = False
USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

if USE_LLM:
    from infosci_spark_client import LLMClient

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
    _em_dim = None
    _sums = {}
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
                vec = np.array(r["emotions"], dtype=np.float32)
                if _em_dim is None:
                    _em_dim = len(vec)
                _sums.setdefault(norm_key, {}).setdefault(src, np.zeros(_em_dim, dtype=np.float32))
                _sums[norm_key][src] += vec
    for norm_key, src_vecs in _sums.items():
        meta = movie_meta.get(norm_key, {})
        display_title = meta.get("title", norm_key)
        for src, vec in src_vecs.items():
            # Use a composite key when a movie has reviews from multiple sources
            entry_key = f"{norm_key}___{src}"
            movies[entry_key] = (display_title, src, vec)

# Fall back to pre-computed emotions in final_movies.json when reviews.zip is absent
if not movies:
    _SOURCE_COUNTS = [
        ("letterboxd", "num_lb_reviews"),
        ("rottentomatoes", "num_rt_reviews"),
        ("imdb", "num_imdb_reviews"),
    ]
    for norm_key, meta in movie_meta.items():
        emo = meta.get("emotions")
        if not emo:
            continue
        src = max(_SOURCE_COUNTS, key=lambda sc: int(meta.get(sc[1]) or 0))[0]
        entry_key = f"{norm_key}___{src}"
        movies[entry_key] = (meta["title"], src, np.array(emo, dtype=np.float32))

# Preferred source per movie (for LSA results that aren't source-keyed)
_SOURCE_PRIORITY = ["letterboxd", "rottentomatoes", "imdb"]
_norm_key_to_source: dict = {}
for _entry_key, (_, _src, _) in movies.items():
    _nk = _entry_key.split("___")[0]
    if _nk not in _norm_key_to_source:
        _norm_key_to_source[_nk] = _src
    elif _SOURCE_PRIORITY.index(_src) < _SOURCE_PRIORITY.index(_norm_key_to_source[_nk]):
        _norm_key_to_source[_nk] = _src

# Build LSA model (TF-IDF + TruncatedSVD) from movie plot texts
_lsa_keys = list(movie_meta.keys())
_lsa_texts = [
    f"{movie_meta[k].get('title', '')} {movie_meta[k].get('plot', '')}".strip()
    for k in _lsa_keys
]
_tfidf = TfidfVectorizer(stop_words="english", max_features=5000)
_svd_model = TruncatedSVD(n_components=64, random_state=1)
_lsa_matrix_norm = sk_normalize(
    _svd_model.fit_transform(_tfidf.fit_transform(_lsa_texts))
)

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

def _title_match(norm_key: str, query_terms: set) -> float:
    """Fraction of query words found in the movie's normalized title."""
    if not query_terms:
        return 0.0
    title_words = set(_normalize(movie_meta.get(norm_key, {}).get("title", "")).split())
    return len(query_terms & title_words) / len(query_terms)

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

def _llm_augment_query(client, topic, emotion):
    if not emotion:
        messages = [
            {"role": "system", "content": (
                "You are augmenting a topic query for a movie search engine. "
                "If the query would benefit from related terms (e.g. adding 'gangster mob' to 'crime'), add them. "
                "If it's already good, return it unchanged. "
                "If it's garbage or a single character, return any reasonable topic. "
                "Return only the query string, nothing else."
            )},
            {"role": "user", "content": topic},
        ]
    elif not topic:
        messages = [
            {"role": "system", "content": (
                "You are augmenting an emotional mood query. The string will be fed to the GoEmotions model "
                "to produce a sentiment vector, so it should be a vivid prose sentence. "
                "If the user supplied a short phrase like 'sad movie', rewrite it as a full sentence like "
                "'My heart broke when I learned I only had a year to live.' "
                "If it's already a good sentence, return it unchanged. "
                "If it's garbage, return any emotional sentence. "
                "Return only the sentence, nothing else."
            )},
            {"role": "user", "content": emotion},
        ]
    else:
        messages = [
            {"role": "system", "content": (
                "You are augmenting two search queries for a movie search engine. "
                "First, a topic (e.g. 'crime') — expand with related terms if helpful, leave alone if fine. "
                "Second, an emotional mood sentence for GoEmotions — if it's a short phrase like 'sad movie', "
                "rewrite it as vivid prose; if it's already a good sentence, leave it alone. "
                "If either is garbage, substitute something reasonable. "
                "Return exactly two lines: the topic on line 1, the mood sentence on line 2. Nothing else."
            )},
            {"role": "user", "content": f"Topic: {topic}\nMood: {emotion}"},
        ]
    content = (client.chat(messages).get("content") or "").strip()
    if not emotion:
        return topic, content or emotion
    if not topic:
        return content or topic, emotion
    lines = content.split("\n", 1)
    return (lines[0].strip() or topic), (lines[1].strip() if len(lines) > 1 else emotion)


def _llm_rerank(client, results, original_topic, original_emotion):
    payload = json.dumps({
        "movies": [{"title": r["title"], "plot": r["plot"]} for r in results],
        "topic_query": original_topic,
        "emotion_query": original_emotion,
    })
    messages = [
        {"role": "system", "content": (
            "You evaluate movie search results. You will receive a JSON object with a list of movies "
            "(title + plot) and the user's original topic and emotion queries. "
            "For each movie decide if it is a reasonable match. Be generous — the dataset is small, "
            "so approve at least one result even if imperfect. "
            "Return a JSON array with one object per movie in the same order: "
            "{\"match\": true/false, \"reason\": \"one sentence why it fits (no spoilers)\"}. "
            "Return only valid JSON — no markdown, no code fences."
        )},
        {"role": "user", "content": payload},
    ]
    content = (client.chat(messages).get("content") or "").strip()
    try:
        evaluations = json.loads(content)
        filtered = []
        for r, ev in zip(results, evaluations):
            if ev.get("match"):
                r["reason"] = ev.get("reason", "")
                filtered.append(r)
        return filtered, True
    except Exception as e:
        print(f"LLM rerank parse error: {e}")
        return results, False


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
        text  = request.args.get("title", "").strip()   # emotion / mood query
        topic = request.args.get("topic", "").strip()   # SVD / topic query
        pool  = request.args.get("pool", "all")

        # ── LLM query augmentation ────────────────────────────────────────────
        llm_client = None
        original_topic, original_text = topic, text
        use_llm_req = request.args.get("use_llm", "true").lower() != "false"
        if USE_LLM and use_llm_req and (text or topic):
            api_key = os.getenv("SPARK_API_KEY")
            if api_key:
                try:
                    llm_client = LLMClient(api_key=api_key)
                    topic, text = _llm_augment_query(llm_client, topic, text)
                except Exception as e:
                    print(f"LLM augmentation failed: {e}")
                    llm_client = None
        # ─────────────────────────────────────────────────────────────────────

        source_filters = set(request.args.getlist("source"))
        genre_filters  = set(request.args.getlist("genre"))

        year_min    = request.args.get("yearMin",    type=int)
        year_max    = request.args.get("yearMax",    type=int)
        runtime_min = request.args.get("runtimeMin", type=int)
        runtime_max = request.args.get("runtimeMax", type=int)
        rt_min      = request.args.get("rtMin",      type=float)
        imdb_min    = request.args.get("imdbMin",    type=float)

        allowed_sources = {SOURCE_MAP.get(s, s) for s in source_filters} if source_filters else None

        raw_query_emotions = []  # list of {"label", "strength"} – populated when mood query present

        if text and topic:
            # ── Combined: emotion + LSA ──────────────────────────────────────
            query_terms = set(_normalize(topic).split())
            emotions  = emotion_query(text)
            raw_query_emotions = emotions
            e_cands   = cosine_search(emotions, top_k=200, pool=pool)
            e_map     = {(r["norm_key"], r["source"]): r["score"] for r in e_cands}

            q_vec  = _tfidf.transform([topic])
            q_norm = sk_normalize(_svd_model.transform(q_vec))
            raw    = (_lsa_matrix_norm @ q_norm.T).flatten()
            top200 = np.argsort(raw)[::-1][:200]
            l_map  = {_lsa_keys[i]: float(raw[i]) for i in top200}

            all_pairs: set = set(e_map.keys())
            for nk, lsa_src in ((k, _norm_key_to_source.get(k)) for k in l_map):
                if lsa_src:
                    all_pairs.add((nk, lsa_src))

            # Also include any title-matching movies not already in the candidate pool
            for nk, meta in movie_meta.items():
                if _title_match(nk, query_terms) > 0:
                    src = _norm_key_to_source.get(nk)
                    if src:
                        all_pairs.add((nk, src))

            candidates = sorted(
                [
                    {
                        "norm_key": nk,
                        "source":   src,
                        "score":    (
                            0.25 * e_map.get((nk, src), 0.0)
                            + 0.70 * l_map.get(nk, 0.0)
                            + 0.05 * _title_match(nk, query_terms)
                        ),
                        "title":    _format_title(movie_meta.get(nk, {}).get("title", nk)),
                    }
                    for nk, src in all_pairs
                ],
                key=lambda x: x["score"],
                reverse=True,
            )[:200]

        elif topic:
            # ── LSA only ─────────────────────────────────────────────────────
            query_terms = set(_normalize(topic).split())
            q_vec  = _tfidf.transform([topic])
            q_norm = sk_normalize(_svd_model.transform(q_vec))
            raw    = (_lsa_matrix_norm @ q_norm.T).flatten()
            lsa_scores = {_lsa_keys[i]: float(raw[i]) for i in range(len(_lsa_keys))}
            allowed_pool = POOL_SOURCES.get(pool, POOL_SOURCES["all"])

            # Score all movies (LSA + title match) so title hits aren't excluded
            scored = []
            for nk, lsa_score in lsa_scores.items():
                src = _norm_key_to_source.get(nk)
                if src is None or src not in allowed_pool:
                    continue
                score = 0.92 * lsa_score + 0.08 * _title_match(nk, query_terms)
                scored.append((nk, src, score))
            scored.sort(key=lambda x: x[2], reverse=True)

            candidates = [
                {
                    "norm_key": nk,
                    "source":   src,
                    "score":    score,
                    "title":    _format_title(movie_meta.get(nk, {}).get("title", nk)),
                }
                for nk, src, score in scored[:200]
            ]

        else:
            # ── Emotion only (original behaviour) ────────────────────────────
            emotions   = emotion_query(text)
            raw_query_emotions = emotions
            candidates = cosine_search(emotions, pool=pool)

        # Build normalised query emotion vector for the response
        query_emotions_out = []
        if raw_query_emotions is not None and len(raw_query_emotions):
            max_q = float(np.max(raw_query_emotions)) or 1.0
            query_emotions_out = [
                {"label": EMOTION_LABELS[i], "score": round(float(raw_query_emotions[i]) / max_q, 3)}
                for i in range(len(EMOTION_LABELS))
            ]

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

            raw_emo = meta.get("emotions") or []
            emotion_scores = []
            if raw_emo:
                max_val = max(raw_emo) or 1.0
                emotion_scores = [
                    {"label": EMOTION_LABELS[i], "score": round(raw_emo[i] / max_val, 3)}
                    for i in range(min(len(raw_emo), len(EMOTION_LABELS)))
                ]

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
                "plot":        meta.get("plot") or "",
                "director":    meta.get("director") or "",
                "actors":      meta.get("actors") or "",
                "emotions":    emotion_scores,
            })

        # ── LLM reranking ─────────────────────────────────────────────────────
        llm_success = None
        if llm_client and results:
            top10 = results[:10]
            reranked, llm_success = _llm_rerank(llm_client, top10, original_topic, original_text)
            results = reranked + results[10:]
        # ─────────────────────────────────────────────────────────────────────

        response = {"results": results, "queryEmotions": query_emotions_out}
        if llm_success is not None:
            response["llm_success"] = llm_success
        return jsonify(response)
