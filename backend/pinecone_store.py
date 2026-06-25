import os
import uuid
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(
    api_key=os.getenv("PINECONE_API_KEY")
)

index = pc.Index(
    os.getenv("PINECONE_INDEX")
)

def upsert_chunks(chunks, embeddings):

    vectors = []

    for chunk, embedding in zip(chunks, embeddings):

        vectors.append({
            "id": str(uuid.uuid4()),
            "values": embedding,
            "metadata": {
                "url": chunk["url"],
                "title": chunk["title"],
                "text": chunk["text"]
            }
        })

    index.upsert(vectors=vectors)


def search_chunks(query_embedding, top_k=5):

    response = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )

    results = []

    for match in response.matches:

        results.append(
            (
                {
                    "url": match.metadata["url"],
                    "title": match.metadata["title"],
                    "text": match.metadata["text"]
                },
                match.score
            )
        )

    return results