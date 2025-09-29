from fastapi import HTTPException
from utils.user_verify import verify_room_ownership, get_db_cursor
from fastapi import  HTTPException, Depends
from utils.user_verify import get_current_user
from models.chat_models import ChatMessage ,ChatHistoryResponse
from utils.room import get_room_messages

def delete_room(room_id: int, current_user: dict):
    """Delete a chatroom if the authenticated user owns it"""
    try:
        user_id = current_user.get("user_id")
        if not verify_room_ownership(room_id, user_id):
            raise HTTPException(status_code=403, detail="You don't have access to this room")

        with get_db_cursor() as cur:
            cur.execute("DELETE FROM chatmessage WHERE room_id = %s", (room_id,))
            cur.execute("DELETE FROM chatroom WHERE id = %s", (room_id,))

        return {"status": "success", "message": f"Room {room_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

def get_room_chat_history(room_id: int, current_user: dict = Depends(get_current_user)):
    """Retrieve all messages for a specific room if user owns it"""
    try:
        user_id = current_user.get("user_id")
        
        if not verify_room_ownership(room_id, user_id):
            raise HTTPException(status_code=403, detail="You don't have access to this room")
        
        result = get_room_messages(room_id, user_id)
        messages = [ChatMessage(**msg) for msg in result["messages"]]
        
        return ChatHistoryResponse(
            messages=messages,
            room_info=result["room_info"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
