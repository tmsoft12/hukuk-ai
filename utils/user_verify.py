from database.db import get_db_connection
from pgvector.psycopg2 import register_vector
from contextlib import contextmanager
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Depends
from routers.users import decode_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@contextmanager
def get_db_cursor():
    """Context manager for database connections with cursor"""
    conn = None
    try:
        conn = get_db_connection()
        register_vector(conn)
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def verify_room_ownership(room_id: int, user_id: int) -> bool:
    """Verify if the user owns the specified room"""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT user_id FROM chatroom WHERE id = %s", (room_id,))
            result = cur.fetchone()
            if result is None:
                return False
            return result['user_id'] == user_id
    except Exception as e:
        logger.error(f"Error verifying room ownership: {e}")
        return False
    

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Decode JWT token and return user information"""
    token = credentials.credentials
    payload = decode_token(token, token_type="access")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    if "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Token does not contain user_id")
    return payload