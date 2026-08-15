from flask import render_template, Blueprint, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import func, extract
import calendar
from datetime import datetime, timedelta
from app import db
from app.models import Product, ProductVariant, Order, OrderItem, Category

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        # 1. بيانات المخزون
        products = Product.query.all()
        low_stock_variants = ProductVariant.query.filter(ProductVariant.quantity <= 10).all()
        low_stock_count = len(low_stock_variants)

        # 2. البيانات المالية
        total_revenue = db.session.query(
            func.sum(OrderItem.price_per_unit * OrderItem.quantity_ordered)
        ).select_from(OrderItem).join(Order).filter(Order.status == 'approved').scalar() or 0

        # 3. الطلبات المعلقة
        pending_orders = db.session.query(OrderItem)\
            .select_from(OrderItem)\
            .join(Order, OrderItem.order_id == Order.id)\
            .filter(Order.status == 'pending')\
            .all()

        # 4. المبيعات الأخيرة
        recent_sales = db.session.query(OrderItem)\
            .select_from(OrderItem)\
            .join(Order, OrderItem.order_id == Order.id)\
            .filter(Order.status == 'approved')\
            .order_by(Order.date_ordered.desc())\
            .limit(5)\
            .all()

        # 5. إحصائيات الأصناف و AI
        total_categories = Category.query.count()

        avg_quality = db.session.query(func.avg(Product.ai_overall_quality_index)).scalar() or 0
        avg_quality_percentage = round(avg_quality, 1)

        defective_fabrics_count = Product.query.filter_by(ai_defects_detected=True).count()

        # 6. بيانات الرسم البياني — مبيعات آخر 6 أشهر
        today = datetime.now()
        six_months_ago = today - timedelta(days=180)

        monthly_sales_raw = db.session.query(
            extract('month', Order.date_ordered).label('month'),
            func.sum(OrderItem.quantity_ordered).label('total_qty')
        ).join(OrderItem, Order.id == OrderItem.order_id)\
         .filter(Order.status == 'approved')\
         .filter(Order.date_ordered >= six_months_ago)\
         .group_by(extract('month', Order.date_ordered))\
         .order_by(extract('month', Order.date_ordered))\
         .all()

        month_names = [
            'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
            'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
        ]

        # بناء قائمة الأشهر الـ6 الأخيرة بالترتيب مع ضمان ظهور الأشهر الفارغة بصفر
        months_range = []
        for i in range(5, -1, -1):
            d = today - timedelta(days=30 * i)
            months_range.append(d.month)

        sales_by_month = {int(r.month): int(r.total_qty or 0) for r in monthly_sales_raw}

        chart_labels = [month_names[m - 1] for m in months_range]
        chart_data   = [sales_by_month.get(m, 0) for m in months_range]

        return render_template(
            'dashboard.html',
            products=products,
            low_stock_variants=low_stock_variants,
            low_stock_count=low_stock_count,
            total_profit=total_revenue,
            pending_orders=pending_orders,
            recent_sales=recent_sales,
            total_categories=total_categories,
            avg_quality_percentage=avg_quality_percentage,
            defective_fabrics_count=defective_fabrics_count,
            chart_labels=chart_labels,
            chart_data=chart_data,
        )

    except Exception as e:
        print(f"Dashboard Error: {e}")
        flash("حدث خطأ أثناء تحميل لوحة التحكم.", "danger")
        return render_template(
            'dashboard.html',
            products=[],
            low_stock_variants=[],
            low_stock_count=0,
            total_profit=0,
            pending_orders=[],
            recent_sales=[],
            total_categories=0,
            avg_quality_percentage=0,
            defective_fabrics_count=0,
            chart_labels=[],
            chart_data=[],
        )