
import requests
from typing import List, Dict, Any

# Cache model in memory
_model_instance = None


def get_model():
    global _model_instance

    if _model_instance is None:
        from sentence_transformers import SentenceTransformer

        _model_instance = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

    return _model_instance


def get_embeddings_batch(
    texts: List[str],
    api_key: str = None
) -> List[List[float]]:

    if not texts:
        return []

    model = get_model()

    embeddings = model.encode(
        texts,
        show_progress_bar=False
    )

    return [embedding.tolist() for embedding in embeddings]


def get_query_embedding(
    text: str,
    api_key: str = None
) -> List[float]:

    model = get_model()

    embedding = model.encode(
        text,
        show_progress_bar=False
    )

    return embedding.tolist()


def generate_answer(
    query: str,
    context_chunks: List[Dict[str, Any]],
    api_key: str
) -> str:

    context_text = ""

    for idx, chunk in enumerate(context_chunks):

        context_text += f"""
SOURCE {idx + 1}

URL:
{chunk.get('url', '')}

TITLE:
{chunk.get('title', '')}

CONTENT:
{chunk.get('text', '')}

==================================================
"""

    system_prompt = """
You are a Retrieval-Augmented Generation (RAG) assistant.

Rules:
1. Use ONLY the provided context.
2. Do NOT use outside knowledge.
3. If the answer is not found, reply:
   "I cannot find the answer in the crawled website content."
4. Be concise and accurate.
5. Mention source URLs when relevant.
"""

    user_prompt = f"""
Context:

{context_text}

Question:

{query}
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1024
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("MODEL USED:", payload["model"])

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(
            f"Groq API Error {response.status_code}: {response.text}"
        )

    data = response.json()

    return data["choices"][0]["message"]["content"]

