import os
import uuid
from io import BytesIO
from google import genai
from google.genai import types
from PIL import Image
from flask import current_app

# مجلد حفظ صور المعاينة المولّدة (فرعي من مجلد الرفع الأساسي)
MOCKUPS_SUBFOLDER = 'mockups'
USAGE_SLUG_MAX_LEN = 40


def slugify_usage(usage_type):
    """
    يحول نص الاستخدام (عربي عادة) إلى اسم ملف آمن (slug) عشان نستخدمه
    بتسمية الصورة المخزّنة ولإعادة استخدام (cache) نفس الصورة بدل توليدها من جديد.
    """
    safe_chars = []
    for ch in usage_type.strip():
        if ch.isalnum():
            safe_chars.append(ch)
        elif ch in (' ', '-', '_'):
            safe_chars.append('_')
    slug = ''.join(safe_chars) or 'usage'
    return slug[:USAGE_SLUG_MAX_LEN]


def generate_fabric_mockup(image_path, usage_type, fabric_type=None, save_filename=None):
    """
    يولّد صورة AI فوتوغرافية توضح شكل المنتج النهائي (usage_type: قميص، ستارة، فستان...)
    لو تم تصنيعه من قماش الصورة المرفقة (image_path)، باستخدام موديل Gemini 3.1 Flash Image
    (المعروف بـ Nano Banana 2).

    يرجع المسار النسبي للصورة المولّدة داخل app/static/uploads (مثلاً: 'mockups/xxx.png')
    أو None في حال فشل التوليد.
    """
    try:
        api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("Error: GEMINI_API_KEY is not configured.")
            return None

        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return None

        client = genai.Client(api_key=api_key)
        source_img = Image.open(image_path)

        fabric_desc = f" (fabric type: {fabric_type})" if fabric_type else ""
        prompt = (
            f"Using the exact texture, pattern, and colors visible in this fabric reference "
            f"image{fabric_desc}, generate a single photorealistic product photograph of a "
            f"finished '{usage_type}' item made entirely from this fabric. "
            f"Requirements: studio lighting, clean plain neutral background, professional "
            f"e-commerce product photography style, the fabric pattern and colors in the "
            f"generated item must closely match the reference image. Do not add any text, "
            f"logo, or watermark to the image."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[prompt, source_img],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        for part in response.parts:
            if part.inline_data is not None:
                generated_image = Image.open(BytesIO(part.inline_data.data))

                upload_root = os.path.dirname(image_path.rstrip('/')) if not save_filename else os.path.join(
                    'app', 'static', 'uploads'
                )
                mockups_folder = os.path.join('app', 'static', 'uploads', MOCKUPS_SUBFOLDER)
                os.makedirs(mockups_folder, exist_ok=True)

                filename = save_filename or f"mockup_{uuid.uuid4().hex[:12]}.png"
                save_path = os.path.join(mockups_folder, filename)

                # الصورة المولدة أحياناً بصيغة RGBA، نحولها لـ RGB قبل الحفظ كـ PNG بأمان
                if generated_image.mode in ("RGBA", "P"):
                    generated_image = generated_image.convert("RGB")
                generated_image.save(save_path)

                return f"{MOCKUPS_SUBFOLDER}/{filename}"

        print("No image part returned from Gemini image model.")
        return None

    except Exception as e:
        print(f"Mockup generation error: {str(e)}")
        return None
