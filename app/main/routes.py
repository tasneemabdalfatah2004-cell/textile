from flask import render_template, Blueprint, request
from app.models import Product, Sale
from app import db
from sqlalchemy import func

# تأكدي أن هذا الاسم هو المستخدم في ملف init.py لتجنب أخطاء الـ Import
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
def dashboard():
    # جلب إحصائيات المنتجات والمخزن
    products = Product.query.all()
    low_stock_products = Product.query.filter(Product.quantity < 5).all()
    low_stock_count = len(low_stock_products)

    # حساب إجمالي المبيعات (المربع الأحمر)
    total_revenue = db.session.query(func.sum(Sale.total_price)).scalar() or 0
    
    # عدد العمليات (المربع الأخضر)
    total_sales_count = Sale.query.count()
    
    # آخر 5 عمليات للجدول
    recent_sales = Sale.query.order_by(Sale.date_sold.desc()).limit(5).all()

    return render_template('dashboard.html', 
                           products=products, 
                           low_stock_products=low_stock_products, 
                           low_stock_count=low_stock_count,
                           total_profit=total_revenue,
                           total_sales_count=total_sales_count,
                           recent_sales=recent_sales)

@main_bp.route('/analytics')
def analytics():
    # تجهيز بيانات الرسم البياني: اسم القماش وإجمالي مبيعاته
    chart_data = db.session.query(
        Product.name, 
        func.sum(Sale.total_price).label('total')
    ).join(Sale).group_by(Product.name).all()

    labels = [row[0] for row in chart_data]
    values = [float(row[1]) for row in chart_data]

    return render_template('analytics.html', labels=labels, values=values)