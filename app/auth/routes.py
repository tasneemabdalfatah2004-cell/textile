from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import db

# التصليح هنا: تم تعديل name إلى name ليتعرف البلوبرنت بشكل صحيح
auth_bp = Blueprint('auth', __name__)

# 🔐 رووت تسجيل الدخول
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('main.dashboard'))
        else:
            return redirect(url_for('inventory.customer_shop'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # التحقق من المستخدم وكلمة المرور المشفرة
        if user and user.check_password(password):
            login_user(user)
            flash(f'مرحباً بك مجدداً {user.username}!', 'success')
            
            # التوجيه حسب الدور (مثل كودك الأصلي تماماً)
            if user.role == 'admin':
                return redirect(url_for('main.dashboard'))
            else:
                return redirect(url_for('inventory.customer_shop'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
            
    return render_template('auth/login.html')

# 🚪 رووت تسجيل الخروج
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('auth.login'))