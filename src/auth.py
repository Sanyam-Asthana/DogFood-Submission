import os
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv

# 1. Initialize the client
# In production, load these from environment variables!
load_dotenv(find_dotenv())
print(os.getenv("CONFIRM"))
SUPABASE_URL = os.getenv("SUPABASE_PUBLIC_URL")
SUPABASE_KEY = os.getenv("ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def create_account(email, password, role="user"):
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
    try:
        response = supabase.auth.sign_out()
    except Exception as e:
        print("Logout Failed:",e)
        return {"error":str(e)}

def get_current_user():
    # Gets the currently logged-in user based on the active session
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