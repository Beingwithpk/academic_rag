import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "academic_super_secret_fallback_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing in .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing in .env")