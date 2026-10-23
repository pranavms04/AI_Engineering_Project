from pathlib import Path

import numpy as np

from app.ingestion.chunking import chunk_documents
from app.ingestion.loader import load_directory
from app.retrieval.embedder import embed_query, embed_texts

# 1. Compare a few sentences
sentences = [
    "How do I install Python packages?",
    "Using pip to add libraries to a project",
    "My favourite food is biryani",
]
vectors = embed_texts(sentences)
print("Shape:", vectors.shape)                       # (3, 384)
print("Similarity matrix:\n", np.round(vectors @ vectors.T, 2))

# 2. Search your own chunks
chunks = chunk_documents(load_directory(Path("data/sample_docs")))
chunk_vectors = embed_texts([c.text for c in chunks])

question = "How do I declare a path parameter with a type?"
scores = chunk_vectors @ embed_query(question)       # one score per chunk
top = np.argsort(scores)[::-1][:3]                   # 3 highest scores

for i in top:
    print(f"\nscore={scores[i]:.3f}  {chunks[i].metadata}")
    print(chunks[i].text[:200])