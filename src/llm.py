"""
LLM chat route — only loaded when USE_LLM = True in routes.py.
Adds a POST /api/chat endpoint that performs LLM-driven RAG.

Setup:
  1. Add SPARK_API_KEY=your_key to .env
  2. Set USE_LLM = True in routes.py
"""
import json
import os
from infosci_spark_client import LLMClient
from search import movie_search_
from flask import jsonify

def llm_augment_query(client, user_field_inputs):
    if user_field_inputs["emotion"] == "":
        messages = [
            {
                "role": "system",
                "content": (
                    "You are tasked with augmenting the following user query for search over a movie database. "
                    "The query will be for topics or genres of film, such as \"crime\" or \"sci-fi\". "
                    "Read the query. If it would benefit from adding terms, e.g., adding \"gangster\" or \"mob\" to \"crime\", "
                    "then you should return just a query with those terms added. If the query is already fine, simply return it unmodified. "
                    "If the query is incomplete or garbage, such as a single character, return a query for any topic you like. "
                )
            },
            {"role": "user", "content": user_field_inputs["topic"]}
        ]
    elif user_field_inputs["topic"] == "":
        messages = [
            {
                "role": "system",
                "content": (
                    "You are tasked with augmenting the following user query. The query string is meant to be a plain-text "
                    "sentence which capture some emotional mood; the sentence will be processed with the GoEmotions model to "
                    "produce a sentiment vector. Although users are asked to put in a full sentence, some users may be confused "
                    "and simply supply a word or phrase such as \"sad movie\". If this is the case, your task is to craft a prose "
                    "sentence which captures the intended emotion and eliminates terms like \"movie\" which are not relevant. "
                    "For example, you could turn \"sad movie\" into \"My heart broke when I learned I only had a year to live.\" "
                    "If the original user query was adequate, return just the query. If not, return just your newly crafted sentence. "
                    "If the query is incomplete or garbage, such as a single character, return a sentence representing any emotion of your choice. "
                )
            },
            {"role": "user", "content": user_field_inputs["emotion"]}
        ]
    else:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are tasked with augmenting the following user queries for search over a movie database. "
                    "The query has two parts: a topic, and an intended emotion. The topic will be for topics or genres "
                    "of film, such as \"crime\" or \"sci-fi\". If this part would benefit from adding terms, e.g., "
                    "adding \"gangster\" or \"mob\" to \"crime\", then add those terms. If the query is already fine, do not change it. "
                    "The second part is a plain-text sentence which capture some emotional mood; the sentence will be processed "
                    "with GoEmotions to produce a sentiment vector. Although users are asked to put in a full sentence, some users may be confused "
                    "and simply supply a word or phrase such as \"sad movie\". If this is the case, your task is to craft a prose "
                    "sentence which captures the intended emotion and eliminates terms like \"movie\" which are not relevant. "
                    "For example, you could turn \"sad movie\" into \"My heart broke when I learned I only had a year to live.\" "
                    "If the original user query was adequate, do not change it. If either query is incomplete or garbage, "
                    "such as a single character, choose any topic or emotion of your choice to craft a query from. "
                    "Return exactly the following: the original or augmented topic query on one line, and the original or augmented emotion "
                    "query on the next."
                ),
            },
            {"role": "user", "content": f"Topic: {user_field_inputs['topic']}\nEmotion:{user_field_inputs['emotion']}"},
        ]
    response = client.chat(messages)
    content = (response.get("content") or "").strip()
    if user_field_inputs["emotion"] == "":
        return {"emotion": "", "topic": content}
    elif user_field_inputs["topic"] == "":
        return {"topic": "", "emotion": content}
    else:
        t = content.split("\n")[0]
        e = content.split("\n")[1]
        return {"emotion": e, "topic": t}

def llm_search(request, films):
    emotion  = request.args.get("title", "").strip()   # emotion / mood query
    topic = request.args.get("topic", "").strip()   # SVD / topic query

    api_key = os.getenv("SPARK_API_KEY")
    if not api_key:
        print("No SPARK_API_KEY")
        return []

    client = LLMClient(api_key=api_key)
    augmented_query = llm_augment_query(client, {"topic": topic, "emotion": emotion})

    ir_response = movie_search_(films, augmented_query["topic"], augmented_query["emotion"], request, True)
    ir_response["augmented_emotion_query"] = augmented_query["emotion"]
    ir_response["augmented_topic_query"] = augmented_query["topic"]

    titles_and_plots = [{"title": ir["title"], "plot": ir["plot"]} for ir in ir_response["results"]]
    movies = json.dumps({"movies": titles_and_plots, "user_emotion_query": emotion, "user_topic_query": topic})

    messages = [
        {
            "role": "system",
            "content": (
                "You are responsible for evaluating the results of an information retrieval search over a movie database. "
                "Users search by both topic and by the emotion a film should create; the latter represented in the form of a prose sentence. "
                "You will now view, in JSON form, a list of the top 10 films matching the user query and their plot summaries, as well as the original user query. "
                "Either the emotion or topic may be blank. Your task is the following: for each of the 10 films returned, determine if it is an "
                "adequate match to the user query. Your response should be exactly the following: a JSON array of 10 entries, one "
                "for each film, with each entry having the following structure: {\"match\": ..., \"reason\": ...}, where match is a boolean value "
                "indicating whether the film matches the user query and \"reason\" is a string explaining (without spoiling the film) why you believe "
                "the film is a good match. You can be somewhat generous with what is considered a match, as the data set is relatively small "
                "and user queries may be difficult to fulfill. Try to approve at least one film; even if you think it is not a good match, users "
                "should see what the closest film to their query is. Make sure that your response is a *valid json string object* which can be parsed: not, "
                "for example, a code block beginning with ```json. Syntax highlighting is not desired; this response will be directly parsed "
                "with json.loads in Python."
            )
        },
        {
            "role": "user",
            "content": movies
        }
    ]

    response = client.chat(messages)
    content = (response.get("content") or "").strip()
    try:
        res = json.loads(content)
        matches = []
        for i, entry in enumerate(res):
            if entry["match"]:
                original_entry = ir_response["results"][i]
                original_entry["reason"] = entry["reason"]
                matches.append(original_entry)
        ir_response["llm_success"] = True
        ir_response["results"] = matches
    except Exception as e: # Malformatted json
        print(f"Exception Type: {type(e).__name__}, Message: {e}")
        ir_response["llm_success"] = False
        
    return jsonify(ir_response)
