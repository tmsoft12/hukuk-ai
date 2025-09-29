from utils.user_verify import verify_room_ownership,get_db_cursor
from typing import List,Optional

def get_room_messages(room_id: int, user_id: int) -> List[dict]:
    """Retrieve all messages for a specific room if user owns it"""
    try:
        if not verify_room_ownership(room_id, user_id):
            return []
        
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT cm.id, cm.type_user, cm.room_id, cm.prompt, cm.created_at,
                          cr.title, cr.user_id as room_owner_id
                   FROM chatmessage cm
                   JOIN chatroom cr ON cm.room_id = cr.id
                   WHERE cm.room_id = %s
                   ORDER BY cm.created_at ASC;""",
                (room_id,)
            )
            rows = cur.fetchall()
            
            messages = []
            room_info = {}
            
            for row in rows:
                message = {
                    "id": row['id'],
                    "type_user": row['type_user'],
                    "room_id": row['room_id'],
                    "prompt": row['prompt'],
                    "created_at": row['created_at'].isoformat()
                }
                messages.append(message)
                
                if not room_info:
                    room_info = {
                        "room_id": row['room_id'],
                        "title": row['title'],
                        "owner_id": row['room_owner_id']
                    }
            
            return {"messages": messages, "room_info": room_info}
    except Exception as e:
        return {"messages": [], "room_info": {}}
    

from utils.llm_call import call_llm_api


async def generate_room_title(prompt: str) -> str:
    """Generate a room title using the LLM based on the user prompt"""
    try:
        messages = [
            {
                "role": "system",
                "content": "Siz Turkmence jogap berýän kömekçi modelsiňiz. Berlen soragdan gysga we manyly otag ady dörediň (maksimum 50 simwol)."
            },
            {
                "role": "user",
                "content": f"Sorag: {prompt}\n\nBu sorag üçin gysga bir title dörediň."
            }
        ]
        response = await call_llm_api(messages, temperature=0.8, max_tokens=50)
        title = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not title:
            return prompt[:50]
        return title[:50]
    except Exception as e:
        return prompt[:50]

def create_room(title: str, user_id: Optional[int] = None) -> Optional[int]:
    """Create a new chatroom with the given title and user_id"""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO chatroom (title, user_id) VALUES (%s, %s) RETURNING id;",
                (title, user_id)
            )
            room_id = cur.fetchone()['id']
            return room_id
    except Exception as e:
        return None



from typing import List, Optional
from typing import Optional, List, Dict

def get_user_rooms(
    user_id: int,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Dict:
    """Retrieve user's chatrooms with optional title search, pagination and has_next info"""
    try:
        with get_db_cursor() as cur:
            query = """
                SELECT id, title, user_id, created_at 
                FROM chatroom 
                WHERE user_id = %s
            """
            params = [user_id]

            if search:
                query += " AND title ILIKE %s"
                params.append(f"%{search}%")

            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit + 1, offset])

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            has_next = len(rows) > limit
            rooms = [
                {
                    "id": row['id'],
                    "title": row['title'],
                    "user_id": row['user_id'],
                    "created_at": row['created_at'].isoformat()
                }
                for row in rows[:limit]
            ]

            return {
                "rooms": rooms,
                "has_next": has_next
            }
    except Exception as e:
        return {"rooms": [], "has_next": False}
