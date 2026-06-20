from app import create_app, db
from dotenv import load_dotenv

# تحميل المتغيرات
load_dotenv()

# إنشاء التطبيق باستخدام الدالة
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)