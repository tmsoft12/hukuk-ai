import logging
from models.chat_models import RoomPrompt, QueryResponse
from fastapi import HTTPException, Depends
from utils.user_verify import get_current_user, get_db_cursor
from utils.llm_call import retrieve_segments, call_llm_api, MODEL_NAME
from utils.room import create_room, verify_room_ownership
from typing import Optional, List, Tuple, Dict, Any
import re
import json

# -----------------------------
# Constants
# -----------------------------
CONTENT_TRUNCATION_LIMIT = 2500
MIN_TRUNCATION_LIMIT = 500
DEFAULT_NO_INFO_RESPONSE = "❌ Maglumat tapylmady."

logger = logging.getLogger(__name__)

# -----------------------------
# Turkmen Corrections
# -----------------------------
with open('soz.json', "r", encoding='utf-8') as f:
    TURKMEN_CORRECTIONS = json.load(f)

# -----------------------------
# Custom Error Class
# -----------------------------
class DatabaseError(Exception):
    pass

# -----------------------------
# Helper Functions
# -----------------------------
def smart_truncate_text(text: str, max_length: int = CONTENT_TRUNCATION_LIMIT) -> str:
    if len(text) <= max_length:
        return text
    if max_length < MIN_TRUNCATION_LIMIT:
        return text[:max_length] + "..."
    sentence_endings = list(re.finditer(r'[.!?]\s+', text[:max_length + 200]))
    if sentence_endings:
        last_sentence_end = sentence_endings[-1].end()
        if last_sentence_end <= max_length:
            return text[:last_sentence_end].strip()
    words = text[:max_length].split()
    if len(words) > 1:
        return ' '.join(words[:-1]) + "..."
    return text[:max_length] + "..."

def save_chat_message(room_id: int, prompt: str, type_user: bool) -> Optional[int]:
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO chatmessage (type_user, room_id, prompt) VALUES (%s, %s, %s) RETURNING id;",
                (type_user, room_id, prompt)
            )
            result = cur.fetchone()
            return result['id'] if result else None
    except Exception as e:
        raise DatabaseError(f"💥 Message could not be saved: {str(e)}")

def apply_turkmen_corrections(text: str) -> str:
    corrected_text = text
    for wrong, correct in TURKMEN_CORRECTIONS.items():
        corrected_text = corrected_text.replace(wrong, correct)

    # Salam 👋 gibi selamları temizle
    corrected_text = re.sub(r'^S?lam\s*👋?\s*[,.]?\s*', '', corrected_text, flags=re.IGNORECASE)
    corrected_text = re.sub(r'(^|\. )([a-zäöü])', lambda m: m.group(1) + m.group(2).upper(), corrected_text)
    corrected_text = re.sub(r'([.!?])([A-ZÄÖÜa-zäöü])', r'\1 \2', corrected_text)

    # Gereksiz cümleleri kaldır
    corrected_text = corrected_text.replace("⚠️ Bu maglumat berlen maddalardan gürleşdirildi.", "")

    # Başlangıç emojileri çeşitlendir
    if not corrected_text.startswith(('⚠️', '❌', '🟢', '📌', '🔎', '📖')):
        corrected_text = '🟢 ' + corrected_text

    # Otomatik emoji eşleştirme
    replacements = {
        "kanun": "kanun 📜",
        "madda": "madda 📑",
        "salgyt": "salgyt 💰",
        "maglumat": "maglumat 📖",
        "mesele": "mesele 🤔",
        "dogry": "dogry ✅",
        "yalňyş": "yalňyş ❌",
        "karar": "karar 🏛️",
        "hukuk": "hukuk ⚖️",
    }
    for k, v in replacements.items():
        corrected_text = re.sub(fr'\b{k}\b', v, corrected_text, flags=re.IGNORECASE)

    return corrected_text.strip()

def create_system_prompt() -> str:
    return (
        "🤖 You are an assistant that always answers in Turkmen. Rules:\n"
        "1️⃣ Always answer in Turkmen.\n"
        "2️⃣ If relevant retrieved information exists, use it 📚.\n"
        "3️⃣ If no relevant info is found, answer using your general knowledge 💡.\n"
        "4️⃣ Do not include greetings 🙅‍♂️.\n"
        "5️⃣ Use Markdown format 📝.\n"
        "6️⃣ If you truly cannot answer, reply with: "
        "'⚠️ Bu barada maglumatym ýok. Başga size nädip kömek edip bilerin?'\n"
    )

def create_direct_answer_from_segments(segments: List[Tuple[str, str, float]]) -> str:
    if not segments:
        return DEFAULT_NO_INFO_RESPONSE
    answer = "📚 **Tapylan maglumatlar:**\n\n"
    for i, (title, content, similarity) in enumerate(segments, 1):
        confidence = round(similarity * 100, 1)
        answer += f"### 📌 {i}. {title}\n"
        answer += f"🔎 Benzetme derejesi: **{confidence}%**\n\n"
        answer += f"{content}\n\n"
        if i < len(segments):
            answer += "--- ✨ ---\n\n"
    return answer

async def process_room_setup(room_id: Optional[int], user_prompt: str, user_id: int) -> Tuple[int, str]:
    if room_id is None:
        room_title = user_prompt[:100] if len(user_prompt) > 100 else user_prompt
        new_room_id = create_room(room_title, user_id)
        if new_room_id is None:
            raise HTTPException(status_code=500, detail="❌ Could not create chat room 🏚️")
        return new_room_id, room_title
    else:
        if not verify_room_ownership(room_id, user_id):
            raise HTTPException(status_code=403, detail="🚫 You do not have access to this room 🔒")
        return room_id, "Existing Room"

# -----------------------------
# Main Function
# -----------------------------
async def room_query(prompt: RoomPrompt, current_user: dict = Depends(get_current_user)) -> QueryResponse:
    if not prompt.user_prompt or not prompt.user_prompt.strip():
        raise HTTPException(status_code=400, detail="⚠️ Empty query submitted ❗")

    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="❌ User not authenticated 🔑")

    room_id, room_title = await process_room_setup(prompt.room_id, prompt.user_prompt, user_id)

    try:
        save_chat_message(room_id, prompt.user_prompt, type_user=True)
    except DatabaseError as e:
        logger.error(f"❌ Could not save user query: {str(e)}")

    # Fetch previous messages
    previous_messages = []
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT type_user, prompt FROM chatmessage WHERE room_id=%s ORDER BY id ASC",
                (room_id,)
            )
            previous_messages = cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Could not fetch previous messages: {str(e)}")

    context_text = ""
    for msg in previous_messages:
        role = "👤 User" if msg['type_user'] else "🤖 Assistant"
        context_text += f"{role}: {msg['prompt']}\n"

    # Retrieve RAG segments
    try:
        top_segments = retrieve_segments(prompt.user_prompt, prompt.top_k, prompt.similarity_threshold)
    except Exception as e:
        logger.error(f"❌ Could not retrieve info: {str(e)}")
        top_segments = []

    # Build messages for LLM
    system_message = {"role": "system", "content": create_system_prompt()}
    user_message_content = f"{context_text}\n👤 User soragy: {prompt.user_prompt}"
    if top_segments:
        context_segment_text = "\n".join([f"{title}: {content}" for title, content, _ in top_segments])
        user_message_content += f"\n\n📌 Relevant info:\n{context_segment_text}"
    user_message = {"role": "user", "content": user_message_content}

    # Call LLM
    generated_answer = ""
    try:
        response = await call_llm_api([system_message, user_message], prompt.temperature, prompt.max_tokens)
        if response and "choices" in response and response["choices"]:
            generated_answer = response["choices"][0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"❌ LLM API error: {str(e)}")

    # Fallback logic
    if not generated_answer:
        if top_segments:
            generated_answer = create_direct_answer_from_segments(top_segments)
        else:
            generated_answer = "🟢 Bu umumy maglumatlara esaslanyp berilen jogap 💡."

    generated_answer = apply_turkmen_corrections(generated_answer)

    try:
        save_chat_message(room_id, generated_answer, type_user=False)
    except DatabaseError as e:
        logger.error(f"❌ Could not save bot response: {str(e)}")

    context_segments = [
        {
            "title": title,
            "content": smart_truncate_text(content),
            "similarity": float(similarity),
            "similarity_percentage": round(float(similarity) * 100, 1)
        } for title, content, similarity in top_segments
    ]

    found_context = [
        {
            "index": i + 1,
            "title": title,
            "content": content,
            "similarity_score": round(float(similarity), 4),
            "similarity_percentage": round(float(similarity) * 100, 1)
        } for i, (title, content, similarity) in enumerate(top_segments)
    ]

    return QueryResponse(
        found_context=found_context,
        generated_response=generated_answer,
        context_segments=context_segments,
        response=generated_answer,
        metadata={
            "model": MODEL_NAME,
            "temperature": prompt.temperature,
            "max_tokens": prompt.max_tokens,
            "segments_used": len(top_segments),
            "similarity_threshold": prompt.similarity_threshold,
            "top_k": prompt.top_k,
            "no_relevant_data": not bool(top_segments),
            "chatroom_id": room_id,
            "chatroom_title": room_title,
            "user_id": user_id,
            "data_source": "database_and_general_knowledge",
            "processing_successful": True
        }
    )
