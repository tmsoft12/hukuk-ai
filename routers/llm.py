from fastapi import APIRouter, HTTPException, Depends
import logging
from models.chat_models import QueryResponse , Prompt,RoomResponse,ChatHistoryResponse,RoomPrompt
from utils.room import get_user_rooms
from controller.room import delete_room , get_room_chat_history
from controller.chat import room_query
from typing import Optional
from fastapi import Query
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/gpt",
    tags=["llm"]
)

from utils.user_verify import get_current_user
# @router.post("/query", response_model=QueryResponse)
# async def query(prompt: Prompt, current_user: dict = Depends(get_current_user)):
#     """Process text query and return response with context - Creates new room"""
#     if not prompt.user_prompt.strip():
#         raise HTTPException(status_code=400, detail="Empty prompt provided")
    
#     try:
#         user_id = current_user.get("user_id")
        
#         room_title = await generate_room_title(prompt.user_prompt)
#         room_id = create_room(room_title, user_id)
#         if room_id is None:
#             logger.warning("Failed to create chatroom, continuing with query processing")

#         if room_id:
#             save_chat_message(room_id, prompt.user_prompt, type_user=True)

#         top_segments = retrieve_segments(
#             prompt.user_prompt,
#             prompt.top_k,
#             prompt.similarity_threshold
#         )
        
#         if not top_segments:
#             no_info_messages = [
#             {
#                 "role": "system",
#                 "content": (
#                     "Siz diňe Turkmence jogap berýän kömekçi modelsiňiz. "
#                     "Eger kontekstde maglumat ýok bolsa, diňe şu sözleri aýdyň: "
#                     "'Bu barada maglumatym ýok.  öwrenmäni dowam edýarin.' "
#                     "Başga sözler ulanma."
#                 )
#             },
#             {
#                 "role": "user",
#                 "content": f"Sorag: {prompt.user_prompt}\n\nHiç hili maglumat tapylmady."
#             }
#         ]

#             response = await call_llm_api(no_info_messages, prompt.temperature, prompt.max_tokens)
#             generated_answer = "Bu barada maglumatym ýok."
            
#             if room_id:
#                 save_chat_message(room_id, generated_answer, type_user=False)
            
#             return QueryResponse(
#                 found_context=[],
#                 generated_response=generated_answer,
#                 context_segments=[],
#                 response=generated_answer,
#                 metadata={
#                     "model": MODEL_NAME,
#                     "temperature": prompt.temperature,
#                     "segments_used": 0,
#                     "similarity_threshold": prompt.similarity_threshold,
#                     "no_relevant_data": True,
#                     "chatroom_id": room_id,
#                     "chatroom_title": room_title,
#                     "user_id": user_id
#                 }
#             )
        
#         found_context = []
#         context_text = ""
#         for i, (title, content, similarity) in enumerate(top_segments, 1):
#             context_item = {
#                 "index": i,
#                 "title": title,
#                 "content": content,
#                 "similarity_score": round(float(similarity), 4),
#                 "similarity_percentage": round(float(similarity) * 100, 1)
#             }
#             found_context.append(context_item)
#             context_text += f"\n--- Kontekst {i} ---\nBaşlyk: {title}\nMazmuny: {content}\n"
        
#         messages = [
#            {
#             "role": "system",
#             "content": "Siz diňe Turkmence jogap berýän kömekçi modelsiňiz. Eger kontekstdan degişli maglumat tapylsa diňe şol maglumat esasynda jogap beriň. Tapylmasa diňe 'Bu barada maglumatym ýok.' diýip jogap beriň. Ýeke-täk iki görnüş bar: ya maglumatly jogap, ya-da 'Bu barada maglumatym ýok.'"
#             },
#             {
#                 "role": "user",
#                 "content": f"Sorag: {prompt.user_prompt}\n\nKontekst:{context_text}"
#             }
#         ]
        
#         response = await call_llm_api(messages, prompt.temperature, prompt.max_tokens)
#         generated_answer = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
#         if room_id:
#             save_chat_message(room_id, generated_answer, type_user=False)
        
#         context_segments = [
#             {
#                 "title": seg[0],
#                 "content": seg[1][:200] + "..." if len(seg[1]) > 200 else seg[1],
#                 "similarity": float(seg[2])
#             }
#             for seg in top_segments
#         ]
        
#         return QueryResponse(
#             found_context=found_context,
#             generated_response=generated_answer,
#             context_segments=context_segments,
#             response=generated_answer,
#             metadata={
#                 "model": MODEL_NAME,
#                 "temperature": prompt.temperature,
#                 "segments_used": len(top_segments),
#                 "similarity_threshold": prompt.similarity_threshold,
#                 "no_relevant_data": False,
#                 "chatroom_id": room_id,
#                 "chatroom_title": room_title,
#                 "user_id": user_id
#             }
#         )
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in query endpoint: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/room-query", response_model=QueryResponse)
async def room_query_endpoint(
    prompt: RoomPrompt,
    current_user: dict = Depends(get_current_user)
):
    return await room_query(prompt, current_user)
from pydantic import BaseModel
from typing import List, Dict

class Room(BaseModel):
    id: int
    title: str
    user_id: int
    created_at: str

class RoomResponse(BaseModel):
    rooms: List[Room]
    has_next: bool

@router.get("/rooms", response_model=RoomResponse)
async def get_rooms(
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search by room title"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve chatrooms for the authenticated user with optional title search
    and pagination (for infinite scroll)
    """
    try:
        user_id = current_user.get("user_id")
        result = get_user_rooms(user_id=user_id, search=search, limit=limit, offset=offset)
        return RoomResponse(**result)
    except Exception as e:
        logger.error(f"Error in get_rooms endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/room/{room_id}/messages", response_model=ChatHistoryResponse)
async def get_room_message( 
    room_id:int,
    current_user: dict = Depends(get_current_user)):
    return get_room_chat_history(room_id,current_user)


@router.delete("/room/{room_id}")
async def delete_room_end(
    room_id:int,
    current_user: dict = Depends(get_current_user)
):
    return delete_room(room_id,current_user)
