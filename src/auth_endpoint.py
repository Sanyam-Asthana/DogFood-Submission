from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import src.auth as auth
from typing import Optional
from pydantic import BaseModel

class AuthDetails(BaseModel):
    username: str
    password: str
    role: Optional[str] = "participant"
    
# class SessionId(BaseModel):
#     session_id:str
    

origins = [
    "*"
]

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Allows requests from these origins
    allow_credentials=True,          # Allows cookies and authentication headers
    allow_methods=["*"],             # Allows all HTTP methods (GET, POST, PUT, etc.)
    allow_headers=["*"],             # Allows all headers
)

@app.post('/create_account')
def create_account(details: AuthDetails):
    # print(details)
    return auth.create_account(details.username, details.password, details.role)
    
    
@app.post('/login')
def login(details: AuthDetails):
    return auth.login(details.username,details.password)
    
    
@app.post('/logout')
def logout():
    return auth.logout()
    
@app.post('/get_current_user')
def get_current_user():
    return auth.get_current_user()


# Mount Events router
from src.routers import events_router
from src.database import init_db

init_db()
app.include_router(events_router, prefix="/api")
app.include_router(events_router)
