from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'koperasi-sekolah-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Database helper
def get_db():
    conn = sqlite3.connect('koperasi.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect('koperasi.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  name TEXT NOT NULL,
                  role TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  description TEXT,
                  price REAL NOT NULL,
                  stock INTEGER NOT NULL,
                  category TEXT,
                  image TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  total_amount REAL NOT NULL,
                  status TEXT DEFAULT 'pending',
                  payment_proof TEXT,
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id INTEGER NOT NULL,
                  product_id INTEGER NOT NULL,
                  quantity INTEGER NOT NULL,
                  price REAL NOT NULL,
                  FOREIGN KEY (order_id) REFERENCES orders(id),
                  FOREIGN KEY (product_id) REFERENCES products(id))''')
    
    # Insert default admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        admin_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                  ('admin', admin_password, 'Administrator', 'admin'))
    
    # Insert sample products
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample_products = [
            ('Buku Tulis 80 Muka', 'Buku tulis berkualiti', 2.50, 100, 'Alat Tulis', '📓'),
            ('Pen Biru Pilot', 'Pen ballpoint biru', 1.50, 200, 'Alat Tulis', '🖊️'),
            ('Pensil 2B', 'Pensil 2B untuk peperiksaan', 0.80, 150, 'Alat Tulis', '✏️'),
            ('Pensel Warna 12 Pcs', 'Set pensel warna 12 keping', 8.00, 50, 'Alat Tulis', '🎨'),
            ('Pembaris 30cm', 'Pembaris plastik 30cm', 1.20, 80, 'Alat Tulis', '📏'),
            ('Pemadam Putih', 'Pemadam untuk pensil', 0.50, 120, 'Alat Tulis', '🧹'),
            ('Buku Latihan Matematik', 'Buku latihan tingkatan 1-5', 12.00, 60, 'Buku', '📚'),
            ('Fail Kotak', 'Fail kotak untuk dokumen', 3.50, 40, 'Alat Tulis', '📁'),
            ('Beg Sekolah', 'Beg sekolah berkualiti tinggi', 45.00, 25, 'Aksesori', '🎒'),
            ('Botol Air 500ml', 'Botol air untuk pelajar', 8.50, 70, 'Aksesori', '💧'),
        ]
        c.executemany("INSERT INTO products (name, description, price, stock, category, image) VALUES (?, ?, ?, ?, ?, ?)",
                      sample_products)
    
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        
        return render_template('login.html', error='Username atau password salah')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        
        db = get_db()
        existing = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing:
            db.close()
            return render_template('register.html', error='Username sudah wujud')
        
        hashed_password = generate_password_hash(password)
        db.execute('INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)',
                   (username, hashed_password, name, 'student'))
        db.commit()
        db.close()
        
        flash('Pendaftaran berjaya! Sila log masuk.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    db = get_db()
    products = db.execute('SELECT * FROM products ORDER BY category, name').fetchall()
    db.close()
    
    return render_template('student_dashboard.html', products=products, user=session)

@app.route('/student/orders')
def student_orders():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    db = get_db()
    orders = db.execute('''
        SELECT o.*
        FROM orders o
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    orders_with_items = []
    for order in orders:
        order_items = db.execute('''
            SELECT oi.*, p.name as product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order['id'],)).fetchall()
        orders_with_items.append({'order': order, 'items': order_items})
    
    db.close()
    
    return render_template('student_orders.html', orders=orders_with_items)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        cart_data = json.loads(request.form['cart_data'])
        notes = request.form.get('notes', '')
        
        # Handle file upload
        payment_proof = request.files.get('payment_proof')
        filename = None
        if payment_proof:
            filename = secure_filename(f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{payment_proof.filename}")
            payment_proof.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        db = get_db()
        
        # Calculate total
        total_amount = sum(item['price'] * item['quantity'] for item in cart_data)
        
        # Create order
        cursor = db.execute(
            'INSERT INTO orders (user_id, total_amount, payment_proof, notes) VALUES (?, ?, ?, ?)',
            (session['user_id'], total_amount, filename, notes)
        )
        order_id = cursor.lastrowid
        
        # Add order items and update stock
        for item in cart_data:
            db.execute(
                'INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                (order_id, item['id'], item['quantity'], item['price'])
            )
            db.execute(
                'UPDATE products SET stock = stock - ? WHERE id = ?',
                (item['quantity'], item['id'])
            )
        
        db.commit()
        db.close()
        
        flash('Pesanan berjaya dihantar!', 'success')
        return redirect(url_for('student_orders'))
    
    return render_template('checkout.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    
    stats = {
        'total_orders': db.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count'],
        'total_sales': db.execute('SELECT COALESCE(SUM(total_amount), 0) as total FROM orders WHERE status != "cancelled"').fetchone()['total'],
        'pending_orders': db.execute('SELECT COUNT(*) as count FROM orders WHERE status = "pending"').fetchone()['count'],
        'total_products': db.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    }
    
    recent_orders = db.execute('''
        SELECT o.*, u.name as student_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
        LIMIT 10
    ''').fetchall()
    
    db.close()
    
    return render_template('admin_dashboard.html', stats=stats, recent_orders=recent_orders)

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    products = db.execute('SELECT * FROM products ORDER BY category, name').fetchall()
    db.close()
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    orders = db.execute('''
        SELECT o.*, u.name as student_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    ''').fetchall()
    
    orders_with_items = []
    for order in orders:
        order_items = db.execute('''
            SELECT oi.*, p.name as product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order['id'],)).fetchall()
        orders_with_items.append({'order': order, 'items': order_items})
    
    db.close()
    
    return render_template('admin_orders.html', orders=orders_with_items)

@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    status = request.form['status']
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    db.commit()
    db.close()
    
    flash('Status pesanan dikemaskini!', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    category = request.form['category']
    image = request.form['image']
    
    db = get_db()
    db.execute('INSERT INTO products (name, description, price, stock, category, image) VALUES (?, ?, ?, ?, ?, ?)',
               (name, description, price, stock, category, image))
    db.commit()
    db.close()
    
    flash('Produk berjaya ditambah!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    
    db = get_db()
    db.execute('UPDATE products SET price = ?, stock = ? WHERE id = ?', (price, stock, product_id))
    db.commit()
    db.close()
    
    flash('Produk dikemaskini!', 'success')
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)