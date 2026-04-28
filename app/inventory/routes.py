import os
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash
from werkzeug.utils import secure_filename

from app.models import Product
from app import db


inventory_bp = Blueprint("inventory", __name__)

# 📦 عرض المنتجات
@inventory_bp.route('/products')
def list_products():
    # استقبال قيمة الفلتر من الرابط
    stock_filter = request.args.get('filter')
    
    if stock_filter == 'low':
        # إذا كان الفلتر "low" نجلب فقط الأقمشة القليلة
        products = Product.query.filter(Product.quantity < 5).all()
    else:
        # الحالة الطبيعية تجلب كل المنتجات
        products = Product.query.all()
        
    return render_template('inventory/list_products.html', products=products)
# ➕ إضافة منتج
@inventory_bp.route("/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        quantity = request.form.get("quantity")
        cost = request.form.get("cost_price", 0)
        selling = request.form.get("selling_price", 0)

        file = request.files.get("image")
        filename = "default.jpg"
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # استخدام المسار الديناميكي
            upload_path = os.path.join(current_app.static_folder, 'uploads', filename)
            file.save(upload_path)

        product = Product(
            name=name,
            description=description,
            quantity=int(quantity) if quantity else 0,
            cost_price=float(cost) if cost else 0.0,
            selling_price=float(selling) if selling else 0.0,
            image_file=filename
        )

        db.session.add(product)
        db.session.commit()
        flash('New fabric added successfully!', 'success')
        return redirect(url_for("inventory.list_products"))

    return render_template("inventory/add_product.html")

# 📝 تعديل منتج
@inventory_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.quantity = int(request.form.get('quantity'))
        product.cost_price = float(request.form.get('cost_price'))
        product.selling_price = float(request.form.get('selling_price'))
        
        file = request.files.get('image')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # توحيد طريقة حفظ المسار
            upload_path = os.path.join(current_app.static_folder, 'uploads', filename)
            file.save(upload_path)
            product.image_file = filename
            
        db.session.commit()
        flash('Fabric updated successfully!', 'success')
        return redirect(url_for('inventory.list_products'))
    
    return render_template('inventory/edit_product.html', product=product)
@inventory_bp.route('/delete/<int:id>', methods=['POST'])
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    # (اختياري) حذف صورة المنتج من المجلد الفعلي لتوفير المساحة
    if product.image_file and product.image_file != 'default.jpg':
        image_path = os.path.join(current_app.static_folder, 'uploads', product.image_file)
        if os.path.exists(image_path):
            os.remove(image_path)
            
    db.session.delete(product)
    db.session.commit()
    
    flash(f'Product "{product.name}" has been deleted.', 'danger')
    return redirect(url_for('inventory.list_products'))    
@inventory_bp.route('/make_sale', methods=['POST'])
def make_sale():
    from app.models import Product, Sale
    product_id = request.form.get('product_id')
    qty = int(request.form.get('quantity'))
    
    product = Product.query.get_or_404(product_id)
    
    if product.quantity >= qty:
        # تنقيص الكمية من المخزن
        product.quantity -= qty
        
        # تسجيل عملية البيع في الجدول الجديد
        new_sale = Sale(
            product_id=product.id,
            quantity_sold=qty,
            total_price=qty * product.selling_price,
            customer_name=request.form.get('customer_name')
        )
        
        db.session.add(new_sale)
        db.session.commit()
        flash(f'Done! Sold {qty} units of {product.name}', 'success')
    else:
        flash('Not enough stock!', 'danger')
        
    return redirect(url_for('inventory.list_products'))
@inventory_bp.route('/sales-history')
def sales_history():
    from app.models import Sale
    # جلب المبيعات مرتبة من الأحدث للأقدم
    sales = Sale.query.order_by(Sale.date_sold.desc()).all()
    # تأكدي من المسار إذا كان داخل مجلد inventory
    return render_template('inventory/sales_history.html', sales=sales)
@inventory_bp.route('/customer/<name>')
def customer_details(name):
    from app.models import Sale
    # جلب جميع مبيعات هذا الزبون بالاسم
    customer_sales = Sale.query.filter_by(customer_name=name).all()
    
    # حساب إجمالي ما أنفقه الزبون
    total_spent = sum(sale.total_price for sale in customer_sales)
    
    return render_template('inventory/customer_report.html', 
                           name=name, 
                           sales=customer_sales, 
                           total_spent=total_spent)   