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

EMOTION_LABELS = [
    'amusement', 'anger', 'caring',
    'confusion', 'curiosity', 'desire', 'disgust',
    'embarrassment', 'excitement', 'fear', 'gratitude', 'grief', 'joy', 'love',
    'nervousness', 'optimism', 'pride', 'realization', 'remorse',
    'sadness', 'surprise'
]

prunes = [0, 3, 4, 9, 10, 23, 27]

# Remove the unused labels, e.g., 'neutral', from the transformer response
def prune_np_vector(vec, inds):
    return np.array([el for ind, el in enumerate(vec.tolist()) if not ind in inds])

# Take a text string and return a normalized numpy array of length 21 representing the emotions of the text
def evaluate(text):
    enc = tokenizer.encode(text)
    inputs = {
        "input_ids": np.array([enc.ids], dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
    }
    outputs = session.run(None, inputs)[0][0]
    def sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))
    scores = prune_np_vector(sigmoid(outputs), prunes)
    sn = np.linalg.norm(scores)
    scores = scores / sn
    return scores
