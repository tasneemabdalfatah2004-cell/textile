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

    # إنشاء الجداول
    with app.app_context():
        db.create_all()

    return app