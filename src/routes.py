"""
Routes: React app serving and episode search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
from flask import send_from_directory, request, jsonify
from emotions import evaluate

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

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
        return jsonify(emotion_query(text))

    # if USE_LLM:
    #    from llm_routes import register_chat_route
    #    register_chat_route(app, json_search)
