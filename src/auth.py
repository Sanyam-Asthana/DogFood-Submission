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

def create_account(email, password):
    print(f"Signing up {email}...")
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        print("Success! User ID:", response.user.id)
        # Return a simple dictionary that FastAPI can easily convert to JSON
        return {"message": "Account created", "user_id": response.user.id}
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
        print("Success! Access Token:", response.session.access_token[:15] + "...")
        # Return the token so the frontend can use it
        return {
            "access_token": response.session.access_token, 
            "user_id": response.user.id
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