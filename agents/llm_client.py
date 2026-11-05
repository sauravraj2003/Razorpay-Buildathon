"""Groq LLM Client configuration with robust fallback support."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def get_groq_llm(temperature: float = 0.2):
    """Returns a ChatGroq instance if GROQ_API_KEY is available, else None."""
    if not GROQ_API_KEY:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=GROQ_MODEL,
            temperature=temperature,
            api_key=GROQ_API_KEY
        )
    except Exception as e:
        print(f"Warning: Failed to initialize ChatGroq: {e}")
        return None
