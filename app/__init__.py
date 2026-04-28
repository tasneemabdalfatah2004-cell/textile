from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app():
    # يجب أن تكون name
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # تسجيل البلوبرنت الخاص بالمخزن
    from app.inventory.routes import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix="/inventory")

    # تسجيل البلوبرنت الخاص بالـ Dashboard (هو الذي سيمسك الصفحة الرئيسية)
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)

    # إضافة ميزة التنبيهات لكل الموقع
    @app.context_processor
    def inject_alerts():
        from app.models import Product
        low_stock = Product.query.filter(Product.quantity < 5).all()
        return dict(low_stock_products=low_stock, low_stock_count=len(low_stock))

    return app
    