from tokenizers import Tokenizer
import onnxruntime as ort
import numpy as np
from huggingface_hub import hf_hub_download

model_path = hf_hub_download(
    repo_id="SamLowe/roberta-base-go_emotions-onnx",
    filename="onnx/model_quantized.onnx",
    cache_dir="./models"
)

tokenizer_path = hf_hub_download(
    repo_id="SamLowe/roberta-base-go_emotions-onnx",
    filename="onnx/tokenizer.json",
    cache_dir="./models"
)

tokenizer = Tokenizer.from_file(tokenizer_path)

opts = ort.SessionOptions()
opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

session = ort.InferenceSession(
    model_path,
    sess_options=opts,
    providers=["CPUExecutionProvider"]
)

labels = ['admiration', 'amusement', 'anger', 'annoyance', 'approval', 'caring', 'confusion', 'curiosity', 'desire', 'disappointment', 'disapproval', 'disgust', 'embarrassment', 'excitement', 'fear', 'gratitude', 'grief', 'joy', 'love', 'nervousness', 'optimism', 'pride', 'realization', 'relief', 'remorse', 'sadness', 'surprise', 'neutral']

def evaluate(text):
    enc = tokenizer.encode(text)
    inputs = {
        "input_ids": np.array([enc.ids], dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
    }
    outputs = session.run(None, inputs)[0]
    def sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))
    scores = sigmoid(outputs)
    res = [{"strength": float(scores[0][i]), "label": labels[i]} for i in range(len(scores[0]))]
    return res
