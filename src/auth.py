import os
import logging
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

# 1. Initialize the client
load_dotenv(find_dotenv())
SUPABASE_URL = os.getenv("SUPABASE_PUBLIC_URL") or "http://localhost:8000"
SUPABASE_KEY = os.getenv("ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.warning(f"Could not initialize Supabase client: {e}")
else:
    logger.warning("ANON_KEY or SUPABASE_PUBLIC_URL not provided. Supabase client skipped.")

def create_account(email, password, role="user"):
    if not supabase:
        return {"error": "Supabase client is not configured (missing ANON_KEY or SUPABASE_PUBLIC_URL)."}
    print(f"Signing up {email} with role {role}...")
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"role": role}
            }
        })
        user_id = response.user.id if response.user else None
        access_token = None
        if response.session and hasattr(response.session, "access_token"):
            access_token = response.session.access_token

        # If session was not immediately returned, attempt login to retrieve token
        if not access_token:
            try:
                sign_in_res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if sign_in_res.session and hasattr(sign_in_res.session, "access_token"):
                    access_token = sign_in_res.session.access_token
                    if not user_id and sign_in_res.user:
                        user_id = sign_in_res.user.id
            except Exception:
                pass

        session_token = access_token or f"usr_{user_id}"

        # Record user and assigned role into local PostgreSQL users table
        if user_id:
            try:
                from src.database import SessionLocal
                from src.models.user import User
                db = SessionLocal()
                u = db.query(User).filter((User.id == user_id) | (User.email == email)).first()
                if not u:
                    u = User(
                        id=user_id,
                        email=email,
                        name=email.split("@")[0],
                        role=role or "user",
                        session_token=f"usr_{user_id}",
                    )
                    db.add(u)
                    db.commit()
                else:
                    if u.id != user_id:
                        u.id = user_id
                    u.role = role or u.role or "user"
                    u.session_token = f"usr_{user_id}"
                    db.commit()
                    role = u.role
                db.close()
            except Exception as dbe:
                print("Could not sync user to db:", dbe)

        print("Success! User ID:", user_id)
        return {
            "message": "Account created",
            "user_id": user_id,
            "email": email,
            "role": role,
            "access_token": access_token or session_token,
            "session_token": session_token,
        }
    except Exception as e:
        print("Sign up failed:", e)
        return {"error": str(e)}

def login(email, password):
    if not supabase:
        return {"error": "Supabase client is not configured (missing ANON_KEY or SUPABASE_PUBLIC_URL)."}
    print(f"Logging in {email}...")
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        user_id = response.user.id
        access_token = response.session.access_token
        print("Success! Access Token:", access_token[:15] + "...")
        role = "user"
        try:
            from src.database import SessionLocal
            from src.models.user import User
            db = SessionLocal()
            u = db.query(User).filter((User.id == user_id) | (User.email == email)).first()
            if not u:
                u = User(
                    id=user_id,
                    email=email,
                    name=email.split("@")[0],
                    role="user",
                    session_token=f"usr_{user_id}",
                )
                db.add(u)
                db.commit()
            else:
                if u.id != user_id:
                    u.id = user_id
                u.session_token = f"usr_{user_id}"
                db.commit()
                role = u.role
            db.close()
        except Exception as dbe:
            print("DB sync error:", dbe)

        return {
            "access_token": access_token,
            "session_token": access_token,
            "user_id": user_id,
            "email": email,
            "role": role,
        }
    except Exception as e:
        print("Login failed:", e)
        return {"error": str(e)}

def logout():
    if not supabase:
        return {"error": "Supabase client is not configured."}
    try:
        response = supabase.auth.sign_out()
    except Exception as e:
        print("Logout Failed:",e)
        return {"error":str(e)}

def get_current_user():
    # Gets the currently logged-in user based on the active session
    if not supabase:
        return "No active session (Supabase not configured)."
    user = supabase.auth.get_user()
    result=""
    if user:
        result="Current user email:"+user.user.email
    else:
        result="No active session."
    print(result)
    return result

# --- Test the workflow ---
test_email = "testuser@example.com"
test_password = "123456"

# Run these one at a time. Once the account is created, you only need to log in.
# create_account(test_email, test_password)
# login(test_email, test_password)
# get_current_user()