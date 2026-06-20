from app import db, login_manager
from flask_login import UserMixin
from sqlalchemy.types import JSON
from werkzeug.security import generate_password_hash, check_password_hash

# =====================
# USER MODEL
# =====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# =====================
# CATEGORY MODEL
# =====================
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # مثل: قطن، حرير، شتوي
    description = db.Column(db.Text, nullable=True)
    
    # علاقة وان-تو-ميني مع المنتجات
    products = db.relationship('Product', backref='category_قثم', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


# =====================
# PRODUCT MODEL (المطور للأقمشة والـ AI)
# =====================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # 1. البيانات الأساسية للقماش (Basic Info)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    selling_price = db.Column(db.Float, nullable=False, default=0.0)
    cost_price_per_meter = db.Column(db.Float, nullable=False, default=0.0)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    customs_file = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # ربط المنتج بالصنف الرئيسي
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)

    # 🤖 حقول التحليل الذكي للأقمشة الـ 13 (AI Fabric Metrics)
    ai_fabric_type = db.Column(db.String(100), nullable=True)            # 1. نوع القماش المكتشف
    ai_thickness = db.Column(db.String(50), nullable=True)               # 2. السماكة
    ai_weaving_density = db.Column(db.String(100), nullable=True)         # 3. تحليل الكثافة والنسج
    ai_weaving_quality_score = db.Column(db.Float, nullable=True)        # 4. جودة النسج والتركيب البنيوي
    ai_pattern_style = db.Column(db.String(100), nullable=True)          # 5 و 10. النمط، الطباعة، والزخارف الدقيقة
    ai_texture_feel = db.Column(db.String(50), nullable=True)            # 6. الملمس والاتجاه
    ai_fiber_direction = db.Column(db.String(50), nullable=True)         # 6. اتجاه الألياف
    ai_pile_analysis = db.Column(db.String(100), nullable=True)          # 7. الوبرة والكثافة السطحية
    ai_light_reflection = db.Column(db.String(50), nullable=True)        # 8. التضاريس وانعكاس الضوء
    ai_finishing_quality = db.Column(db.String(100), nullable=True)       # 9. جودة الحواف والتشطيب
    ai_defects_detected = db.Column(db.Boolean, default=False)           # 11. كشف وجود عيوب
    ai_defects_details = db.Column(db.Text, nullable=True)               # 11. تفاصيل العيوب (إن وجدت)
    ai_recommended_usage = db.Column(db.String(100), nullable=True)       # 12. الاستخدام المقترح
    ai_suggested_season = db.Column(db.String(50), nullable=True)         # 12. الموسم المقترح
    ai_overall_quality_index = db.Column(db.Integer, nullable=True, default=100) # 13. التقييم الرقمي الشامل للجودة
    ai_analysis = db.Column(db.JSON, nullable=True)                      # حقل الـ JSON الاحتياطي للبيانات الخام

    # العلاقات ومغيرات المنتج (Variants)
    variants = db.relationship(
        'ProductVariant',
        backref='product',
        lazy=True,
        cascade="all, delete-orphan"
    )

    @property
    def total_quantity(self):
        return sum(v.quantity for v in self.variants)
# =====================
# PRODUCT VARIANT
# =====================
class ProductVariant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    color_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    image_filename = db.Column(db.String(200), nullable=True)

    order_items = db.relationship('OrderItem', backref='variant', lazy=True)


# =====================
# CUSTOMER
# =====================
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    orders = db.relationship('Order', backref='customer', lazy=True)


# =====================
# ORDER
# =====================
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    date_ordered = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

    @property
    def total_price(self):
        return sum(item.quantity_ordered * item.price_per_unit for item in self.items)


# =====================
# ORDER ITEM
# =====================
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id'), nullable=False)
    quantity_ordered = db.Column(db.Float, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)


# ==========================================
# SUPPLY LOG / PARTNERS MODEL
# ==========================================
class SupplyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    partner_name = db.Column(db.String(100), nullable=False)  # اسم الشركة أو الشريك
    supplied_quantity = db.Column(db.Float, nullable=False, default=0.0)  # الكمية الموردة بالمتر
    cost_price_at_purchase = db.Column(db.Float, nullable=False, default=0.0)  # سعر الشراء من المصدر للمتر
    purchase_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())  # وقت الشراء
    notes = db.Column(db.String(250), nullable=True)  # ملاحظات إضافية

    # ربط خلفي مع الموديل الرئيسي
    product = db.relationship('Product', backref=db.backref('supplies', lazy=True, cascade="all, delete-orphan"))    