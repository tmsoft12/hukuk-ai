from pydantic import BaseModel

class AuthService(BaseModel):
    id: int | None = None   
    name: str
    password: str
