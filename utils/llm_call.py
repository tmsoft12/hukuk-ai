import asyncio
import aiohttp
from typing import List,Tuple
import logging
import os
from fastapi import  HTTPException
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np
from utils.user_verify import get_db_cursor
try:
    model_path = Path("/home/tm/models/multilingual-e5-large")
    embed_model = SentenceTransformer(str(model_path))
except Exception as e:
    raise


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:1234/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")

logger.info(f"LLM_API_URL: {LLM_API_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")


async def call_llm_api(messages: List[dict], temperature: float = 0.7, max_tokens: int = 1000) -> dict:
    """Make async call to LLM API"""
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(LLM_API_URL, json=payload, timeout=30) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"LLM API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=500, detail=f"LLM API error: {response.status}")
    except asyncio.TimeoutError:
        logger.error("LLM API timeout")
        raise HTTPException(status_code=504, detail="LLM API timeout")
    except Exception as e:
        logger.error(f"Error calling LLM API: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def retrieve_segments(text: str, top_k: int = 3, similarity_threshold: float = 0.3) -> List[Tuple[str, str, float]]:
    """Retrieve top-k most similar document segments based on combined title and content similarity"""
    try:
        query_vec = embed_model.encode([text])[0].astype(np.float32)
        with get_db_cursor() as cur:
            cur.execute("SELECT title, content, embedding FROM documents")
            rows = cur.fetchall()
            if not rows:
                logger.warning("No documents found in database")
                return []
            
            sims = []
            for row in rows:
                try:
                    content_emb_array = np.array(row['embedding'], dtype=np.float32)
                    title_emb_array = embed_model.encode([row['title']])[0].astype(np.float32)
                    content_sim = cosine_sim(query_vec, content_emb_array)
                    title_sim = cosine_sim(query_vec, title_emb_array)
                    combined_sim = 0.7 * content_sim + 0.3 * title_sim
                    if combined_sim >= similarity_threshold:
                        sims.append((row['title'], row['content'], combined_sim))
                except Exception as e:
                    logger.error(f"Error processing embedding for {row['title']}: {e}")
                    continue
            
            if not sims:
                logger.info(f"No relevant segments found above threshold {similarity_threshold}")
                return []
            
            return sorted(sims, key=lambda x: x[2], reverse=True)[:top_k]
    except Exception as e:
        logger.error(f"Error in retrieve_segments: {e}")
        return []