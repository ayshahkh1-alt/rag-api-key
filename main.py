from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import weaviate
import os

load_dotenv()

app = FastAPI()

# ===================================
# ENV VARIABLES
# ===================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# ===================================
# OPENAIprint("OPENAI:", OPENAI_API_KEY)
print("WEAVIATE URL:", WEAVIATE_URL)
print("WEAVIATE KEY:", WEAVIATE_API_KEY)
# ===================================

client_ai = OpenAI(api_key=OPENAI_API_KEY)

# ===================================
# WEAVIATE
# ===================================
try:
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=WEAVIATE_URL,
        auth_credentials=weaviate.auth.AuthApiKey(
            WEAVIATE_API_KEY
        )
    )

    collection = client.collections.get("KnowledgeBase")
    print("Weaviate connected successfully ✅")

except Exception as e:
    print("ERROR CONNECTING TO WEAVIATE:")
    print(e)
# ===================================
# REQUEST MODEL
# ===================================

class ChatRequest(BaseModel):
    question: str

# ===================================
# HOME
# ===================================

@app.get("/")
def home():
    return {"message": "RAG API working 🚀"}

# ===================================
# CHAT ENDPOINT
# ===================================

@app.post("/chat")
def chat(req: ChatRequest):

    results = collection.query.near_text(
        query=req.question,
        limit=5
    )

    context = "\n".join([
        obj.properties.get("text", "")
        for obj in results.objects
    ]) if results.objects else ""

    prompt = f"""
أنت مساعد ذكي لمتجر ورد.

استخدم المعلومات التالية فقط:

{context}

السؤال:
{req.question}

أجب بالعربية بشكل مرتب.
"""

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "أنت مساعد متجر ورد محترف."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content

    return {
        "question": req.question,
        "answer": answer
    }
