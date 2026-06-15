import os
import uuid
import json
from app.models import Product, db 
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash,session ,jsonify
from flask_login import login_required
from sqlalchemy import func
from flask import request 
from app.ai_service import analyze_fabric_image
from sqlalchemy.orm import joinedload 
from datetime import datetime 
from app import db
from app.models import User, Product, ProductVariant, Order, OrderItem, Customer, SupplyLog
from werkzeug.utils import secure_filename
# تم تصحيح البلوبرينت ليعمل بسلاسة
inventory_bp = Blueprint('inventory', __name__)

UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

COLOR_MAP = {
    'أحمر': '#ff0000', 'ازرق': '#0000ff', 'أزرق': '#0000ff',
    'اخضر': '#00ff00', 'أخضر': '#00ff00',
    'أسود': '#000000', 'اسود': '#000000',
    'أبيض': '#ffffff', 'ابيض': '#ffffff',
    'أصفر': '#ffff00', 'اصفر': '#ffff00',
    'رمادي': '#808080', 'بني': '#8b4513',
    'كحلي': '#000080', 'زهري': '#ffc0cb'
}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# =========================
# SHOP (CUSTOMER VIEW)
# =========================
@inventory_bp.route('/')
@inventory_bp.route('/shop')
def customer_shop():
    # الفلتر هنا يضمن أن الأقمشة المؤرشفة (is_active=False) لا تظهر للزبون
    products = Product.query.filter_by(is_active=True).all()
    cart = session.get('cart', {})
    return render_template('inventory/shop.html', products=products, cart=cart)
# =========================
# ADD TO CART
# =========================
@inventory_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    # 1. استلام البيانات من الـ JavaScript (AJAX)
    variant_id = request.form.get('variant_id')
    try:
        quantity_ordered = float(request.form.get('quantity', 0.0))
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid quantity"}), 400

    if not variant_id or quantity_ordered <= 0:
        return jsonify({"status": "error", "message": "Invalid input"}), 400
    # 2. جلب تفاصيل القماش
    variant = ProductVariant.query.get_or_404(variant_id)
    
    # 3. إدارة السلة في الـ Session
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    current_in_cart = cart.get(str(variant_id), 0.0)
    total_requested = current_in_cart + quantity_ordered

    # 4. التحقق من المخزون
    if variant.quantity < total_requested:
        return jsonify({"status": "error", "message": f"Only {variant.quantity}m available"}), 400

    # 5. حفظ البيانات
    session['variant_info_' + str(variant_id)] = f"{variant.product.name} - {variant.color_name}"
    cart[str(variant_id)] = total_requested
    session['cart'] = cart
    session.modified = True
    print("CART =", session.get('cart'))
    # 6. الرد بنجاح (بدون Reload)
    return jsonify({
        "status": "success", 
        "new_count": len(cart), 
        "message": "Added to cart successfully!"
    })
# =========================
# REMOVE FROM CART 
# =========================
@inventory_bp.route('/cart/remove/<string:variant_id>', methods=['POST'])
def remove_from_cart(variant_id):
    # التأكد من وجود السلة في السيشن
    if 'cart' in session:
        # حذف المنتج من قاموس السلة
        if variant_id in session['cart']:
            session['cart'].pop(variant_id)
            # حذف معلومات المنتج المرتبطة (الاسم واللون)
            session.pop('variant_info_' + str(variant_id), None)
            # إعلام Flask بأن السيشن تغيرت
            session.modified = True
    
    # إرجاع العدد الجديد للسلة بتنسيق JSON
    # هذا الرقم هو ما تستخدمه دالة JavaScript لتحديث العداد في الـ Navbar
    return jsonify({
        "status": "success", 
        "new_count": len(session.get('cart', {}))
    })
# =========================
# CART CHECKOUT
# =========================
@inventory_bp.route('/cart/checkout', methods=['POST'])
def cart_checkout():

    customer_name = request.form.get(
        'customer_name'
    )

    cart = session.get('cart', {})

    if not customer_name or not cart:

        flash(
            'Cart is empty or customer name missing.',
            'danger'
        )

        return redirect(
            url_for('inventory.customer_shop')
        )

    # =========================
    # STOCK VALIDATION
    # =========================

    for variant_id_str, qty in cart.items():

        variant = ProductVariant.query.get(
            int(variant_id_str)
        )

        if not variant:

            flash(
                'Product variant not found.',
                'danger'
            )

            return redirect(
                url_for('inventory.customer_shop')
            )

        if variant.quantity < float(qty):

            flash(
                f'Insufficient stock for '
                f'{variant.product.name} - '
                f'{variant.color_name}',
                'danger'
            )

            return redirect(
                url_for('inventory.customer_shop')
            )

    # =========================
    # CREATE / GET CUSTOMER
    # =========================

    customer = Customer.query.filter_by(
        name=customer_name
    ).first()

    if not customer:

        customer = Customer(
            name=customer_name
        )

        db.session.add(customer)
        db.session.flush()

    # =========================
    # CREATE ORDER
    # =========================

    new_order = Order(
        customer_id=customer.id,
        status='pending'
    )

    db.session.add(new_order)
    db.session.flush()

    # =========================
    # CREATE ORDER ITEMS
    # =========================

    for variant_id_str, qty in cart.items():

        variant = ProductVariant.query.get(
            int(variant_id_str)
        )

        order_item = OrderItem(
            order_id=new_order.id,
            variant_id=variant.id,
            quantity_ordered=float(qty),
            price_per_unit=variant.product.selling_price
        )

        db.session.add(order_item)

    db.session.commit()

    # =========================
    # CLEAR CART
    # =========================

    for variant_id_str in cart.keys():

        session.pop(
            'variant_info_' + str(variant_id_str),
            None
        )

    session.pop('cart', None)

    flash(
        'Order submitted successfully and waiting for factory approval.',
        'success'
    )

    return redirect(
        url_for('inventory.customer_shop')
    )
#==========================================
# APPROVE ORDER
# ==========================================
@inventory_bp.route('/approve_order/<int:order_id>', methods=['POST'])
@login_required
def approve_order(order_id):

    order = Order.query.get_or_404(order_id)

    # already approved
    if order.status == 'approved':

        flash('Order already approved', 'info')
        return redirect(url_for('main.dashboard'))

    # reduce stock now
    for item in order.items:

        variant = item.variant

        if variant.quantity < item.quantity_ordered:

            flash(
                f'Not enough stock for {variant.product.name} - {variant.color_name}',
                'danger'
            )

            return redirect(url_for('main.dashboard'))

        variant.quantity -= item.quantity_ordered

    order.status = 'approved'

    db.session.commit()

    flash('Order approved and shipped successfully', 'success')

    return redirect(url_for('main.dashboard'))
# =========================
# PRODUCTS LIST
# =========================
@inventory_bp.route('/products')
@login_required
def list_products():
    filter_type = request.args.get('filter')
    
    if filter_type == 'low_stock':
        # تشخيص: هل هناك أي متغيرات كميتها <= 10 فعلاً؟
        all_variants = ProductVariant.query.all()
        for v in all_variants:
            print(f"DEBUG: Variant {v.color_name} has quantity: {v.quantity}")
        
        # الاستعلام الفعلي
        products = Product.query.join(Product.variants).filter(ProductVariant.quantity <= 10).distinct().all()
        print(f"DEBUG: Found {len(products)} products with low stock")
        
    else:
        products = Product.query.all()
        
    return render_template('inventory/list_products.html', products=products, filter_type=filter_type)
# =========================
# ADD PRODUCT (FULL CORRECTED VERSION)
# =========================
@inventory_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form.get('name', '').strip()
        product = Product.query.filter(Product.name.ilike(product_name)).first()

        # 1. معالجة بيانات المنتج الأساسية
        if product:
            product.description = request.form.get('description')
            product.selling_price = float(request.form.get('selling_price', 0))
            product.cost_price_per_meter = float(request.form.get('cost_price_per_meter', 0))
        else:
            product = Product(
                name=product_name,
                description=request.form.get('description'),
                selling_price=float(request.form.get('selling_price', 0)),
                cost_price_per_meter=float(request.form.get('cost_price_per_meter', 0))
            )
            db.session.add(product)
            db.session.flush() # للحصول على product.id

        # 2. معالجة صورة القماش الرئيسية (استخدام متغير فريد main_filename)
        if 'image' in request.files:
            image = request.files['image']
            if image and image.filename and allowed_file(image.filename):
                main_filename = secure_filename(image.filename)
                image.save(os.path.join(UPLOAD_FOLDER, main_filename))
                # لا نغير الصورة إلا إذا كانت فارغة أو القماش جديد
                if not product.image_file or product.image_file == 'default.jpg':
                    product.image_file = main_filename

        # 3. معالجة الرسومات / الألوان (Variants)
        variant_names = request.form.getlist('color_names[]')
        quantities = request.form.getlist('color_quantities[]')
        variant_images = request.files.getlist('variant_images[]')

        for index, variant_name in enumerate(variant_names):
            variant_name = variant_name.strip()
            if not variant_name:
                continue

            quantity = float(quantities[index] if index < len(quantities) else 0)
            
            # معالجة صورة الديسان (استخدام image_filename منفصل)
            image_filename = None
            if index < len(variant_images) and variant_images[index].filename:
                image_file = variant_images[index]
                image_filename = f"variant_{product.id}_{index}_{secure_filename(image_file.filename)}"
                image_file.save(os.path.join(UPLOAD_FOLDER, image_filename))

            # البحث عن الديسان أو إضافته
            existing_variant = ProductVariant.query.filter_by(
                product_id=product.id, color_name=variant_name
            ).first()

            if existing_variant:
                existing_variant.quantity += quantity
                if image_filename:
                    existing_variant.image_filename = image_filename
            else:
                new_variant = ProductVariant(
                    product_id=product.id,
                    color_name=variant_name,
                    quantity=quantity,
                    image_filename=image_filename
                )
                db.session.add(new_variant)

        # 4. تسجيل المورد (SupplyLog)
        partner_name = request.form.get('partner_name')
        if partner_name:
            supply = SupplyLog(
                product_id=product.id,
                partner_name=partner_name,
                supplied_quantity=sum(float(q or 0) for q in quantities),
                cost_price_at_purchase=float(request.form.get('source_cost_price', 0)),
                notes=request.form.get('source_notes')
            )
            db.session.add(supply)

        db.session.commit()
        flash('Fabric batch saved successfully', 'success')
        return redirect(url_for('inventory.list_products'))

    return render_template('inventory/add_product.html')
#=========================
# EDIT PRODUCT (MODIFIED FOR IMAGE DESIGNS)
# =========================
@inventory_bp.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    # استخدام joinedload لجلب الألوان/الصور مع المنتج فوراً لتحسين الأداء
    product = Product.query.options(joinedload(Product.variants)).get_or_404(id)

    if request.method == 'POST':
        # 1. تحديث الأسعار (البيانات الأساسية)
        product.cost_price_per_meter = float(request.form.get('cost_price_per_meter') or 0)
        product.selling_price = float(request.form.get('selling_price') or 0)
        
        # 2. تحديث كميات الديسانات الموجودة (عبر الصور)
        for variant in product.variants:
            qty_input = request.form.get(f'qty_variant_{variant.id}')
            if qty_input is not None:
                variant.quantity = float(qty_input)

        # 3. معالجة إضافة ديسان جديد (صورة)
        if 'new_variant_image' in request.files:
            file = request.files['new_variant_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # حفظ الصورة في المجلد
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                design_name = request.form.get('new_variant_name') or "unnamed design"
                # إضافة ديسان جديد
                new_variant = ProductVariant(
                    product_id=product.id,
                    color_name=design_name, # يمكن تركه افتراضياً أو تسميته باسم الملف
                    image_filename=filename,
                    quantity=float(request.form.get('new_variant_qty') or 0)
                )
                db.session.add(new_variant)

        db.session.commit()
        flash("Product and design specifications updated successfully", "success")
        return redirect(url_for('inventory.list_products'))

    return render_template('inventory/edit_product.html', product=product)
# =========================
# SALES HISTORY
# =========================
@inventory_bp.route('/sales/history')
@login_required
def sales_history():
    from app.models import Order
    # نستخدم joinedload(Order.customer) لضمان جلب الزبون مع كل طلب
    # ونضيف joinedload(Order.items) أيضاً لتسريع عرض الأصناف
    orders = Order.query.options(
        joinedload(Order.customer),
        joinedload(Order.items).joinedload(OrderItem.variant)
    ).order_by(Order.date_ordered.desc()).all()
    
    return render_template('inventory/sales_history.html', orders=orders)
#=============================
#customer_details
#============================
@inventory_bp.route('/customer/<int:customer_id>')
@login_required
def customer_details(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = customer.orders 
    total_spent = sum(order.total_price for order in orders)
    
    # يجب إرسال المتغير now لصفحة الـ HTML
    return render_template('inventory/customer_report.html', 
                           customer=customer, 
                           orders=orders, 
                           total_spent=total_spent,
                           now=datetime.now()) # هذا السطر هو الحل لخطأ 'now' في التقرير
# =========================
# ARCHIVE/UNARCHIVE PRODUCT
# =========================
@inventory_bp.route('/product/toggle_archive/<int:id>', methods=['POST'])
@login_required
def toggle_archive(id):
    product = Product.query.get_or_404(id)
    # تغيير الحالة: إذا كان True يصبح False (مؤرشف)، والعكس صحيح
    product.is_active = not product.is_active
    db.session.commit()
    
    status = "archived" if not product.is_active else "restored"
    flash(f'Product "{product.name}" has been {status} successfully.', 'success')
    return redirect(url_for('inventory.list_products'))  
#=================
#list source
#====================      
@inventory_bp.route('/sources')
@login_required
def list_sources():
    # جلب كل سجلات الشراء والمصادر مرتبة من الأحدث للأقدم
    all_supplies = SupplyLog.query.order_by(SupplyLog.purchase_date.desc()).all()
    return render_template('inventory/list_sources.html', supplies=all_supplies)
#================    
@inventory_bp.route('/product/customs/<filename>')
@login_required
def view_customs(filename):
    try:
        # تأكد أن UPLOAD_FOLDER معرف عندك بالملف ويشير لمجلد حفظ الملفات
        return send_from_directory(uploads, filename)
    except FileNotFoundError:
        abort(404, description="Customs document file not found on core storage.")    
@inventory_bp.route('/product/search')
@login_required
def search_products():

    term = request.args.get('q', '').strip()

    if not term:
        return jsonify([])

    products = Product.query.filter(
        Product.name.ilike(f"%{term}%")
    ).limit(10).all()

    return jsonify([
        product.name
        for product in products
    ])        
@inventory_bp.route('/product/details/<string:name>')
@login_required
def product_details(name):

    product = Product.query.filter(
        Product.name.ilike(name)
    ).first()

    if not product:
        return jsonify({})

    return jsonify({
        "id": product.id,
        "name": product.name,
        "description": product.description or "",
        "selling_price": product.selling_price,
        "cost_price_per_meter": product.cost_price_per_meter,
    })    
@inventory_bp.route('/cart')
def view_cart():
    # هذا السطر سيطبع محتوى السلة في الـ Terminal عند دخول صفحة السلة
    print("DEBUG: View Cart - Session Data:", session.get('cart'))
    
    # تأكد أنك لا تعيد تعريف السلة هنا
    cart = session.get('cart', {})
    
    return render_template('cart.html', cart=cart)    
@inventory_bp.route('/financial-report')
@login_required
def financial_report():
    # استعلام الأرباح
    total_revenue = db.session.query(
        func.sum(OrderItem.price_per_unit * OrderItem.quantity_ordered)
    ).join(Order).filter(Order.status == 'approved').scalar() or 0
    
    # استعلام الطلبات المعتمدة
    approved_orders = Order.query.filter_by(status='approved').all()
    
    # تأكد من المسار الصحيح للملف
    return render_template('inventory/financial_report.html', 
                           orders=approved_orders, 
                           total_revenue=total_revenue)

@inventory_bp.route('/fix-database')
def fix_database():
    from app.models import Order
    # جلب جميع الطلبات التي ليس لها زبون
    orphaned_orders = Order.query.filter(Order.customer_id == None).all()
    count = len(orphaned_orders)
    
    for order in orphaned_orders:
        db.session.delete(order)
    
    db.session.commit()
    return f"تم حذف {count} طلب تالف بنجاح! يمكنك الآن العودة لصفحة المبيعات."
@inventory_bp.route('/orders/pending')
@login_required
def pending_orders():
    # جلب الطلبات المعلقة فقط من قاعدة البيانات
    # افترضنا أن لديك علاقة تربط Order بـ OrderItem
    pending_items = OrderItem.query.join(Order).filter(Order.status == 'pending').all()
    print(f"DEBUG: Found {len(pending_items)} pending orders")
    
    return render_template('inventory/pending_orders.html', pending_items=pending_items)    
#-------------------------------------------------------------------------------------------------------------------
#AI    
#-------------------------------------------------------------------------------------------------------------------
@inventory_bp.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        # التحقق من وجود ملف في الطلب
        if 'file' not in request.files:
            return "لم يتم رفع ملف", 400
        
        file = request.files['file']
        if file.filename == '':
            return "لم يتم اختيار صورة", 400

        if file:
            # حفظ الصورة في المجلد الذي أنشأناه سابقاً
            upload_folder = 'app/static/uploads'
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            # استدعاء دالة الذكاء الاصطناعي التي كتبناها
            try:
                ai_result = analyze_fabric_image(file_path)
                # تمرير النتيجة إلى صفحة المعاينة (سننشئها في الخطوة الخامسة)
                return render_template('inventory/preview.html', result=ai_result, image_name=file.filename)
            except Exception as e:
                return f"حدث خطأ أثناء التحليل: {str(e)}"
            
    return render_template('inventory/upload.html')
#---------------------------------------------
#save
#--------------------------------------------
@inventory_bp.route('/save-product', methods=['POST'])
def save_product():
    try:
        # استلام البيانات من فورم preview.html
        name = request.form.get('name')
        ai_analysis_json = request.form.get('ai_analysis_json')
        
        # تحويل النص القادم من الفورم إلى JSON (Python Dict)
        analysis_data = json.loads(ai_analysis_json) if ai_analysis_json else None
        
        # إنشاء منتج جديد وتخزين بيانات الـ AI فيه
        new_product = Product(
            name=name,
            ai_analysis=analysis_data
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        flash('تم حفظ المنتج ونتائج التحليل الذكي بنجاح! 🎉', 'success')
        return redirect(url_for('inventory.list_products'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء حفظ المنتج: {str(e)}', 'danger')
        return redirect(url_for('inventory.analyze'))
#-----------------------
@inventory_bp.route('/products')
def list_product():
    # جلب جميع المنتجات من قاعدة البيانات لعرضها للمدير
    products = Product.query.all()
    return render_template('inventory/products_list.html', products=products)        