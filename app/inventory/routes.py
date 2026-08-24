import os
import requests
import uuid
import json
from app.models import Product, db 
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash,session ,jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from flask import request 
from app.ai_service import analyze_fabric_image
from app.ai_mockup_service import generate_fabric_mockup, slugify_usage
from sqlalchemy.orm import joinedload 
from datetime import datetime 
from app import db
from app.models import User, Product, ProductVariant, Order, OrderItem, Customer, SupplyLog ,Category
from werkzeug.utils import secure_filename
# تم تصحيح البلوبرينت ليعمل بسلاسة
inventory_bp = Blueprint('inventory', __name__)

NANOBANANA_API_KEY = os.getenv("NANOBANANA_API_KEY", "YOUR_NANOBANANA_API_TOKEN")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "YOUR_FREE_IMGBB_API_KEY") # Free key for uploading local images

UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

COLOR_MAP = {
    'أحمر': '#ff0000', 'ازرق': '#0000ff', 'أزرق': '#0000ff',
    'اخضر': '#00ff00', 'أخضر': '#00ff00',
    'أسود': '#000000', 'اسود': '#000000',
    'أبيض': '#ffffff', 'ابيض': '#ffffff',
    'أصفر': '#ffff00', 'اصفر': '#ffff00',
    'رمادي': '#808080', 'بني': '#8b4513',
    'كحلي': '#000080', 'زهني': '#ffc0cb'
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
    categories = Category.query.all()
    cart = session.get('cart', {})
    return render_template('inventory/shop.html', products=products, categories=categories, cart=cart)
# =========================
# ADD TO CART
# =========================
@inventory_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    variant_id = request.form.get('variant_id')
    try:
        quantity_ordered = float(request.form.get('quantity', 0.0))
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid quantity"}), 400

    if not variant_id or quantity_ordered <= 0:
        return jsonify({"status": "error", "message": "Invalid input"}), 400
    variant = ProductVariant.query.get_or_404(variant_id)
    
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    current_in_cart = cart.get(str(variant_id), 0.0)
    total_requested = current_in_cart + quantity_ordered

    if variant.quantity < total_requested:
        return jsonify({"status": "error", "message": f"Only {variant.quantity}m available"}), 400

    session['variant_info_' + str(variant_id)] = f"{variant.product.name} - {variant.color_name}"
    cart[str(variant_id)] = total_requested
    session['cart'] = cart
    session.modified = True
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
    if 'cart' in session:
        if variant_id in session['cart']:
            session['cart'].pop(variant_id)
            session.pop('variant_info_' + str(variant_id), None)
            session.modified = True
    
    return jsonify({
        "status": "success", 
        "new_count": len(session.get('cart', {}))
    })
# =========================
# CART CHECKOUT
# =========================
@inventory_bp.route('/cart/checkout', methods=['POST'])
def cart_checkout():

    customer_name = request.form.get('customer_name')
    cart = session.get('cart', {})

    if not customer_name or not cart:
        flash('Cart is empty or customer name missing.', 'danger')
        return redirect(url_for('inventory.customer_shop'))

    for variant_id_str, qty in cart.items():
        variant = ProductVariant.query.get(int(variant_id_str))
        if not variant:
            flash('Product variant not found.', 'danger')
            return redirect(url_for('inventory.customer_shop'))
        if variant.quantity < float(qty):
            flash(f'Insufficient stock for {variant.product.name} - {variant.color_name}', 'danger')
            return redirect(url_for('inventory.customer_shop'))

    customer = Customer.query.filter_by(name=customer_name).first()
    if not customer:
        customer = Customer(name=customer_name)
        db.session.add(customer)
        db.session.flush()

    new_order = Order(customer_id=customer.id, status='pending')
    db.session.add(new_order)
    db.session.flush()

    for variant_id_str, qty in cart.items():
        variant = ProductVariant.query.get(int(variant_id_str))
        order_item = OrderItem(
            order_id=new_order.id,
            variant_id=variant.id,
            quantity_ordered=float(qty),
            price_per_unit=variant.product.selling_price
        )
        db.session.add(order_item)

    db.session.commit()

    for variant_id_str in cart.keys():
        session.pop('variant_info_' + str(variant_id_str), None)
    session.pop('cart', None)

    flash('Order submitted successfully and waiting for factory approval.', 'success')
    return redirect(url_for('inventory.customer_shop'))
#==========================================
# APPROVE ORDER
# ==========================================
@inventory_bp.route('/approve_order/<int:order_id>', methods=['POST'])
@login_required
def approve_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == 'approved':
        flash('Order already approved', 'info')
        return redirect(url_for('main.dashboard'))

    for item in order.items:
        variant = item.variant
        if variant.quantity < item.quantity_ordered:
            flash(f'Not enough stock for {variant.product.name} - {variant.color_name}', 'danger')
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
        products = Product.query.join(Product.variants).filter(ProductVariant.quantity <= 10).distinct().all()
    else:
        products = Product.query.all()
        
    return render_template('inventory/list_products.html', products=products, filter_type=filter_type)
# =========================
# ADD PRODUCT (VERSION WITH CATEGORY & AI METRICS)
# =========================
@inventory_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form.get('name', '').strip()
        product = Product.query.filter(Product.name.ilike(product_name)).first()

        category_id = request.form.get('category_id')
        chosen_category_id = int(category_id) if category_id else None

        if product:
            product.description = request.form.get('description')
            product.selling_price = float(request.form.get('selling_price', 0))
            product.cost_price_per_meter = float(request.form.get('cost_price_per_meter', 0))
            if chosen_category_id:
                product.category_id = chosen_category_id
        else:
            product = Product(
                name=product_name,
                description=request.form.get('description'),
                selling_price=float(request.form.get('selling_price', 0)),
                cost_price_per_meter=float(request.form.get('cost_price_per_meter', 0)),
                category_id=chosen_category_id
            )
            db.session.add(product)
            db.session.flush() # للحصول على product.id

        if 'image' in request.files:
            image = request.files['image']
            if image and image.filename and allowed_file(image.filename):
                main_filename = secure_filename(image.filename)
                full_image_path = os.path.join(UPLOAD_FOLDER, main_filename)
                image.save(full_image_path)
                
                if not product.image_file or product.image_file == 'default.jpg':
                    product.image_file = main_filename

                try:
                    ai_results = analyze_fabric_image(full_image_path)
                    
                    if ai_results:
                        product.ai_fabric_type = ai_results.get('fabric_type')
                        product.ai_thickness = ai_results.get('thickness')
                        product.ai_weaving_density = ai_results.get('weaving_density')
                        product.ai_weaving_quality_score = ai_results.get('weaving_quality_score')
                        product.ai_pattern_style = ai_results.get('pattern_style')
                        product.ai_texture_feel = ai_results.get('texture_feel')
                        product.ai_fiber_direction = ai_results.get('fiber_direction')
                        product.ai_pile_analysis = ai_results.get('pile_analysis')
                        product.ai_light_reflection = ai_results.get('light_reflection')
                        product.ai_finishing_quality = ai_results.get('finishing_quality')
                        product.ai_defects_detected = ai_results.get('defects_detected', False)
                        product.ai_defects_details = ai_results.get('defects_details')
                        product.ai_recommended_usage = ai_results.get('recommended_usage')
                        product.ai_suggested_season = ai_results.get('suggested_season')
                        product.ai_overall_quality_index = ai_results.get('overall_quality_index', 100)
                        product.ai_estimated_price_per_meter = ai_results.get('estimated_price_per_meter')
                        product.ai_analysis = ai_results
                except Exception as e:
                    print(f"AI Analysis Error: {str(e)}")

        variant_names = request.form.getlist('color_names[]')
        quantities = request.form.getlist('color_quantities[]')
        variant_images = request.files.getlist('variant_images[]')

        for index, variant_name in enumerate(variant_names):
            variant_name = variant_name.strip()
            if not variant_name:
                continue
            quantity = float(quantities[index] if index < len(quantities) else 0)
            
            image_filename = None
            if index < len(variant_images) and variant_images[index].filename:
                image_file = variant_images[index]
                image_filename = f"variant_{product.id}_{index}_{secure_filename(image_file.filename)}"
                image_file.save(os.path.join(UPLOAD_FOLDER, image_filename))

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
        flash('Fabric batch saved successfully with AI Smart Analysis', 'success')
        return redirect(url_for('inventory.list_products'))

    categories = Category.query.all()
    return render_template('inventory/add_product.html', categories=categories)
# =========================
# EDIT PRODUCT (MODIFIED FOR IMAGE DESIGNS & CATEGORIES)
# =========================
from sqlalchemy.orm import joinedload

@inventory_bp.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.options(joinedload(Product.variants)).get_or_404(id)

    if request.method == 'POST':
        product.cost_price_per_meter = float(request.form.get('cost_price_per_meter') or 0)
        product.selling_price = float(request.form.get('selling_price') or 0)
        
        category_id = request.form.get('category_id')
        product.category_id = int(category_id) if category_id else None

        # 🌟 استبدال الصورة الرئيسية بالمتجر (منفصلة عن صورة التحليل) 🌟
        if 'main_display_image' in request.files:
            main_image = request.files['main_display_image']
            if main_image and main_image.filename and allowed_file(main_image.filename):
                main_filename = secure_filename(main_image.filename)
                main_filename = f"main_{product.id}_{main_filename}"
                main_image.save(os.path.join(UPLOAD_FOLDER, main_filename))
                product.image_file = main_filename

        for variant in product.variants:
            qty_input = request.form.get(f'qty_variant_{variant.id}')
            if qty_input is not None:
                variant.quantity = float(qty_input)

        if 'new_variant_image' in request.files:
            file = request.files['new_variant_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                design_name = request.form.get('new_variant_name') or "unnamed design"
                
                new_variant = ProductVariant(
                    product_id=product.id,
                    color_name=design_name, 
                    image_filename=filename,
                    quantity=float(request.form.get('new_variant_qty') or 0)
                )
                db.session.add(new_variant)

        # 🌟 إضافة سجل مصدر/مورد جديد (اختياري) 🌟
        partner_name = request.form.get('partner_name')
        if partner_name:
            supply = SupplyLog(
                product_id=product.id,
                partner_name=partner_name,
                supplied_quantity=float(request.form.get('source_quantity') or 0),
                cost_price_at_purchase=float(request.form.get('source_cost_price') or 0),
                notes=request.form.get('source_notes')
            )
            db.session.add(supply)

        db.session.commit()
        flash("Product and design specifications updated successfully", "success")
        return redirect(url_for('inventory.list_products'))

    categories = Category.query.all()
    return render_template('inventory/edit_product.html', product=product, categories=categories)
# =========================
# AI REPORT VIEW (SAVED PRODUCT)
# =========================
@inventory_bp.route('/product/ai-report/<int:id>')
@login_required
def view_ai_report(id):
    product = Product.query.get_or_404(id)
    return render_template('inventory/product_ai_report.html', product=product)
# =========================
# SALES HISTORY
# =========================
@inventory_bp.route('/sales/history')
@login_required
def sales_history():
    from app.models import Order
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
    
    return render_template('inventory/customer_report.html', 
                           customer=customer, 
                           orders=orders, 
                           total_spent=total_spent,
                           now=datetime.now())
# =========================
# ARCHIVE/UNARCHIVE PRODUCT
# =========================
@inventory_bp.route('/product/toggle_archive/<int:id>', methods=['POST'])
@login_required
def toggle_archive(id):
    product = Product.query.get_or_404(id)
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
    all_supplies = SupplyLog.query.order_by(SupplyLog.purchase_date.desc()).all()
    return render_template('inventory/list_sources.html', supplies=all_supplies)
#================    
@inventory_bp.route('/product/customs/<filename>')
@login_required
def view_customs(filename):
    try:
        return send_from_directory(uploads, filename)
    except FileNotFoundError:
        abort(404, description="Customs document file not found on core storage.")    
@inventory_bp.route('/product/search')
@login_required
def search_products():
    term = request.args.get('q', '').strip()
    if not term:
        return jsonify([])
    products = Product.query.filter(Product.name.ilike(f"%{term}%")).limit(10).all()
    return jsonify([product.name for product in products])        
@inventory_bp.route('/product/details/<string:name>')
@login_required
def product_details(name):
    product = Product.query.filter(Product.name.ilike(name)).first()
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
    cart = session.get('cart', {})
    return render_template('cart.html', cart=cart)    
@inventory_bp.route('/financial-report')
@login_required
def financial_report():
    total_revenue = db.session.query(
        func.sum(OrderItem.price_per_unit * OrderItem.quantity_ordered)
    ).join(Order).filter(Order.status == 'approved').scalar() or 0
    
    approved_orders = Order.query.filter_by(status='approved').all()
    
    return render_template('inventory/financial_report.html', 
                           orders=approved_orders, 
                           total_revenue=total_revenue)

@inventory_bp.route('/fix-database')
def fix_database():
    from app.models import Order
    orphaned_orders = Order.query.filter(Order.customer_id == None).all()
    count = len(orphaned_orders)
    
    for order in orphaned_orders:
        db.session.delete(order)
    
    db.session.commit()
    return f"تم حذف {count} طلب تالف بنجاح! يمكنك الآن العودة لصفحة المبيعات."
@inventory_bp.route('/orders/pending')
@login_required
def pending_orders():
    pending_items = OrderItem.query.join(Order).filter(Order.status == 'pending').all()
    return render_template('inventory/pending_orders.html', pending_items=pending_items)    
#-------------------------------------------------------------------------------------------------------------------
#AI    
#-------------------------------------------------------------------------------------------------------------------
@inventory_bp.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("لم يتم رفع ملف!", "danger")
            return redirect(url_for('inventory.analyze'))
        
        file = request.files['file']
        if file.filename == '':
            flash("لم يتم اختيار صورة!", "danger")
            return redirect(url_for('inventory.analyze'))

        if file:
            upload_folder = 'app/static/uploads'
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            try:
                ai_result = analyze_fabric_image(file_path)
                
                if not ai_result:
                    flash("عذراً، لم يتمكن الذكاء الاصطناعي من تحليل هذه الصورة. يرجى تجربة صورة أوضح.", "warning")
                    return redirect(url_for('inventory.analyze'))

                return render_template('inventory/fabric_ai_report.html', result=ai_result, image_name=file.filename)
            
            except Exception as e:
                print(f"Error: {e}")
                flash(f"حدث خطأ تقني أثناء التحليل: {str(e)}", "danger")
                return redirect(url_for('inventory.analyze'))
            
    return render_template('inventory/upload.html')
#---------------------------------------------
# SAVE PRODUCT (MODIFIED FOR AI METRICS)
#-------------------------------------------
@inventory_bp.route('/save-product', methods=['POST'])
@login_required
def save_product():
    try:
        name = request.form.get('name')
        image_name = request.form.get('image_name') or 'default.jpg'
        ai_analysis_json = request.form.get('ai_analysis_json')
        
        analysis_data = {}
        if ai_analysis_json:
            try:
                analysis_data = json.loads(ai_analysis_json)
            except:
                analysis_data = {}
        
        if analysis_data is None:
            analysis_data = {}

        new_product = Product(
            name=name,
            image_file=image_name,
            ai_analysis=analysis_data,
            is_active=False,  # 🔒 مسودة: ما بيطلع عند الزبون حتى تنشريه يدوياً
            ai_fabric_type=analysis_data.get('fabric_type'),
            ai_thickness=analysis_data.get('thickness'),
            ai_weaving_density=analysis_data.get('weaving_density'),
            ai_weaving_quality_score=analysis_data.get('weaving_quality_score'),
            ai_pattern_style=analysis_data.get('pattern_style'),
            ai_texture_feel=analysis_data.get('texture_feel'),
            ai_fiber_direction=analysis_data.get('fiber_direction'),
            ai_pile_analysis=analysis_data.get('pile_analysis'),
            ai_light_reflection=analysis_data.get('light_reflection'),
            ai_finishing_quality=analysis_data.get('finishing_quality'),
            ai_defects_detected=analysis_data.get('defects_detected', False),
            ai_defects_details=analysis_data.get('defects_details'),
            ai_recommended_usage=analysis_data.get('recommended_usage'),
            ai_suggested_season=analysis_data.get('suggested_season'),
            ai_overall_quality_index=analysis_data.get('overall_quality_index', 100),
            ai_estimated_price_per_meter=analysis_data.get('estimated_price_per_meter')
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        flash('تم حفظ القماش كمسودة 📋 — أكملي السعر والكمية والصنف، ثم فعّليه ليظهر عند الزبون.', 'success')
        return redirect(url_for('inventory.edit_product', id=new_product.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error detail: {e}") 
        flash(f'حدث خطأ أثناء حفظ المنتج: {str(e)}', 'danger')
        return redirect(url_for('inventory.analyze'))
#-----------------------
@inventory_bp.route('/products')
def list_product():
    products = Product.query.all()
    return render_template('inventory/products_list.html', products=products)        
# ==========================================
# MANAGEMENT OF CATEGORIES
# ==========================================
@inventory_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'admin':
        flash('عذراً، لا تمتلك صلاحية للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('inventory.list_products'))
        
    if request.method == 'POST':
        category_name = request.form.get('name', '').strip()
        category_desc = request.form.get('description', '').strip()
        
        existing_category = Category.query.filter_by(name=category_name).first()
        if existing_category:
            flash('هذا الصنف موجود بالفعل!', 'warning')
        elif category_name:
            new_category = Category(name=category_name, description=category_desc)
            db.session.add(new_category)
            db.session.commit()
            flash(f'تم إضافة صنف "{category_name}" بنجاح! 🎉', 'success')
            return redirect(url_for('inventory.manage_categories'))

    categories = Category.query.all()
    return render_template('inventory/manage_categories.html', categories=categories)    
@inventory_bp.route('/delete-category/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('inventory.manage_categories'))
# =========================
# AI FABRIC MOCKUP PREVIEW (SHOP)
# =========================
def upload_local_image_to_public_url(local_path):
    """
    Uploads local fabric/variant image to ImgBB so NanoBanana servers can access it.
    """
    try:
        if not os.path.exists(local_path):
            return None
            
        with open(local_path, "rb") as file:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": IMGBB_API_KEY},
                files={"image": file},
                timeout=15
            )
            res_data = response.json()
            if response.status_code == 200 and res_data.get("success"):
                return res_data["data"]["url"]
    except Exception as e:
        print(f"ImgBB upload error: {e}")
    return None


@inventory_bp.route('/product/preview-mockup', methods=['POST'])
def preview_mockup():
    product_id = request.form.get('product_id')
    variant_id = request.form.get('variant_id')
    usage_type = (request.form.get('usage_type') or '').strip()

    if not product_id or not usage_type:
        return jsonify({"status": "error", "message": "بيانات ناقصة، يرجى تحديد الاستخدام أولاً"}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"status": "error", "message": "المنتج غير موجود"}), 404

    # 1. Target the selected variant image instead of default product image
    variant = ProductVariant.query.get(variant_id) if variant_id else None
    
    if variant and variant.image_filename:
        image_filename = variant.image_filename
        variant_key = f"v{variant.id}"
    else:
        image_filename = product.image_file
        variant_key = "main"

    image_path = os.path.join(UPLOAD_FOLDER, image_filename)

    # 2. Check local disk cache (scoped per product + variant + usage)
    slug = slugify_usage(usage_type)
    cache_filename = f"mockup_p{product_id}_{variant_key}_{slug}.png"
    cache_dir = os.path.join(UPLOAD_FOLDER, 'mockups')
    os.makedirs(cache_dir, exist_ok=True)
    cache_full_path = os.path.join(cache_dir, cache_filename)

    if os.path.exists(cache_full_path):
        return jsonify({
            "status": "success",
            "image_url": url_for('static', filename='uploads/mockups/' + cache_filename),
            "cached": True
        })

    # 3. Upload selected variant image to ImgBB
    public_fabric_url = upload_local_image_to_public_url(image_path)
    if not public_fabric_url:
        return jsonify({"status": "error", "message": "تعذر رفع صورة النقشة للخادم السحابي"}), 500

    # 4. Configure NanoBanana Image-to-Image Payload
    prompt = (
        f"Generate a professional, realistic product mockup of a {usage_type} "
        f"crafted completely using the exact fabric texture, pattern, and color from the provided input image."
    )

    headers = {
        "Authorization": f"Bearer {NANOBANANA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "type": "IMAGETOIAMGE",
        "imageUrls": [public_fabric_url],
        "numImages": 1,
        "image_size": "1:1",
        "callBackUrl": "https://localhost/dummy-callback"
    }

    try:
        api_res = requests.post(
            "https://api.nanobananaapi.ai/api/v1/nanobanana/generate",
            json=payload,
            headers=headers,
            timeout=15
        )
        res_json = api_res.json()

        if api_res.status_code == 200 and res_json.get("code") == 200:
            task_id = res_json.get("data", {}).get("taskId")
            return jsonify({
                "status": "pending",
                "task_id": task_id,
                "product_id": product_id,
                "variant_id": variant_id,
                "usage_type": usage_type
            })
        else:
            return jsonify({"status": "error", "message": res_json.get("msg", "فشل بدء التوليد")}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": "تعذر الاتصال بخدمة التوليد"}), 500


@inventory_bp.route('/product/mockup-status/<task_id>', methods=['GET'])
def check_mockup_status(task_id):
    product_id = request.args.get('product_id')
    variant_id = request.args.get('variant_id', '')
    usage_type = request.args.get('usage_type', '')

    headers = {"Authorization": f"Bearer {NANOBANANA_API_KEY}"}
    
    try:
        res = requests.get(
            f"https://api.nanobananaapi.ai/api/v1/nanobanana/record-info?taskId={task_id}",
            headers=headers,
            timeout=10
        )
        data = res.json()

        if data.get("code") == 200 and data.get("data"):
            record = data["data"]
            if record.get("successFlag") == 1:
                result_url = record.get("response", {}).get("resultImageUrl")
                
                # Cache result locally once completed
                if result_url and product_id and usage_type:
                    variant_key = f"v{variant_id}" if variant_id else "main"
                    slug = slugify_usage(usage_type)
                    cache_filename = f"mockup_p{product_id}_{variant_key}_{slug}.png"
                    cache_full_path = os.path.join(UPLOAD_FOLDER, 'mockups', cache_filename)

                    img_data = requests.get(result_url).content
                    with open(cache_full_path, 'wb') as f:
                        f.write(img_data)

                    local_url = url_for('static', filename='uploads/mockups/' + cache_filename)
                    return jsonify({"status": "completed", "image_url": local_url})
                
                return jsonify({"status": "completed", "image_url": result_url})

            elif record.get("errorCode") and record.get("errorCode") != 0:
                return jsonify({"status": "failed", "message": record.get("errorMessage", "حدث خطأ أثناء المعالجة")})

        return jsonify({"status": "processing"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500