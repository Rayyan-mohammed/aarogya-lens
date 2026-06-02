"""
BharatHealth Analyst — ChromaDB Vector Index Builder
Embeds 706 district summaries using sentence-transformers (no API key needed).
"""

import json
import os
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
VECTOR_DIR = ROOT / "backend" / "vector_store" / "chroma_db"
SUMMARIES_PATH = DATA_DIR / "district_summaries.json"

VECTOR_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, free, good quality — 384 dims


def build_index():
    print("Loading district summaries...")
    with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
        summaries = json.load(f)
    print(f"  Loaded {len(summaries)} district summaries")

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Initialising ChromaDB...")
    client = chromadb.PersistentClient(path=str(VECTOR_DIR))

    # Drop and recreate collection for clean build
    try:
        client.delete_collection("districts")
        print("  Dropped existing collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="districts",
        metadata={"hnsw:space": "cosine"}
    )

    # Batch embed
    texts = [s["text"] for s in summaries]
    ids = [s["id"] for s in summaries]

    # Clean metadata — ChromaDB requires no None values
    def clean_meta(meta):
        return {k: (v if v is not None else -1) for k, v in meta.items()}

    metadatas = [clean_meta(s["metadata"]) for s in summaries]

    print(f"Embedding {len(texts)} district summaries...")
    BATCH_SIZE = 100
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_ids = ids[i:i+BATCH_SIZE]
        batch_meta = metadatas[i:i+BATCH_SIZE]
        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=embeddings,
            metadatas=batch_meta,
        )
        print(f"  Embedded {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

    print(f"[OK] ChromaDB index built at: {VECTOR_DIR}")
    print(f"     Collection size: {collection.count()} documents")

    # Quick sanity check
    results = collection.query(
        query_embeddings=model.encode(["worst stunting districts India"]).tolist(),
        n_results=3
    )
    print("\nSanity check — query: 'worst stunting districts India'")
    for doc in results["documents"][0]:
        print(f"  -> {doc[:120]}...")

    return client, collection


if __name__ == "__main__":
    build_index()
