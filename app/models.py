from app import db, login_manager
from flask_login import UserMixin
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
# PRODUCT MODEL
# =====================

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text, nullable=True)

    selling_price = db.Column(db.Float, nullable=False, default=0.0)

    cost_price_per_meter = db.Column(db.Float, nullable=False, default=0.0)

    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')

    customs_file = db.Column(db.String(100), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

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

    product_id = db.Column(
        db.Integer,
        db.ForeignKey('product.id'),
        nullable=False
    )

    color_name = db.Column(db.String(100), nullable=False)

    

    quantity = db.Column(db.Float, nullable=False, default=0.0)
    
    # 🌟 التعديل الجديد: تخزين اسم ملف الصورة المرتبط بهذا اللون/النقشة
    image_filename = db.Column(db.String(200), nullable=True)

    order_items = db.relationship('OrderItem', backref='variant', lazy=True)
#===================
#customer
#====================
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # ربط العميل بطلباته
    orders = db.relationship('Order', backref='customer', lazy=True)
# =====================
# ORDER
# =====================
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # استبدال customer_name بـ customer_id
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

    order_id = db.Column(
        db.Integer, 
        db.ForeignKey('order.id'), 
        nullable=False
    )

    # 🌟 تم إصلاح المسافة البادئة هنا
    variant_id = db.Column(
        db.Integer, 
        db.ForeignKey('product_variant.id'), 
        nullable=False
    )

    quantity_ordered = db.Column(db.Float, nullable=False)

    price_per_unit = db.Column(db.Float, nullable=False)
# ==========================================
# SUPPLY LOG / PARTNERS MODEL (جدول المصادر والشركاء الجديد)
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