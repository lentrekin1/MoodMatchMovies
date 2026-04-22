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
from flask import send_from_directory, request, jsonify
from search import movie_search_

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

current_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_directory)
data_dir = os.path.join(project_root, 'src', 'data')
assets_dir = os.path.join(project_root, 'assets')

# service number → source name
SERVICE_SOURCE = {0: "imdb", 1: "letterboxd", 2: "rt"}

films = {}
films_path = os.path.join(data_dir, "final_movies.json")
if os.path.exists(films_path):
    with open(films_path, "r", encoding="utf-8") as f:
        films_arr = json.load(f)
        films = {film["tconst"]: film for film in films_arr}

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
        poster_dir = os.path.join(assets_dir, 'posters')
        return send_from_directory(poster_dir, f"{tconst}.jpg")

    @app.route("/api/movies")
    def movie_search():
        return movie_search_(films, request, data_dir)
    
    # if USE_LLM:
    #    from llm_routes import register_chat_route
    #    register_chat_route(app, json_search)
