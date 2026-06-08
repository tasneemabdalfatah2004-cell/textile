from flask import render_template, Blueprint, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta

from app import db
from app.models import Product, ProductVariant, Order, OrderItem

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        # 1. بيانات المخزون (أساسية للمدير)
        products = Product.query.all()
        low_stock_variants = ProductVariant.query.filter(ProductVariant.quantity <= 10).all()
        low_stock_count = len(low_stock_variants)

        # 2. البيانات المالية (مبسطة)
        total_revenue = db.session.query(
            func.sum(OrderItem.price_per_unit * OrderItem.quantity_ordered)
        ).select_from(OrderItem).join(Order).filter(Order.status == 'approved').scalar() or 0

        # 3. الطلبات المعلقة (أهم شيء للمدير يومياً)
        pending_orders = db.session.query(OrderItem)\
            .select_from(OrderItem)\
            .join(Order, OrderItem.order_id == Order.id)\
            .filter(Order.status == 'pending')\
            .all()

        # 4. المبيعات الأخيرة (لإعطاء حركة للوحة)
        recent_sales = db.session.query(OrderItem)\
            .select_from(OrderItem)\
            .join(Order, OrderItem.order_id == Order.id)\
            .filter(Order.status == 'approved')\
            .order_by(Order.date_ordered.desc())\
            .limit(5)\
            .all()

        return render_template(
            'dashboard.html',
            products=products,
            low_stock_variants=low_stock_variants,
            low_stock_count=low_stock_count,
            total_profit=total_revenue,
            pending_orders=pending_orders,
            recent_sales=recent_sales
        )

    except Exception as e:
        print(f"Error: {e}")
        flash("حدث خطأ أثناء تحميل لوحة التحكم.", "danger")
        return render_template('dashboard.html', low_stock_count=0, pending_orders=[], recent_sales=[])