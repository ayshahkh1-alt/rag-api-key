from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import weaviate
from openai import OpenAI
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ OpenAI
client_ai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ✅ Weaviate
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=weaviate.auth.AuthApiKey(
        WEAVIATE_API_KEY
    )
)

collection = client.collections.get("KnowledgeBase")


class ChatRequest(BaseModel):
    question: str


# 🌸 كلمات خاصة بمجال الورد
flower_keywords = [
    "ورد",
    "بوكيه",
    "زهور",
    "هدية",
    "هدايا",
    "جوري",
    "تغليف",
    "مناسبة",
    "عيد",
    "تنسيق",
    "توليب",
    "لافندر",
    "باقة"
]


# 🧼 تنظيف النص
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# 🎯 استخراج السعر
def extract_price(text: str):

    match = re.search(r"(\d+(\.\d+)?)\s*شيكل", text)

    return float(match.group(1)) if match else None


# 🎯 فلترة النتائج
def filter_results(objects, question):

    filtered = []

    price_filter = None

    price_match = re.search(r"(\d+)\s*شيكل", question)

    if price_match:
        price_filter = float(price_match.group(1))

    for obj in objects:

        text = obj.properties.get("text", "")
        text = clean_text(text)

        price = extract_price(text)

        # ✅ فلترة السعر
        if price_filter is not None and price != price_filter:
            continue

        filtered.append(text)

    return filtered


# ✨ تنسيق الرد
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


# 🌸 شخصية المساعد
SYSTEM_PROMPT = """
أنت مساعد ذكي خاص بمتجر ورود وهدايا فقط.

مهمتك:
- مساعدة العملاء في اختيار البوكيهات والهدايا
- اقتراح منتجات مناسبة
- الإجابة عن الأسعار والألوان والمناسبات

إذا كان السؤال خارج نطاق الورد أو المتجر:
لا تجب على السؤال.

بدلاً من ذلك قل:
"أنا مساعد مختص بالورود والهدايا 🌸
يمكنني مساعدتك في البوكيهات والهدايا والتنسيقات 😊"

طريقة الرد:
- كن ودودًا
- اجعل الرد طبيعيًا
- افتح حوار مع العميل
- اسأل سؤالاً يساعده يكمل الحديث
"""


@app.post("/chat")
def chat(req: ChatRequest):

    question = req.question.strip()

    # ✅ منع الأسئلة خارج النطاق
    if not any(word in question for word in flower_keywords):

        return {
            "question": question,
            "answer": "أنا مساعد مختص بالورود والهدايا 🌸\nيمكنني مساعدتك في البوكيهات والهدايا والتنسيقات 😊"
        }

    # ✅ Retrieve
    results = collection.query.near_text(
        query=question,
        limit=20
    )

    # ✅ فلترة
    filtered_texts = filter_results(
        results.objects,
        question
    )

    # ❌ لا يوجد نتائج
    if not filtered_texts:

        return {
            "question": question,
            "answer": "لا توجد منتجات مطابقة حالياً 🌸\nهل تفضل لوناً معيناً أو مناسبة محددة لنقترح عليك خيارات أخرى؟ 😊"
        }

    context = "\n\n".join(filtered_texts)

    # ✅ Prompt
    prompt = f"""
استخدم فقط المعلومات التالية للإجابة.

المعلومات:
{context}

السؤال:
{question}

مهم:
- لا تخترع منتجات
- استخدم المعلومات فقط
- كن ودوداً
- افتح حواراً مع العميل
"""

    # ✅ GPT
    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_answer = response.choices[0].message.content

    answer = format_answer(raw_answer)

    return {
        "question": question,
        "answer": answer,
        "sources_used": len(results.objects),
        "filtered_results": len(filtered_texts)
    }
