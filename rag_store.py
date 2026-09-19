import chromadb
from rag_chunker import build_repo_chunks
from rag_embeddings import generate_embeddings, build_embedding_text, model

# Persistent client -> data disk par save hoga, dobara chalane par dobara banane ki zarurat nahi
client = chromadb.PersistentClient(path="./chroma_db")

# Collection banao (ya agar already hai toh use lo)
# ChromaDB by default HNSW index use karta hai similarity search ke liye
collection = client.get_or_create_collection(
    name="codesentinel_repo",
    metadata={"hnsw:space": "cosine"}  # cosine similarity - code comparison ke liye best
)


def build_and_store_index(branch="main"):
    """Repo ko chunk karo, embeddings banao, aur ChromaDB mein store karo"""
    print("Fetching and chunking repo code...\n")
    chunks = build_repo_chunks(branch=branch)
    print(f"Total chunks: {len(chunks)}\n")

    print("Generating embeddings...\n")
    embeddings = generate_embeddings(chunks)

    # Har chunk ke liye unique ID banao
    ids = [f"{c['filename']}::{c['function_name']}::{i}" for i, c in enumerate(chunks)]

    # Metadata - taaki search result ke sath filename/function name bhi mile
    metadatas = [
        {
            "filename": c["filename"],
            "function_name": c["function_name"],
            "start_line": c["start_line"],
            "end_line": c["end_line"]
        }
        for c in chunks
    ]

    # Documents - actual text jo store hoga (readable form mein)
    documents = [build_embedding_text(c) for c in chunks]

    print("Storing in ChromaDB...\n")
    collection.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        metadatas=metadatas,
        documents=documents
    )

    print(f"✅ Stored {len(ids)} chunks in ChromaDB collection 'codesentinel_repo'\n")
    return len(ids)


def search_related_code(query_text, n_results=3):
    """Query text se milta julta code dhundo ChromaDB mein (humara khud ka model use karke)"""
    query_embedding = model.encode([query_text]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    return results


if __name__ == "__main__":
    # Step 1: Index banao aur store karo
    build_and_store_index(branch="main")

    # Step 2: Test query chalao - confirm karo search kaam kar raha hai
    print("=" * 70)
    print("TEST QUERY: 'function that divides two numbers'")
    print("=" * 70)

    results = search_related_code("function that divides two numbers", n_results=3)

    for i in range(len(results['ids'][0])):
        print(f"\n🔍 Match #{i+1}")
        print(f"File: {results['metadatas'][0][i]['filename']}")
        print(f"Function: {results['metadatas'][0][i]['function_name']}")
        print(f"Distance (kam = zyada similar): {results['distances'][0][i]:.4f}")