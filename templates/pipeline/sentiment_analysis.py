"""
Phase 5: Sentiment Analysis

Two models:
  - Sentiment: nlptown/bert-base-multilingual-uncased-sentiment (1-5 stars)
  - Emotion: j-hartmann/emotion-english-distilroberta-base (7 classes)

Uses MPS (Apple Silicon GPU) if available, falls back to CPU.

Input: saved_posts.json
Output: data/sentiment_scores.json
"""

import json
from pathlib import Path

import torch

# ============ CONFIGURATION ============
POSTS_PATH = Path("data/instagram/saved_posts.json")
OUTPUT_PATH = Path("data/sentiment_scores.json")
SENTIMENT_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"
EMOTION_MODEL = "j-hartmann/emotion-english-distilroberta-base"
BATCH_SIZE = 32
MAX_LENGTH = 512
# =======================================


def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_text(post):
    return (post.get("final_explainer", "") or post.get("text", "") or "")[:MAX_LENGTH]


def main():
    from transformers import pipeline

    device = get_device()
    print(f"Device: {device}")

    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)
    texts = [get_text(p) for p in posts]
    print(f"Posts: {len(posts)}")

    # Sentiment (1-5 stars)
    print(f"Loading sentiment model: {SENTIMENT_MODEL}")
    sent_pipe = pipeline("sentiment-analysis", model=SENTIMENT_MODEL,
                         device=device, truncation=True, max_length=MAX_LENGTH)

    print("Running sentiment...", flush=True)
    sent_results = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        batch = [t if t.strip() else "neutral" for t in batch]
        results = sent_pipe(batch)
        sent_results.extend(results)
        if (i // BATCH_SIZE) % 50 == 0:
            print(f"  {i}/{len(texts)}", flush=True)

    # Emotion (7 classes)
    print(f"Loading emotion model: {EMOTION_MODEL}")
    emo_pipe = pipeline("text-classification", model=EMOTION_MODEL,
                        device=device, truncation=True, max_length=MAX_LENGTH,
                        top_k=None)

    print("Running emotions...", flush=True)
    emo_results = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        batch = [t if t.strip() else "neutral" for t in batch]
        results = emo_pipe(batch)
        emo_results.extend(results)
        if (i // BATCH_SIZE) % 50 == 0:
            print(f"  {i}/{len(texts)}", flush=True)

    # Combine
    output = []
    for i, post in enumerate(posts):
        stars = int(sent_results[i]["label"].split()[0]) if i < len(sent_results) else 3
        score = sent_results[i].get("score", 0) if i < len(sent_results) else 0

        emotions = {}
        dominant = "neutral"
        if i < len(emo_results):
            for item in emo_results[i]:
                emotions[item["label"]] = round(item["score"], 4)
            dominant = max(emotions, key=emotions.get) if emotions else "neutral"

        output.append({
            "post_id": post["id"],
            "stars": stars,
            "sentiment_score": round(score, 4),
            "dominant_emotion": dominant,
            "emotions": emotions,
        })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {OUTPUT_PATH}")

    # Stats
    from collections import Counter
    star_dist = Counter(r["stars"] for r in output)
    emo_dist = Counter(r["dominant_emotion"] for r in output)
    print(f"Stars: {dict(sorted(star_dist.items()))}")
    print(f"Emotions: {dict(emo_dist.most_common())}")


if __name__ == "__main__":
    main()
