from sentence_transformers import SentenceTransformer
from rag_chunker import build_repo_chunks

print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded!\n")


def build_embedding_text(chunk):
    """
    Chunk ko ek achhe descriptive text mein convert karo, taaki
    embedding model ko zyada context mile (sirf raw code se behtar hai).
    """
    return (
        f"File: {chunk['filename']}\n"
        f"Function: {chunk['function_name']}\n"
        f"Code:\n{chunk['code']}"
    )


def generate_embeddings(chunks):
    """Har chunk ke liye embedding (vector) banao"""
    texts = [build_embedding_text(chunk) for chunk in chunks]
    embeddings = model.encode(texts)
    return embeddings


if __name__ == "__main__":
    print("Fetching and chunking repo code...\n")
    chunks = build_repo_chunks(branch="main")
    print(f"\nTotal chunks: {len(chunks)}\n")

    print("Generating embeddings...\n")
    embeddings = generate_embeddings(chunks)

    print(f"✅ Generated {len(embeddings)} embeddings")
    print(f"Each embedding has {len(embeddings[0])} dimensions\n")

    print("=" * 70)
    print("Sample check — first chunk's embedding:")
    print("=" * 70)
    print(f"Chunk: {chunks[0]['filename']} :: {chunks[0]['function_name']}()")
    print(f"First 10 values of its embedding vector: {embeddings[0][:10]}")
    print(f"Total dimensions: {len(embeddings[0])}")