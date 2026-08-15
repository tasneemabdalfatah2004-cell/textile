import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    
    app = Flask(__name__)

    # إعدادات التطبيق
    app.config['SECRET_KEY'] = 'my_secret_key_12345'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # تهيئة الإضافات
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # صفحة تسجيل الدخول
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # 🌟 هذا السطر السحري يحل خطأ الـ UndefinedError في Jinja2 نهائياً عند دخول صفحة المدير
    app.jinja_env.globals.update(hasattr=hasattr)

    # استيراد وتسجيل الـ Blueprints
    from app.auth.routes import auth_bp
    from app.inventory.routes import inventory_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(main_bp)

    # 🔔 context_processor: يوصل عدد التنبيهات (طلبات معلقة + نقص كمية) لكل صفحة بالموقع
    # عشان الجرس بـ base.html يقدر يعرضهم بأي مكان بدون ما نمررهم يدوياً من كل route
    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        if not current_user.is_authenticated:
            return dict(notif_pending_orders=[], notif_low_stock=[], notif_total_count=0)

        from app.models import Order, ProductVariant

        pending_orders = Order.query.filter_by(status='pending').order_by(Order.date_ordered.desc()).limit(5).all()
        low_stock_variants = ProductVariant.query.filter(ProductVariant.quantity <= 10).limit(5).all()

        pending_orders_count = Order.query.filter_by(status='pending').count()
        low_stock_count = ProductVariant.query.filter(ProductVariant.quantity <= 10).count()

        return dict(
            notif_pending_orders=pending_orders,
            notif_low_stock=low_stock_variants,
            notif_total_count=pending_orders_count + low_stock_count
        )

    # إنشاء الجداول
    with app.app_context():
        db.create_all()

    return app
