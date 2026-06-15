import google.generativeai as genai

# ضع مفتاح الـ API الخاص بك هنا
genai.configure(api_key="ضع_مفتاحك_هنا")

print("الموديلات المتاحة التي تدعم تحليل الصور (generateContent):")
print("-" * 50)

# جلب قائمة الموديلات
for m in genai.list_models():
    # التحقق من أن الموديل يدعم خاصية توليد المحتوى (generateContent)
    if 'generateContent' in m.supported_generation_methods:
        print(f"اسم الموديل: {m.name}")
        print(f"الوصف: {m.description}")
        print("-" * 30)