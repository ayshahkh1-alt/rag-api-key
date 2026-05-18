اfrom fastapi import FastAPI
from pydantic import BaseModel
import weaviate
from openai import OpenAI
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI()

# OpenAI client
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Weaviate
client = weaviate.connect_to_weaviate_cloud(
    cluster_url="https://avorqfxtslmw00omr0rt1g.c0.asia-southeast1.gcp.weaviate.cloud",
    auth_credentials=weaviate.auth.AuthApiKey(
        "aDMzTFVKNmQ4MHBYQ2RHc19GOGtId3NJMHJ2MDZMRHhsNVcyY2J5c3l5Q2l5RW40cDk3ejdPWmpuN0dBPV92MjAw"
    )
)

collection = client.collections.get("KnowledgeBase")


class ChatRequest(BaseModel):
    question: str


# 🧼 تنظيف النص
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# 🎯 استخراج السعر
def extract_price(text: str):
    match = re.search(r"(\d+(\.\d+)?)\s*شيكل", text)
    return float(match.group(1)) if match else None


# 🎯 فلترة حسب السؤال
def filter_results(objects, question):

    filtered = []

    # استخراج رقم السعر من السؤال
    price_filter = None
    price_match = re.search(r"(\d+)\s*شيكل", question)
    if price_match:
        price_filter = float(price_match.group(1))

    for obj in objects:

        text = obj.properties.get("text", "")
        text = clean_text(text)

        price = extract_price(text)

        # 🔥 فلترة السعر إذا موجود بالسؤال
        if price_filter is not None and price != price_filter:
            continue

        filtered.append(text)

    return filtered


# 🔥 تنسيق الرد النهائي
def format_answer(text: str) -> str:

    lines = text.split("\n")
    result = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        line = line.replace("-", "•")

        result.append(line)

    return "\n".join(result)


@app.post("/chat")
def chat(req: ChatRequest):

    # 1. Retrieve من Weaviate
    results = collection.query.near_text(
        query=req.question,
        limit=20
    )

    # 2. فلترة ذكية
    filtered_texts = filter_results(results.objects, req.question)

    context = "\n\n".join(filtered_texts)

    # 3. Prompt محسن
    prompt = f"""
أنت مساعد متجر ورد احترافي جداً.

🎯 قواعد مهمة:
- استخدم فقط المعلومات الموجودة
- لا تخترع منتجات
- رد بشكل "كرت منتج"
- إذا لا يوجد نتائج قل: لا توجد منتجات مطابقة

تنسيق الرد:

🌹 اسم المنتج
💰 السعر: ...
📦 التوفر: ...

المعلومات:
{context}

السؤال:
{req.question}

أجب بالعربية فقط وبشكل منظم.
"""

    # 4. GPT
    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "أنت مساعد متجر ورد ذكي يعرض المنتجات بدقة وبدون تخمين."
            },
            {"role": "user", "content": prompt}
        ]
    )

    raw_answer = response.choices[0].message.content

    # 5. تنظيف الرد
    answer = format_answer(raw_answer)

    return {
        "question": req.question,
        "answer": answer,
        "sources_used": len(results.objects),
        "filtered_results": len(filtered_texts)
    }
