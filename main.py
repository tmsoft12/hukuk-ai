# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import users, llm
from dotenv import load_dotenv


load_dotenv(override=True) 


app = FastAPI(title="FastAPI Modular with PostgreSQL")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       
    allow_credentials=True,
    allow_methods=["*"],         
    allow_headers=["*"],  
    expose_headers=["x-captcha-id"]
)
app.include_router(users.router)
app.include_router(llm.router)
