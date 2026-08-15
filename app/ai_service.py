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

        # 🌟 الـ Prompt الهندسي: المفاتيح مطابقة تماماً لأسماء الحقول المستخدمة
        # في القالب fabric_ai_report.html وفي دالة save_product (بدون بادئة ai_) 🌟
        prompt = """
        You are an expert textile engineer, quality control AI, and fabric market analyst. Analyze this fabric texture image and extract exactly 16 specialized structural and commercial metrics.
        CRITICAL RULE: The JSON KEYS must be exactly as specified below in English, but the VALUES (descriptions, types, instructions) MUST BE WRITTEN IN PERFECT PROFESSIONAL ARABIC.

        You must respond ONLY with a raw valid JSON object. Do not include markdown blocks or any conversational prose.

        The JSON must match this structure exactly:
        {
            "fabric_type": "نوع القماش الدقيق باللغة العربية، مثل: جاكار، مخمل، قطن مبرد، ستان حرير",
            "thickness": "تصنيف سماكة القماش، مثل: خفيف الوزن، متوسط الوزن، ثقيل الوزن",
            "weaving_density": "تقدير كثافة وتداخل الخيوط، مثل: كثافة عالية جداً، كثافة متوسطة، كثافة منخفضة",
            "weaving_quality_score": 85,
            "pattern_style": "وصف النمط والزخارف الدقيقة الظاهرة بالنسيج، مثل: أزهار صغيرة متكررة، هندسي، بدون نقشة",
            "texture_feel": "وصف ملمس السطح الخارجي، مثل: ناعم ولامع، خشن الملمس، ناعم وبري",
            "fiber_direction": "اتجاه الألياف الظاهر، مثل: طولي، عرضي، غير منتظم",
            "pile_analysis": "دراسة الوبرة السطحية، مثل: لا يوجد وبرة، وبرة كثيفة قصيرة، وبرة طويلة ناعمة",
            "light_reflection": "وصف التضاريس وانعكاس الضوء عن السطح، مثل: لامع عاكس، مطفي، شبه لامع",
            "finishing_quality": "تقييم جودة الحواف والتشطيب النهائي، مثل: تشطيب ممتاز بلا تنسيل، تشطيب متوسط، حواف غير مشغولة",
            "defects_detected": false,
            "defects_details": "تفاصيل العيوب المصنعية المكتشفة باللغة العربية (مثل: وجود تنسيل خيوط، بقعة لونية) أو اكتب 'لا يوجد عيوب' إذا كان النسيج سليماً",
            "defect_locations": "قائمة إحداثيات كل عيب مكتشف بالصورة (اتركها قائمة فارغة [] إذا defects_detected كانت false)، كل عنصر بالقائمة كائن فيه x و y هما النسبة المئوية لموقع مركز العيب بالصورة (0 تعني أقصى اليسار/الأعلى، 100 تعني أقصى اليمين/الأسفل)، مثال: [{\"x\": 35, \"y\": 60}, {\"x\": 70, \"y\": 20}]",
            "recommended_usage": "أبرز الاستخدامات المقترحة مفصولة بفاصلة عربية (،)، مثل: الفساتين السواريه، تنجيد الأثاث الفاخر، الملابس الصيفية",
            "suggested_season": "الموسم الأنسب لاستخدام القماش، مثل: شتوي، صيفي، كل المواسم",
            "overall_quality_index": 85,
            "estimated_price_per_meter": "تقدير عام تقريبي لسعر بيع المتر الواحد بالسوق بالدولار الأمريكي. مهم جداً: احسبي هذا التقدير بناءً على الخصائص المحددة يلي استنتجتيها لهذا القماش بالذات (fabric_type، thickness، weaving_density، overall_quality_index) — قماش خفيف الوزن كثافة منخفضة لازم يطلع بسعر أقل من قماش جاكار كثيف عالي الجودة. لا تعطي نفس الرقم لكل الأقمشة، السعر لازم يتغير فعلياً حسب نوع وجودة هذا القماش تحديداً. بصيغة نطاق سعري مثل: 8 - 12 $ للمتر (تقدير عام تقريبي)"
        }
        Note: weaving_quality_score and overall_quality_index must be integers between 1 and 100. defects_detected must be a boolean (true/false). estimated_price_per_meter must always include the word "تقديري" or "تقدير عام تقريبي" so it is clear this is not a fixed price. defect_locations must be a valid JSON array (use [] when there are no defects), with x and y as numbers between 0 and 100.
        """

        # إرسال الصورة والطلب للـ AI
        response = model.generate_content([prompt, img])

        # تنظيف الرد لضمان استخراج الـ JSON بشكل نقي
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]

        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        # تحويل النص المستلم إلى Dictionary (بقيم عربية ومفاتيح إنجليزية مطابقة للقالب)
        return json.loads(text)

    except json.JSONDecodeError as je:
        print(f"JSON Parsing Error: {je}")
        return {}
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {}
