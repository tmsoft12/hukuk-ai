from pydantic import BaseModel
from typing import List, Tuple, Optional

class Prompt(BaseModel):
    user_prompt: str
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 100
    top_k: Optional[int] = 3
    similarity_threshold: Optional[float] = 0.3

class RoomPrompt(BaseModel):
    user_prompt: str
    room_id: Optional[int] = None
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 100
    top_k: Optional[int] = 3
    similarity_threshold: Optional[float] = 0.3

class QueryResponse(BaseModel):
    found_context: List[dict]
    generated_response: str
    context_segments: List[dict]
    response: str
    metadata: dict

class ChatMessage(BaseModel):
    id: int
    type_user: bool
    room_id: int
    prompt: str
    created_at: str

class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]
    room_info: dict

class Room(BaseModel):
    id: int
    title: str
    user_id: Optional[int]
    created_at: str

class RoomResponse(BaseModel):
    rooms: List[Room]
