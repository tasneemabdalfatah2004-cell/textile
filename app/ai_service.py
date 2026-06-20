import google.generativeai as genai
import PIL.Image
import json
import os
from dotenv import load_dotenv
from flask import current_app

def analyze_fabric_image(image_path):
    try:
        # 🔑 جلب مفتاح الـ API بأمان من إعدادات Flask أو البيئة المحيطة لتجنب الثغرات الأمنية
        api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("Error: GEMINI_API_KEY is not configured in the application.")
            return None

        # إعداد المكتبة بالمفتاح
        genai.configure(api_key=api_key)

        # 🎯 استخدام الموديل الذي حددته أنت بالتحديد لمشروعك
        model = genai.GenerativeModel('models/gemini-3.1-flash-lite')
        
        # فتح صورة القماش المرفوعة باستخدام PIL
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None
            
        img = PIL.Image.open(image_path)
        
        # 🌟 الـ Prompt الهندسي: المفاتيح بالإنجليزية للكود والقيم باللغة العربية للمناقشة 🌟
        prompt = """
        You are an expert textile engineer and quality control AI. Analyze this fabric texture image and extract exactly 13 specialized structural metrics.
        CRITICAL RULE: The JSON KEYS must be exactly as specified below in English, but the VALUES (descriptions, types, instructions) MUST BE WRITTEN IN PERFECT PROFESSIONAL ARABIC.
        
        You must respond ONLY with a raw valid JSON object. Do not include markdown blocks like
  json ...  
  or any conversational prose.

        The JSON must match this structure exactly:
        {
            "ai_fabric_type": "نوع القماش الدقيق باللغة العربية، مثل: جاكار، مخمل، قطن مبرد، ستان حرير",
            "ai_weave_pattern": "نوع بناء النسيج، مثل: نسج سادة، مبرد، أطلس/ستان، تريكو/محبوك",
            "ai_thread_count_estimation": "تقدير كثافة الخيوط، مثل: كثافة عالية جداً، كثافة متوسطة، كثافة منخفضة",
            "ai_thickness": "تصنيف سماكة القماش، مثل: خفيف الوزن، متوسط الوزن، ثقيل الوزن",
            "ai_stretchability": "مرونة القماش، مثل: غير قابل للتمدد، تمدد منخفض، مرونة عالية جداً",
            "ai_recommended_usage": "أبرز الاستخدامات المقترحة مفصولة بفاصلة، مثل: الفساتين السواريه، تنجيد الأثاث الفاخر، الملابس الصيفية",
            "ai_care_instructions": "تعليمات العناية والغسيل الصارمة، مثل: تنظيف جاف فقط، غسيل آلي بماء بارد، تجنب الكي الحراري المباشر",
            "ai_color_palette": "الألوان السائدة أو أكواد الهكس البديلة للألوان الظاهرة في نقشة النسيج باللغة العربية أو الرموز",
            "ai_texture_smoothness": "وصف ملمس السطح الخارجي، مثل: ناعم ولامع، خشن الملمس، ناعم وبري",
            "ai_overall_quality_index": 85,
            "ai_defects_detected": false,
            "ai_defects_details": "تفاصيل العيوب المصنعية المكتشفة باللغة العربية (مثل: وجود تنسيل خيوط، بقعة لونية) أو اكتب 'لا يوجد عيوب' إذا كان النسيج سليماً",
            "ai_sustainability_rating": "التقييم البيئي والاستدامة للقماش، مثل: ألياف طبيعية مستدامة، ألياف صناعية قياسية، مزيج صديق للبيئة"
        }
        Note: ai_overall_quality_index must be an integer between 1 and 100. ai_defects_detected must be a boolean (true/false).
        """
        
        # إرسال الصورة والطلب للـ AI
        response = model.generate_content([prompt, img])
        
        # تنظيف الرد لضمان استخراج الـ JSON بشكل نقي كما فعلت بكودك الذكي
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
            
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        # تحويل النص المستلم إلى Dictionary (بقيم عربية ومفاتيح إنجليزية سليمة)
        return json.loads(text)

    except json.JSONDecodeError as je:
        print(f"JSON Parsing Error: {je}")
        return {}  # ⬅️ تغيير: أرجع قاموساً فارغاً بدلاً من None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {}  # ⬅️ تغيير: أرجع قاموساً فارغاً بدلاً من None