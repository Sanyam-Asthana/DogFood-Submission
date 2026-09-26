from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import src.auth as auth
from pydantic import BaseModel

class AuthDetails(BaseModel):
    username:str
    password:str
    
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
    return auth.create_account(details.username,details.password)
    
    
@app.post('/login')
def login(details: AuthDetails):
    return auth.login(details.username,details.password)
    
    
@app.post('/logout')
def logout():
    return auth.logout()
    
@app.post('/get_current_user')
def get_current_user():
    return auth.get_current_user()

    
