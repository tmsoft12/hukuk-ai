from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database.db import get_db_connection
from models.auth import AuthService
import bcrypt
from utils.jwt import decode_token, create_access_token, create_refresh_token
from pydantic import BaseModel
from captcha.image import ImageCaptcha
import io, random, string, uuid, time
from typing import Dict

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

# ---------------- CAPTCHA Cache ----------------
CAPTCHA_CACHE: Dict[str, dict] = {}
CAPTCHA_EXPIRE_TIME = 300  # 5 dakika

def cleanup_expired_captchas():
    """Süresi geçen CAPTCHA'ları temizle"""
    current_time = time.time()
    expired_keys = [
        captcha_id for captcha_id, data in CAPTCHA_CACHE.items()
        if current_time - data['created_at'] > CAPTCHA_EXPIRE_TIME
    ]
    for key in expired_keys:
        del CAPTCHA_CACHE[key]

# ---------------- Parola işlemleri ----------------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# ---------------- Refresh token request modeli ----------------
class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    user: AuthService
    captcha_solution: str
    captcha_id: str

# ---------------- CAPTCHA ----------------
@router.get("/captcha")
def get_captcha():
    cleanup_expired_captchas()

    captcha_id = str(uuid.uuid4())
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

    CAPTCHA_CACHE[captcha_id] = {
        'text': captcha_text,
        'created_at': time.time(),
        'used': False
    }

    # CAPTCHA resmi oluştur
    image_captcha = ImageCaptcha(width=280, height=90)
    data = image_captcha.generate(captcha_text)
    buf = io.BytesIO(data.read())
    buf.seek(0)
    print(captcha_text)
    response = StreamingResponse(buf, media_type="image/png")
    response.headers["X-Captcha-ID"] = captcha_id
    return response

def verify_captcha(captcha_id: str, input_text: str):
    cleanup_expired_captchas()

    if captcha_id not in CAPTCHA_CACHE:
        raise HTTPException(status_code=400, detail="Invalid or expired CAPTCHA")

    captcha_data = CAPTCHA_CACHE[captcha_id]

    if captcha_data['used']:
        raise HTTPException(status_code=400, detail="CAPTCHA already used")

    if input_text.upper() != captcha_data['text'].upper():
        raise HTTPException(status_code=400, detail="Captcha verification failed")

    captcha_data['used'] = True

# ---------------- Register ----------------
@router.post("/register")
def create_user(user: AuthService):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        hashed_pwd = hash_password(user.password)
        cur.execute(
            "INSERT INTO users (name, password) VALUES (%s, %s) RETURNING id, name",
            (user.name, hashed_pwd)
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        conn.close()

    access_token = create_access_token({"user_id": row["id"], "name": row["name"]})
    refresh_token = create_refresh_token({"user_id": row["id"], "name": row["name"]})

    return {
        "message": "User created successfully",
        "user": {"id": row["id"], "name": row["name"]},
        "access_token": access_token,
        "refresh_token": refresh_token
    }

# ---------------- Login ----------------
@router.post("/login")
def login_user(login_data: LoginRequest):
    verify_captcha(login_data.captcha_id, login_data.captcha_solution)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, password FROM users WHERE name = %s", (login_data.user.name,))
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if row is None or not verify_password(login_data.user.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token({"user_id": row["id"], "name": row["name"]})
    refresh_token = create_refresh_token({"user_id": row["id"], "name": row["name"]})

    return {
        "message": "Login successful",
        "user": {"id": row["id"], "name": row["name"]},
        "access_token": access_token,
        "refresh_token": refresh_token
    }

# ---------------- Refresh ----------------
@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest):
    payload = decode_token(request.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = create_access_token({"user_id": payload["user_id"], "name": payload["name"]})
    new_refresh_token = create_refresh_token({"user_id": payload["user_id"], "name": payload["name"]})

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token
    }

# ---------------- Koruma için dependency ----------------
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token, token_type="access")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    return payload

# ---------------- Örnek korumalı endpoint ----------------
@router.get("/protected")
def protected_route(current_user: dict = Depends(get_current_user)):
    return {
        "user_id":current_user['user_id'],
        "name":current_user['name']}
