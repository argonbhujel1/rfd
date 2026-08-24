import os
import re
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, send_from_directory, abort
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required,
    current_user
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from config import Config
from models import (
    db, Admin, DeliveryBoy, Category, FoodItem, Order, OrderItem,
    DeliveryLocation, WebsiteSetting, Banner, Review
)

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Ensure folders exist
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    if user_id.startswith('admin:'):
        return Admin.query.get(int(user_id.split(':')[1]))
    if user_id.startswith('delivery:'):
        return DeliveryBoy.query.get(int(user_id.split(':')[1]))
    return None


# --------------- Helpers ---------------

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def save_upload(file):
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = Path(app.config['UPLOAD_FOLDER']) / filename
    file.save(filepath)
    return filename


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:100]


def get_setting(key, default=''):
    s = WebsiteSetting.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value):
    s = WebsiteSetting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = WebsiteSetting(key=key, value=value)
        db.session.add(s)
    db.session.commit()


def generate_order_number():
    last = Order.query.order_by(Order.id.desc()).first()
    num = (last.id + 1) if last else 1001
    return f"RFD-{num}"


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Admin):
            flash('Please log in as admin.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def delivery_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, DeliveryBoy):
            flash('Please log in as delivery boy.', 'warning')
            return redirect(url_for('delivery_login'))
        if not current_user.is_active:
            flash('Your account is inactive.', 'danger')
            logout_user()
            return redirect(url_for('delivery_login'))
        return f(*args, **kwargs)
    return decorated


def get_cart():
    return session.get('cart', {})


def cart_count():
    cart = get_cart()
    return sum(item.get('quantity', 0) for item in cart.values())


def cart_subtotal():
    cart = get_cart()
    return sum(item['price'] * item['quantity'] for item in cart.values())


@app.context_processor
def inject_globals():
    return {
        'cart_count': cart_count(),
        'site_name': get_setting('site_name', 'Ratuwamai Food Delivery'),
        'phone': get_setting('phone', '9800000000'),
        'email': get_setting('email', 'info@ratuwamai.com'),
        'address': get_setting('address', 'Ratuwamai, Nepal'),
        'tiktok': get_setting('tiktok', ''),
        'facebook': get_setting('facebook', ''),
        'delivery_charge': float(get_setting('delivery_charge', '50')),
    }


# --------------- Customer Routes ---------------

@app.route('/')
def index():
    featured = FoodItem.query.filter_by(is_featured=True, is_available=True).limit(8).all()
    popular = FoodItem.query.filter_by(is_popular=True, is_available=True).limit(8).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    banners = Banner.query.filter_by(is_active=True).all()
    reviews = Review.query.filter_by(is_active=True).order_by(Review.created_at.desc()).limit(6).all()
    return render_template('index.html',
                           featured=featured, popular=popular,
                           categories=categories, banners=banners,
                           reviews=reviews,
                           hero_title=get_setting('hero_title', 'Delicious Food. Delivered to Your Door.'),
                           hero_subtitle=get_setting('hero_subtitle', 'Fresh local favourites from Ratuwamai — momo, chowmein, khaja & more.'),
                           about_text=get_setting('about_text', 'We deliver the best local food in Ratuwamai area. Fast, friendly and always fresh.'),
                           delivery_areas=get_setting('delivery_areas', 'Ratuwamai, Nearby villages & local areas'))


@app.route('/menu')
def menu():
    q = request.args.get('q', '').strip()
    cat = request.args.get('category', '')
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    query = FoodItem.query.filter_by(is_available=True)
    if q:
        query = query.filter(FoodItem.name.ilike(f'%{q}%') | FoodItem.description.ilike(f'%{q}%'))
    if cat:
        c = Category.query.filter_by(slug=cat, is_active=True).first()
        if c:
            query = query.filter_by(category_id=c.id)
    foods = query.order_by(FoodItem.name).all()
    return render_template('menu.html', foods=foods, categories=categories, q=q, active_cat=cat)


@app.route('/food/<slug>')
def food_detail(slug):
    food = FoodItem.query.filter_by(slug=slug, is_available=True).first_or_404()
    related = FoodItem.query.filter(
        FoodItem.category_id == food.category_id,
        FoodItem.id != food.id,
        FoodItem.is_available == True
    ).limit(4).all()
    return render_template('food_detail.html', food=food, related=related)


@app.route('/cart')
def cart():
    cart_data = get_cart()
    items = []
    for fid, data in cart_data.items():
        food = FoodItem.query.get(int(fid))
        if food and food.is_available:
            items.append({
                'id': food.id,
                'name': food.name,
                'image': food.image,
                'price': data['price'],
                'quantity': data['quantity'],
                'subtotal': data['price'] * data['quantity'],
                'instructions': data.get('instructions', '')
            })
    subtotal = sum(i['subtotal'] for i in items)
    delivery = float(get_setting('delivery_charge', '50'))
    return render_template('cart.html', items=items, subtotal=subtotal,
                           delivery_charge=delivery, total=subtotal + delivery)


@app.route('/api/cart/add', methods=['POST'])
def cart_add():
    data = request.get_json() or {}
    food_id = str(data.get('food_id'))
    quantity = int(data.get('quantity', 1))
    instructions = data.get('instructions', '')[:200]
    food = FoodItem.query.get(int(food_id))
    if not food or not food.is_available:
        return jsonify({'ok': False, 'error': 'Food not available'}), 400
    cart = get_cart()
    if food_id in cart:
        cart[food_id]['quantity'] += quantity
        if instructions:
            cart[food_id]['instructions'] = instructions
    else:
        cart[food_id] = {
            'name': food.name,
            'price': food.price,
            'quantity': quantity,
            'image': food.image or '',
            'instructions': instructions
        }
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'count': cart_count(), 'message': f'{food.name} added to cart'})


@app.route('/api/cart/update', methods=['POST'])
def cart_update():
    data = request.get_json() or {}
    food_id = str(data.get('food_id'))
    quantity = int(data.get('quantity', 1))
    cart = get_cart()
    if food_id not in cart:
        return jsonify({'ok': False}), 400
    if quantity <= 0:
        del cart[food_id]
    else:
        cart[food_id]['quantity'] = quantity
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'count': cart_count()})


@app.route('/api/cart/remove', methods=['POST'])
def cart_remove():
    data = request.get_json() or {}
    food_id = str(data.get('food_id'))
    cart = get_cart()
    if food_id in cart:
        del cart[food_id]
        session['cart'] = cart
        session.modified = True
    return jsonify({'ok': True, 'count': cart_count()})


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_data = get_cart()
    if not cart_data:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('menu'))

    items = []
    for fid, data in cart_data.items():
        food = FoodItem.query.get(int(fid))
        if food and food.is_available:
            items.append({
                'food': food,
                'quantity': data['quantity'],
                'price': data['price'],
                'subtotal': data['price'] * data['quantity'],
                'instructions': data.get('instructions', '')
            })
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('menu'))

    subtotal = sum(i['subtotal'] for i in items)
    delivery = float(get_setting('delivery_charge', '50'))
    total = subtotal + delivery

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        landmark = request.form.get('landmark', '').strip()
        note = request.form.get('note', '').strip()

        errors = []
        if not name or len(name) < 2:
            errors.append('Please enter your full name.')
        if not phone or not re.match(r'^9\d{9}$', phone.replace(' ', '')):
            errors.append('Please enter a valid 10-digit Nepali mobile number (starting with 9).')
        if not address or len(address) < 5:
            errors.append('Please enter a delivery address.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('checkout.html', items=items, subtotal=subtotal,
                                   delivery_charge=delivery, total=total)

        phone = phone.replace(' ', '')
        order = Order(
            order_number=generate_order_number(),
            customer_name=name,
            customer_phone=phone,
            delivery_address=address,
            landmark=landmark or None,
            note=note or None,
            subtotal=subtotal,
            delivery_charge=delivery,
            total=total,
            status='PENDING'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            oi = OrderItem(
                order_id=order.id,
                food_id=item['food'].id,
                quantity=item['quantity'],
                price=item['price'],
                subtotal=item['subtotal'],
                special_instructions=item['instructions'] or None
            )
            db.session.add(oi)

        db.session.commit()
        session.pop('cart', None)
        return redirect(url_for('order_success', order_number=order.order_number))

    return render_template('checkout.html', items=items, subtotal=subtotal,
                           delivery_charge=delivery, total=total)


@app.route('/order/success/<order_number>')
def order_success(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_success.html', order=order)


@app.route('/track')
@app.route('/track/<order_number>')
def track_order(order_number=None):
    order = None
    if order_number:
        order = Order.query.filter_by(order_number=order_number.upper()).first()
        if not order:
            flash('Order not found. Please check the Order ID.', 'warning')
    elif request.args.get('order'):
        return redirect(url_for('track_order', order_number=request.args.get('order').upper()))
    return render_template('track_order.html', order=order)


@app.route('/api/orders/<order_number>/location')
def api_order_location(order_number):
    order = Order.query.filter_by(order_number=order_number.upper()).first()
    if not order:
        return jsonify({'ok': False, 'error': 'Order not found'}), 404
    loc = order.location
    data = {
        'ok': True,
        'status': order.status,
        'order_number': order.order_number,
        'has_location': loc is not None,
        'customer_lat': order.customer_lat,
        'customer_lng': order.customer_lng,
    }
    if loc:
        data.update({
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'updated_at': loc.updated_at.isoformat() + 'Z',
            'delivery_boy_name': order.delivery_boy.name if order.delivery_boy else None,
        })
    return jsonify(data)


@app.route('/about')
def about():
    return render_template('about.html',
                           about_text=get_setting('about_text', 'We deliver the best local food in Ratuwamai area.'))


@app.route('/contact')
def contact():
    return render_template('contact.html')


# --------------- Admin Routes ---------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    stats = {
        'total_orders': Order.query.count(),
        'pending': Order.query.filter_by(status='PENDING').count(),
        'approved': Order.query.filter_by(status='APPROVED').count(),
        'preparing': Order.query.filter_by(status='PREPARING').count(),
        'out_for_delivery': Order.query.filter_by(status='OUT_FOR_DELIVERY').count(),
        'delivered': Order.query.filter_by(status='DELIVERED').count(),
        'total_foods': FoodItem.query.count(),
        'total_delivery': DeliveryBoy.query.count(),
    }
    recent = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent=recent)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    status = request.args.get('status', '')
    q = request.args.get('q', '').strip()
    query = Order.query
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(
            Order.order_number.ilike(f'%{q}%') |
            Order.customer_name.ilike(f'%{q}%') |
            Order.customer_phone.ilike(f'%{q}%')
        )
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders, status=status, q=q)


@app.route('/admin/orders/<int:order_id>', methods=['GET', 'POST'])
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    boys = DeliveryBoy.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'status':
            new_status = request.form.get('status')
            if new_status in ['PENDING', 'APPROVED', 'PREPARING', 'ASSIGNED',
                              'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED']:
                order.status = new_status
                order.updated_at = datetime.utcnow()
                db.session.commit()
                flash(f'Status updated to {new_status}.', 'success')
        elif action == 'assign':
            boy_id = request.form.get('delivery_boy_id')
            if boy_id:
                order.delivery_boy_id = int(boy_id)
                if order.status in ['PENDING', 'APPROVED', 'PREPARING']:
                    order.status = 'ASSIGNED'
                order.updated_at = datetime.utcnow()
                db.session.commit()
                flash('Delivery boy assigned.', 'success')
        return redirect(url_for('admin_order_detail', order_id=order.id))
    return render_template('admin/order_detail.html', order=order, boys=boys)


@app.route('/admin/foods')
@admin_required
def admin_foods():
    foods = FoodItem.query.order_by(FoodItem.name).all()
    return render_template('admin/foods.html', foods=foods)


@app.route('/admin/foods/add', methods=['GET', 'POST'])
@admin_required
def admin_food_add():
    categories = Category.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        category_id = request.form.get('category_id')
        is_available = 'is_available' in request.form
        is_featured = 'is_featured' in request.form
        is_popular = 'is_popular' in request.form
        try:
            price = float(price)
        except ValueError:
            flash('Invalid price.', 'danger')
            return render_template('admin/food_form.html', categories=categories, food=None)

        if not name or not category_id:
            flash('Name and category are required.', 'danger')
            return render_template('admin/food_form.html', categories=categories, food=None)

        slug = slugify(name)
        base_slug = slug
        n = 1
        while FoodItem.query.filter_by(slug=slug).first():
            slug = f'{base_slug}-{n}'
            n += 1

        image = None
        if 'image' in request.files:
            image = save_upload(request.files['image'])

        food = FoodItem(
            name=name, slug=slug, description=description, price=price,
            category_id=int(category_id), image=image,
            is_available=is_available, is_featured=is_featured, is_popular=is_popular
        )
        db.session.add(food)
        db.session.commit()
        flash('Food added successfully.', 'success')
        return redirect(url_for('admin_foods'))
    return render_template('admin/food_form.html', categories=categories, food=None)


@app.route('/admin/foods/<int:food_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_food_edit(food_id):
    food = FoodItem.query.get_or_404(food_id)
    categories = Category.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        food.name = request.form.get('name', '').strip()
        food.description = request.form.get('description', '').strip()
        try:
            food.price = float(request.form.get('price', food.price))
        except ValueError:
            pass
        food.category_id = int(request.form.get('category_id', food.category_id))
        food.is_available = 'is_available' in request.form
        food.is_featured = 'is_featured' in request.form
        food.is_popular = 'is_popular' in request.form
        if 'image' in request.files and request.files['image'].filename:
            new_img = save_upload(request.files['image'])
            if new_img:
                food.image = new_img
        food.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Food updated.', 'success')
        return redirect(url_for('admin_foods'))
    return render_template('admin/food_form.html', categories=categories, food=food)


@app.route('/admin/foods/<int:food_id>/delete', methods=['POST'])
@admin_required
def admin_food_delete(food_id):
    food = FoodItem.query.get_or_404(food_id)
    db.session.delete(food)
    db.session.commit()
    flash('Food deleted.', 'success')
    return redirect(url_for('admin_foods'))


@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                slug = slugify(name)
                if not Category.query.filter_by(slug=slug).first():
                    cat = Category(name=name, slug=slug)
                    db.session.add(cat)
                    db.session.commit()
                    flash('Category added.', 'success')
                else:
                    flash('Category already exists.', 'warning')
        elif action == 'edit':
            cat_id = request.form.get('id')
            cat = Category.query.get(cat_id)
            if cat:
                cat.name = request.form.get('name', cat.name).strip()
                cat.is_active = 'is_active' in request.form
                db.session.commit()
                flash('Category updated.', 'success')
        elif action == 'delete':
            cat_id = request.form.get('id')
            cat = Category.query.get(cat_id)
            if cat and cat.foods.count() == 0:
                db.session.delete(cat)
                db.session.commit()
                flash('Category deleted.', 'success')
            else:
                flash('Cannot delete category with foods.', 'danger')
        return redirect(url_for('admin_categories'))
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template('admin/categories.html', categories=cats)


@app.route('/admin/delivery-boys', methods=['GET', 'POST'])
@admin_required
def admin_delivery_boys():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            if name and phone and username and password:
                if DeliveryBoy.query.filter_by(username=username).first():
                    flash('Username already exists.', 'danger')
                else:
                    boy = DeliveryBoy(name=name, phone=phone, username=username)
                    boy.set_password(password)
                    db.session.add(boy)
                    db.session.commit()
                    flash('Delivery boy added.', 'success')
            else:
                flash('All fields required.', 'danger')
        elif action == 'edit':
            boy = DeliveryBoy.query.get(request.form.get('id'))
            if boy:
                boy.name = request.form.get('name', boy.name).strip()
                boy.phone = request.form.get('phone', boy.phone).strip()
                boy.is_active = 'is_active' in request.form
                pwd = request.form.get('password', '')
                if pwd:
                    boy.set_password(pwd)
                db.session.commit()
                flash('Updated.', 'success')
        elif action == 'delete':
            boy = DeliveryBoy.query.get(request.form.get('id'))
            if boy:
                boy.is_active = False
                db.session.commit()
                flash('Deactivated.', 'success')
        return redirect(url_for('admin_delivery_boys'))
    boys = DeliveryBoy.query.order_by(DeliveryBoy.name).all()
    return render_template('admin/delivery_boys.html', boys=boys)


@app.route('/admin/banners', methods=['GET', 'POST'])
@admin_required
def admin_banners():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title', '').strip()
            subtitle = request.form.get('subtitle', '').strip()
            button_text = request.form.get('button_text', '').strip()
            button_url = request.form.get('button_url', '').strip()
            image = None
            if 'image' in request.files:
                image = save_upload(request.files['image'])
            banner = Banner(title=title, subtitle=subtitle, button_text=button_text,
                            button_url=button_url, image=image, is_active=True)
            db.session.add(banner)
            db.session.commit()
            flash('Banner added.', 'success')
        elif action == 'toggle':
            b = Banner.query.get(request.form.get('id'))
            if b:
                b.is_active = not b.is_active
                db.session.commit()
        elif action == 'delete':
            b = Banner.query.get(request.form.get('id'))
            if b:
                db.session.delete(b)
                db.session.commit()
                flash('Banner deleted.', 'success')
        return redirect(url_for('admin_banners'))
    banners = Banner.query.order_by(Banner.created_at.desc()).all()
    return render_template('admin/banners.html', banners=banners)


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    keys = [
        'site_name', 'phone', 'email', 'address', 'tiktok', 'facebook',
        'hero_title', 'hero_subtitle', 'about_text', 'delivery_areas',
        'delivery_charge', 'footer_text'
    ]
    if request.method == 'POST':
        for k in keys:
            val = request.form.get(k, '')
            set_setting(k, val)
        flash('Settings saved.', 'success')
        return redirect(url_for('admin_settings'))
    settings = {k: get_setting(k) for k in keys}
    return render_template('admin/settings.html', settings=settings)


# --------------- Delivery Boy Routes ---------------

@app.route('/delivery/login', methods=['GET', 'POST'])
def delivery_login():
    if current_user.is_authenticated and isinstance(current_user, DeliveryBoy):
        return redirect(url_for('delivery_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        boy = DeliveryBoy.query.filter_by(username=username, is_active=True).first()
        if boy and boy.check_password(password):
            login_user(boy)
            return redirect(url_for('delivery_dashboard'))
        flash('Invalid credentials or account inactive.', 'danger')
    return render_template('delivery/login.html')


@app.route('/delivery/logout')
@login_required
def delivery_logout():
    logout_user()
    return redirect(url_for('delivery_login'))


@app.route('/delivery/dashboard')
@delivery_required
def delivery_dashboard():
    orders = Order.query.filter(
        Order.delivery_boy_id == current_user.id,
        Order.status.in_(['ASSIGNED', 'OUT_FOR_DELIVERY'])
    ).order_by(Order.created_at.desc()).all()
    return render_template('delivery/dashboard.html', orders=orders)


@app.route('/delivery/order/<int:order_id>')
@delivery_required
def delivery_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.delivery_boy_id != current_user.id:
        abort(403)
    return render_template('delivery/delivery_detail.html', order=order)


@app.route('/api/delivery/status', methods=['POST'])
@delivery_required
def api_delivery_status():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    new_status = data.get('status')
    order = Order.query.get(order_id)
    if not order or order.delivery_boy_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403
    allowed = {
        'ASSIGNED': ['OUT_FOR_DELIVERY'],
        'OUT_FOR_DELIVERY': ['DELIVERED'],
    }
    if order.status in allowed and new_status in allowed[order.status]:
        order.status = new_status
        order.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'ok': True, 'status': new_status})
    return jsonify({'ok': False, 'error': 'Invalid status transition'}), 400


@app.route('/api/delivery/location', methods=['POST'])
@delivery_required
def api_delivery_location():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    lat = data.get('latitude')
    lng = data.get('longitude')
    if not order_id or lat is None or lng is None:
        return jsonify({'ok': False, 'error': 'Missing data'}), 400
    order = Order.query.get(order_id)
    if not order or order.delivery_boy_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403
    if order.status not in ['OUT_FOR_DELIVERY', 'ASSIGNED']:
        return jsonify({'ok': False, 'error': 'Order not in delivery'}), 400

    loc = DeliveryLocation.query.filter_by(order_id=order.id).first()
    if loc:
        loc.latitude = float(lat)
        loc.longitude = float(lng)
        loc.updated_at = datetime.utcnow()
    else:
        loc = DeliveryLocation(
            order_id=order.id,
            delivery_boy_id=current_user.id,
            latitude=float(lat),
            longitude=float(lng)
        )
        db.session.add(loc)
    if order.status == 'ASSIGNED':
        order.status = 'OUT_FOR_DELIVERY'
        order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'updated_at': loc.updated_at.isoformat() + 'Z'})


# --------------- Error Handlers ---------------

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500


# --------------- CLI / Init ---------------

def init_db():
    with app.app_context():
        db.create_all()
        # Default admin
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin', email='admin@ratuwamai.com')
            admin.set_password('admin123')
            db.session.add(admin)
            print('Created default admin: admin / admin123  (CHANGE IN PRODUCTION!)')

        # Default settings
        defaults = {
            'site_name': 'Ratuwamai Food Delivery',
            'phone': '9801234567',
            'email': 'hello@ratuwamai.com',
            'address': 'Ratuwamai Bazar, Nepal',
            'tiktok': 'https://tiktok.com/@ratuwamai',
            'facebook': 'https://facebook.com/ratuwamai',
            'hero_title': 'Delicious Food. Delivered to Your Door.',
            'hero_subtitle': 'Fresh local favourites from Ratuwamai — momo, chowmein, khaja & more.',
            'about_text': 'Ratuwamai Food Delivery brings the best local food straight to your door. We partner with trusted local kitchens to serve authentic Nepali flavours with speed and care.',
            'delivery_areas': 'Ratuwamai, Nearby local areas & surrounding villages',
            'delivery_charge': '50',
            'footer_text': 'Ratuwamai Food Delivery — Fresh food, fast delivery.',
        }
        for k, v in defaults.items():
            if not WebsiteSetting.query.filter_by(key=k).first():
                db.session.add(WebsiteSetting(key=k, value=v))

        # Categories
        cats = [
            ('Momo', 'momo', 1),
            ('Chowmein', 'chowmein', 2),
            ('Khaja', 'khaja', 3),
            ('Burger', 'burger', 4),
            ('Pizza', 'pizza', 5),
            ('Chicken', 'chicken', 6),
            ('Snacks', 'snacks', 7),
            ('Drinks', 'drinks', 8),
            ('Other', 'other', 9),
        ]
        for name, slug, order in cats:
            if not Category.query.filter_by(slug=slug).first():
                db.session.add(Category(name=name, slug=slug, sort_order=order))

        db.session.commit()

        # Sample foods (if empty)
        if FoodItem.query.count() == 0:
            sample_foods = [
                ('Steam Momo (Chicken)', 'momo', 180, 'Juicy chicken momo steamed to perfection. 10 pieces.', True, True),
                ('Fry Momo', 'momo', 200, 'Crispy fried chicken momo with spicy achar.', True, False),
                ('Jhol Momo', 'momo', 220, 'Momo served in flavourful jhol soup.', False, True),
                ('Chicken Chowmein', 'chowmein', 160, 'Classic spicy chicken chowmein.', True, True),
                ('Veg Chowmein', 'chowmein', 140, 'Fresh vegetable chowmein.', False, False),
                ('Egg Chowmein', 'chowmein', 150, 'Chowmein with egg and veggies.', False, False),
                ('Chicken Khaja Set', 'khaja', 250, 'Rice, dal, chicken curry, achar & pickle.', True, True),
                ('Veg Khaja Set', 'khaja', 180, 'Complete veg set with seasonal curry.', False, False),
                ('Chicken Burger', 'burger', 220, 'Crispy chicken patty with fresh veggies.', True, False),
                ('Cheese Burger', 'burger', 250, 'Juicy patty with melted cheese.', False, True),
                ('Margherita Pizza', 'pizza', 350, 'Classic cheese & tomato pizza (8 inch).', True, False),
                ('Chicken Pizza', 'pizza', 420, 'Loaded chicken pizza with mozzarella.', False, True),
                ('Chicken Wings (6pc)', 'chicken', 280, 'Spicy crispy chicken wings.', True, True),
                ('Chicken Lollipop', 'chicken', 260, 'Crispy lollipop with special sauce.', False, False),
                ('French Fries', 'snacks', 120, 'Crispy golden fries with ketchup.', False, True),
                ('Samosa (2pc)', 'snacks', 60, 'Classic potato samosa.', False, False),
                ('Cold Drinks', 'drinks', 60, 'Coke / Fanta / Sprite 250ml.', False, False),
                ('Lassi', 'drinks', 80, 'Fresh sweet or salty lassi.', True, False),
                ('Masala Tea', 'drinks', 40, 'Hot Nepali masala chiya.', False, False),
            ]
            for name, cat_slug, price, desc, featured, popular in sample_foods:
                cat = Category.query.filter_by(slug=cat_slug).first()
                if cat:
                    food = FoodItem(
                        name=name, slug=slugify(name), description=desc,
                        price=price, category_id=cat.id,
                        is_available=True, is_featured=featured, is_popular=popular
                    )
                    db.session.add(food)

            # Sample reviews
            reviews = [
                ('Sita R.', 5, 'Best momo in Ratuwamai! Fast delivery too.'),
                ('Ram K.', 5, 'Chowmein was perfect. Will order again.'),
                ('Anita S.', 4, 'Good food and friendly delivery boy.'),
                ('Bikash T.', 5, 'Khaja set is filling and tasty.'),
            ]
            for name, rating, comment in reviews:
                db.session.add(Review(customer_name=name, rating=rating, comment=comment))

            # Sample delivery boy
            if not DeliveryBoy.query.filter_by(username='delivery1').first():
                boy = DeliveryBoy(name='Hari Bahadur', phone='9812345678', username='delivery1')
                boy.set_password('delivery123')
                db.session.add(boy)

            db.session.commit()
            print('Sample data seeded.')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
