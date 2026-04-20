import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "ai-quiz-system-secret")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    UPLOAD_FOLDER = "uploads"
    ALLOWED_EXTENSIONS = {"pdf"}

# Debug print for API Key (masked)
if Config.GEMINI_API_KEY:
    masked_key = Config.GEMINI_API_KEY[:5] + "..." + Config.GEMINI_API_KEY[-5:]
    print(f"✅ GEMINI_API_KEY loaded: {masked_key}")
else:
    print("❌ GEMINI_API_KEY NOT FOUND! Please check your .env file.")
