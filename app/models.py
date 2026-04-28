from app import db
from datetime import datetime

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, default=0)
    
    # حقول الأسعار
    cost_price = db.Column(db.Float, default=0.0)    
    selling_price = db.Column(db.Float, default=0.0) 
    
    # حقل الصورة
    image_file = db.Column(db.String(100), default='default.jpg')
    
    # حقل وقت الإضافة
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Product('{self.name}', '{self.quantity}', '{self.selling_price}')"

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    # التصحيح هنا: استخدام nullable=True بدلاً من shadow
    customer_name = db.Column(db.String(100), nullable=True) 
    date_sold = db.Column(db.DateTime, default=datetime.utcnow)

    # ربط العلاقة مع جدول المنتجات
    product = db.relationship('Product', backref='sales_records')

    def __repr__(self):
        return f"Sale(Product ID: {self.product_id}, Quantity: {self.quantity_sold}, Total: {self.total_price})"