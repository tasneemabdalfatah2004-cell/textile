import google.generativeai as genai
import PIL.Image
import json
import os

# 🔑 تأكد من الحصول على مفتاح يبدأ بـ AIzaSy من Google AI Studio
API_KEY = ""
# إعداد المكتبة بالمفتاح الصحيح
genai.configure(api_key=API_KEY)

def analyze_fabric_image(image_path):
    # 🎯 استخدام الاسم الكامل للموديل لتجنب خطأ 404
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    
    # فتح صورة القماش المرفوعة
    img = PIL.Image.open(image_path)
    
    prompt = """
    أنت خبير منسوجات محترف. قم بتحليل هذه الصورة واستخرج الخصائص التالية في صيغة JSON فقط وبدون أي نصوص إضافية:
    {
        "fabric_type": "نوع القماش",
        "thickness": "السماكة",
        "quality_score": 85,
        "recommended_usage": "الاستخدام المقترح"
    }
    """
    
    # إرسال الصورة والطلب للـ AI
    response = model.generate_content([prompt, img])
    
    # تنظيف الرد لضمان استخراج الـ JSON بشكل نقي
    text = response.text.strip()
    if text.startswith('```json'):
        text = text[7:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    
    return json.loads(text)