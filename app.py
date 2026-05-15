from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
import os
import mercadopago
from werkzeug.utils import secure_filename
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mi_secreto_super_seguro')

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Configuración para producción vs desarrollo
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
DEBUG_MODE = os.environ.get('DEBUG', 'True').lower() == 'true'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tienda.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Inicializar Mercado Pago
mp_access_token = os.environ.get('MP_ACCESS_TOKEN', 'APP_USR-814094876045551-050615-ce53a8ffac39556a6c210a230039f18b-93020827')
mp_sdk = mercadopago.SDK(mp_access_token)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    productos = db.relationship('Producto', backref='categoria_rel', lazy=True)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    colores = db.Column(db.String(200), nullable=True)
    img = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.Text, nullable=True)
    materiales = db.Column(db.Text, nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    destacado = db.Column(db.Boolean, default=False)
    oculto = db.Column(db.Boolean, default=False)

class ImagenSecundaria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    orden = db.Column(db.Integer, default=0)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    producto = db.relationship('Producto', backref=db.backref('imagenes_extra', lazy=True, cascade="all, delete-orphan", order_by='ImagenSecundaria.orden'))

CATALOGO_INICIAL = {
    "Sweaters": [
        {"nombre": "Amore", "precio": 200000, "stock": 3, "colores": "Dulce de leche, Crudo, Gris claro, Violeta", "img": "amore.jpg", "desc": "Detalles románticos con un calce holgado ideal para media estación.", "materiales": "100% hilo de algodón hipoalergénico. Lavar a mano con agua fría."},
        {"nombre": "Patagonia", "precio": 180000, "stock": 5, "colores": "Coral melange, Gris melange, Vison melange", "img": "placeholder1.png", "desc": "Diseño inspirado en la montaña, super abrigado y de trama gruesa.", "materiales": "Mezcla de lana merino y acrílico premium para evitar picazón. Lavar en seco."}
    ],
    "Sacos": [
        {"nombre": "Amelie", "precio": 280000, "stock": 2, "colores": "Vison, Camel, Gris oscuro", "img": "placeholder1.png", "desc": "Estilo parisino, largo medio y botones de madera artesanales.", "materiales": "Lana sedificada extra suave. Botones tallados a mano en madera natural."},
        {"nombre": "Luna", "precio": 250000, "stock": 4, "colores": "Arena, Tabaco", "img": "luna.jpg", "desc": "Corte asimétrico, perfecto para salidas nocturnas.", "materiales": "100% lana merino de grosor medio. Caída ligera y abrigada."}
    ],
    "Tapados": [
        {"nombre": "Meli", "precio": 75000, "stock": 3, "colores": "Melange", "img": "placeholder1.png", "desc": "Clásico, abrigado y combinable con cualquier outfit.", "materiales": "Hilado jaspeado de alta densidad para estructurar el corte."},
        {"nombre": "Narciso", "precio": 85000, "stock": 1, "colores": "Crudo, Berry", "img": "placeholder1.png", "desc": "Largo hasta la rodilla, estructura firme y máxima calidez.", "materiales": "Doble hebra de lana gruesa de oveja. Extrema calidez térmica."},
        {"nombre": "Nose", "precio": 70000, "stock": 0, "colores": "x", "img": "placeholder1.png", "desc": "Modelo experimental de edición limitada, textura única.", "materiales": "Hilado fantasía texturizado de edición limitada."},
        {"nombre": "Tokio", "precio": 80000, "stock": 2, "colores": "Azul, Crudo, Gris, Negro, Camel", "img": "placeholder1.png", "desc": "Corte oriental con mangas amplias y cuello volcado.", "materiales": "Lana con un toque de angora para mayor suavidad visual."}
    ],
    "Chalecos": [
        {"nombre": "Cuore", "precio": 150000, "stock": 4, "colores": "Crudo", "img": "placeholder1.png", "desc": "Detalles de corazones calados en la trama.", "materiales": "Hilo rústico de algodón, perfecto para usar sobre camisas."},
        {"nombre": "Granny", "precio": 150000, "stock": 6, "colores": "Gris Granny, Crudo Granny", "img": "placeholder1.png", "desc": "Hecho con la técnica clásica de cuadrados tejidos.", "materiales": "Restos seleccionados de hilados premium (Zero Waste)."},
        {"nombre": "Otoño", "precio": 150000, "stock": 3, "colores": "Bordo, Verde militar", "img": "placeholder1.png", "desc": "Paleta de colores tierra y corte relajado.", "materiales": "Lana acrílica de tacto sedoso."},
        {"nombre": "Trama", "precio": 100000, "stock": 5, "colores": "Malbec, Camel", "img": "placeholder1.png", "desc": "Tejido tupido y estructurado, ideal para superponer.", "materiales": "Lana merino de un solo cabo."},
        {"nombre": "Vintage", "precio": 130000, "stock": 5, "colores": "Verde", "img": "placeholder1.png", "desc": "Toque retro con escote en V profundo.", "materiales": "Mezcla de algodón y acrílico de colores sólidos."}
    ],
    "Accesorios": [
        {"nombre": "Bufandón XXL", "precio": 25000, "stock": 10, "img": "bufandon_xxl.jpg", "desc": "Extra grande, envuelve por completo y abriga al máximo.", "materiales": "Lana acrílica gruesa para máximo volumen sin peso extra."},
        {"nombre": "Cuello Granny", "precio": 14000, "stock": 7, "img": "placeholder1.png", "desc": "Cuello cerrado con técnica de cuadrados coloridos.", "materiales": "Hilos de algodón multicolor."},
        {"nombre": "Cuello Romantic", "precio": 15000, "stock": 5, "img": "placeholder1.png", "desc": "Cuello ajustado con terminaciones en volados sutiles.", "materiales": "Lana merino ultra fina."},
        {"nombre": "Jabot", "precio": 18000, "stock": 4, "img": "placeholder1.png", "desc": "Accesorio frontal de estilo victoriano para realzar camisas.", "materiales": "Hilo de algodón peinado con detalles en punto red."},
        {"nombre": "Mitones", "precio": 15000, "stock": 12, "img": "placeholder1.png", "desc": "Guantes sin dedos para mantener las manos calientes y libres.", "materiales": "Lana y acrílico elástico para ajustarse a la mano."},
        {"nombre": "Pañoleta", "precio": 18000, "stock": 8, "img": "placeholder1.png", "desc": "Ligera y versátil para el cuello o la cabeza.", "materiales": "Hilo 100% algodón súper fresco."},
        {"nombre": "Polainas", "precio": 16000, "stock": 10, "img": "polainas.jpg", "desc": "Clásicas, ideales para usar sobre botas o borcegos.", "materiales": "Lana acrílica resistente al roce."},
        {"nombre": "Puntilla", "precio": 12000, "stock": 8, "img": "placeholder1.png", "desc": "Accesorio decorativo con borde tejido de alta precisión.", "materiales": "Hilo macramé fino."}
    ]
}

def init_db():
    with app.app_context():
        # Check if we need to recreate the database
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Si la tabla producto existe, verificar si tiene la columna oculto
            if 'producto' in tables:
                producto_columns = [col['name'] for col in inspector.get_columns('producto')]
                if 'oculto' not in producto_columns:
                    print("Columna 'oculto' no encontrada. Eliminando BD antigua...")
                    db.drop_all()
        except Exception as e:
            print(f"Error al verificar BD: {e}. Eliminando y recreando...")
            try:
                db.drop_all()
            except:
                pass
        
        db.create_all()
        if not Categoria.query.first():
            for cat_nombre, productos in CATALOGO_INICIAL.items():
                categoria = Categoria(nombre=cat_nombre)
                db.session.add(categoria)
                db.session.commit()
                
                for p_data in productos:
                    producto = Producto(
                        nombre=p_data['nombre'],
                        precio=p_data['precio'],
                        stock=p_data['stock'],
                        colores=p_data.get('colores', ''),
                        img=p_data['img'],
                        desc=p_data['desc'],
                        materiales=p_data['materiales'],
                        categoria_id=categoria.id
                    )
                    db.session.add(producto)
            db.session.commit()
            print("Base de datos inicializada con el catálogo.")

@app.context_processor
def inject_cart_count():
    cart_count = 0
    if 'carrito' in session:
        cart_count = sum(item['qty'] for item in session['carrito'].values())
    return dict(cart_count=cart_count)

@app.route('/')
def inicio():
    destacados = Producto.query.filter_by(destacado=True, oculto=False).limit(3).all()
    return render_template('index.html', destacados=destacados)

@app.route('/productos')
def productos():
    catalogo = {}
    categorias = Categoria.query.all()
    for cat in categorias:
        catalogo[cat.nombre] = [p for p in cat.productos if not p.oculto]
        
    return render_template('productos.html', catalogo=catalogo)

@app.route('/carrito')
def carrito():
    items_carrito = []
    total = 0
    if 'carrito' in session:
        for nombre, data in session['carrito'].items():
            subtotal = data['precio'] * data['qty']
            total += subtotal
            items_carrito.append({
                'nombre': nombre,
                'nombre_base': data.get('nombre_base', nombre),
                'color': data.get('color', ''),
                'qty': data['qty'],
                'precio': data['precio'],
                'img': data['img'],
                'subtotal': subtotal
            })
    return render_template('carrito.html', items_carrito=items_carrito, total=total)

@app.route('/add_to_cart/<nombre>', methods=['POST'])
def add_to_cart(nombre):
    # Support both AJAX JSON and standard form submission
    if request.is_json:
        data = request.get_json()
        color = data.get('color', '')
        qty = int(data.get('quantity', 1))
        is_ajax = True
    else:
        color = request.form.get('color', '')
        qty = 1
        is_ajax = False

    producto_encontrado = Producto.query.filter(Producto.nombre.ilike(nombre)).first()
            
    if not producto_encontrado:
        if is_ajax: return {"error": "Producto no encontrado"}, 404
        return "Producto no encontrado", 404
        
    if 'carrito' not in session:
        session['carrito'] = {}
        
    carrito = session['carrito']
    
    # Create a unique key if a color is selected
    cart_key = f"{producto_encontrado.nombre} - {color}" if color else producto_encontrado.nombre
    
    if cart_key in carrito:
        carrito[cart_key]['qty'] += qty
    else:
        carrito[cart_key] = {
            'nombre_base': producto_encontrado.nombre,
            'color': color,
            'qty': qty,
            'precio': producto_encontrado.precio,
            'img': producto_encontrado.img
        }
        
    session.modified = True
    
    if is_ajax:
        cart_count = sum(item['qty'] for item in session['carrito'].values())
        return {"success": True, "cart_count": cart_count}
    return redirect(request.referrer or url_for('productos'))

@app.route('/update_cart/<path:key>/<action>', methods=['POST'])
def update_cart(key, action):
    is_ajax = request.is_json
    item_deleted = False
    new_qty = 0
    item_subtotal = 0
    
    if 'carrito' in session and key in session['carrito']:
        if action == 'increase':
            session['carrito'][key]['qty'] += 1
        elif action == 'decrease':
            session['carrito'][key]['qty'] -= 1
            if session['carrito'][key]['qty'] <= 0:
                del session['carrito'][key]
                item_deleted = True
                
        session.modified = True
        
        if not item_deleted and key in session['carrito']:
            new_qty = session['carrito'][key]['qty']
            item_subtotal = session['carrito'][key]['precio'] * new_qty

    if is_ajax:
        cart_count = sum(item['qty'] for item in session.get('carrito', {}).values())
        total = sum(item['precio'] * item['qty'] for item in session.get('carrito', {}).values())
        return {
            "success": True,
            "deleted": item_deleted,
            "new_qty": new_qty,
            "item_subtotal": item_subtotal,
            "cart_total": total,
            "cart_count": cart_count
        }
    return redirect(url_for('carrito'))

@app.route('/remove_from_cart/<path:nombre>', methods=['POST'])
def remove_from_cart(nombre):
    key_to_remove = None
    if 'carrito' in session:
        for key in session['carrito']:
            if key.lower() == nombre.lower():
                key_to_remove = key
                break
                
        if key_to_remove:
            del session['carrito'][key_to_remove]
            session.modified = True
            
    return redirect(url_for('carrito'))

@app.route('/empty_cart', methods=['POST'])
def empty_cart():
    session.pop('carrito', None)
    return redirect(url_for('carrito'))

@app.route('/producto/<nombre>')
def producto_detalle(nombre):
    producto = Producto.query.filter(Producto.nombre.ilike(nombre)).first()
    if not producto or producto.oculto:
        return "Producto no encontrado", 404
        
    # Obtener productos relacionados aleatorios (no solo de la misma categoría)
    relacionados = Producto.query.filter(Producto.id != producto.id, Producto.oculto == False).order_by(db.func.random()).limit(4).all()
    
    return render_template('producto.html', item=producto, categoria=producto.categoria_rel.nombre, relacionados=relacionados)

@app.route('/guardar_datos_cliente', methods=['POST'])
def guardar_datos_cliente():
    data = request.get_json()
    session['datos_cliente'] = {
        'nombre': data.get('nombre', ''),
        'celular': data.get('celular', ''),
        'email': data.get('email', ''),
        'direccion': data.get('direccion', '')
    }
    session.modified = True
    return {'ok': True}

@app.route('/guardar_envio', methods=['POST'])
def guardar_envio():
    data = request.get_json()
    session['envio'] = {
        'tipo': data.get('tipo', 'retiro'),
        'costo': data.get('costo', 0),
        'zona': data.get('zona', ''),
        'cp': data.get('cp', '')
    }
    session.modified = True
    return {'ok': True}

@app.route('/checkout', methods=['POST'])
def checkout_mp():
    if 'carrito' not in session or not session['carrito']:
        flash('Tu carrito está vacío.', 'error')
        return redirect(url_for('carrito'))
        
    items = []
    for nombre, item_data in session['carrito'].items():
        items.append({
            "title": nombre,
            "quantity": int(item_data['qty']),
            "unit_price": float(item_data['precio']),
            "currency_id": "ARS"
        })
    
    # Agregar costo de envío si existe
    envio_info = session.get('envio', {})
    if envio_info.get('costo', 0) > 0:
        items.append({
            "title": f"Envío - {envio_info.get('zona', 'A domicilio')}",
            "quantity": 1,
            "unit_price": float(envio_info['costo']),
            "currency_id": "ARS"
        })
        
    preference_data = {
        "items": items,
        "back_urls": {
            "success": BASE_URL + "/pago_exitoso",
            "failure": BASE_URL + "/carrito",
            "pending": BASE_URL + "/carrito"
        }
    }
    
    try:
        preference_response = mp_sdk.preference().create(preference_data)
        preference = preference_response["response"]
        return redirect(preference["init_point"])
    except Exception as e:
        print(f"Error Mercado Pago: {type(e).__name__}: {str(e)}")
        flash(f'Error al conectar con Mercado Pago. Verifica tus credenciales.', 'error')
        return redirect(url_for('carrito'))

def enviar_correos_venta(comprador_email, comprador_nombre, items_str, total, datos_cliente=None):
    remitente_email = "somostejidosmargot@gmail.com"
    # IMPORTANT: Reemplaza esto con tu contraseña de aplicación de Gmail (16 letras sin espacios)
    remitente_pass = "zrgu bcxr rkdh kqok" 
    
    if remitente_pass == "TU_CONTRASEÑA_DE_APLICACION_AQUI":
        print("Aviso: No se enviaron correos porque no se configuró la contraseña de aplicación.")
        return

    # --- 1. Correo al comprador ---
    msg_cliente = MIMEMultipart()
    msg_cliente['From'] = formataddr(('Tejidos Margot', remitente_email))
    msg_cliente['To'] = comprador_email
    msg_cliente['Subject'] = "¡Gracias por tu compra en Margot! 🧶"
    
    body_cliente = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #523D35; font-size: 24px;">¡Hola {comprador_nombre}!</h1>
        </div>
        <p>Tu pago ha sido procesado con éxito. Queremos agradecerte enormemente por elegir lo artesanal y confiar en nuestras manos.</p>
        
        <div style="background-color: #EFEFE9; padding: 20px; border-radius: 5px; margin: 25px 0;">
            <h3 style="margin-top: 0; color: #523D35;">Detalle de tu compra:</h3>
            <p style="margin-bottom: 15px;">{items_str}</p>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 15px 0;">
            <p style="margin: 0;"><strong>Total pagado:</strong> ${total}</p>
        </div>
        
        <p>En breve <strong>nos pondremos en contacto contigo por WhatsApp</strong> (al número que dejaste en Mercado Pago) para coordinar el envío o indicarte la dirección exacta para el retiro por nuestro showroom en Villa Pueyrredón.</p>
        
        <br>
        <p>¡Gracias por ser parte de la familia Margot!</p>
        <p style="color: #959D90;"><i>Con cariño,<br>El equipo de Tejidos Margot</i></p>
    </body>
    </html>
    """
    msg_cliente.attach(MIMEText(body_cliente, 'html'))
    
    # --- 2. Correo a Margot (Administradora) ---
    msg_admin = MIMEMultipart()
    msg_admin['From'] = formataddr(('Bot de Ventas Margot', remitente_email))
    msg_admin['To'] = remitente_email
    msg_admin['Subject'] = f"💰 ¡NUEVA VENTA! - {comprador_nombre}"
    
    datos_extra = ""
    if datos_cliente:
        direccion = datos_cliente.get('direccion', '')
        direccion_html = f'<li>Dirección: {direccion}</li>' if direccion else '<li>Método: Retiro en showroom</li>'
        datos_extra = f"""
        <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 15px; margin: 15px 0;">
            <p style="margin: 0 0 8px 0;"><strong>📋 Datos ingresados por el cliente:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                <li>Nombre: {datos_cliente.get('nombre', 'No especificado')}</li>
                <li>Celular: {datos_cliente.get('celular', 'No especificado')}</li>
                <li>Email: {datos_cliente.get('email', 'No especificado')}</li>
                {direccion_html}
            </ul>
        </div>
        """
    
    body_admin = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #4CAF50;">¡Tus manos mágicas lo hicieron de nuevo! Nueva venta registrada.</h2>
        <p><strong>Datos del Cliente (Mercado Pago):</strong></p>
        <ul>
            <li>Nombre: {comprador_nombre}</li>
            <li>Email: {comprador_email}</li>
        </ul>
        {datos_extra}
        <p><strong>Detalle de los tejidos comprados:</strong></p>
        <p>{items_str}</p>
        <p><strong>Total Cobrado:</strong> ${total}</p>
        <hr>
        <p>👉 <em>Ve a tu panel de Mercado Pago para ver el número de teléfono de {comprador_nombre} y contactarle por WhatsApp.</em></p>
    </body>
    </html>
    """
    msg_admin.attach(MIMEText(body_admin, 'html'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente_email, remitente_pass)
        server.send_message(msg_cliente)
        server.send_message(msg_admin)
        server.quit()
        print("Correos enviados exitosamente.")
    except Exception as e:
        print(f"Error al enviar correos: {e}")

@app.route('/pago_exitoso')
def pago_exitoso():
    payment_id = request.args.get('payment_id')
    status = request.args.get('status')
    
    if payment_id and status == 'approved':
        try:
            # Consultar a MP
            payment_info = mp_sdk.payment().get(payment_id)
            if payment_info["status"] == 200:
                pago = payment_info["response"]
                comprador_email = pago.get("payer", {}).get("email", "")
                
                comprador_nombre = pago.get("payer", {}).get("first_name", "")
                if not comprador_nombre:
                    comprador_nombre = comprador_email.split("@")[0] if "@" in comprador_email else "Cliente"
                
                total = pago.get("transaction_amount", 0)
                
                items_comprados = []
                for item in pago.get("additional_info", {}).get("items", []):
                    items_comprados.append(f"{item.get('quantity')}x {item.get('title')} (${item.get('unit_price')})")
                
                items_str = "<br>".join(items_comprados)
                
                # Recuperar datos del cliente ingresados en el formulario
                datos_cliente = session.get('datos_cliente', {})
                
                if comprador_email:
                    enviar_correos_venta(comprador_email, comprador_nombre, items_str, total, datos_cliente)
        except Exception as e:
            print(f"Error procesando pago exitoso: {e}")

    session.pop('carrito', None)
    session.pop('datos_cliente', None)
    return render_template('pago_exitoso.html')

# --- RUTAS DE ADMINISTRACIÓN ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'margot2026':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Contraseña incorrecta', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('inicio'))

@app.route('/admin')
@login_required
def admin_dashboard():
    productos = Producto.query.all()
    # Generar lista de letras iniciales únicas de productos
    letras = set()
    for p in productos:
        if p.nombre:
            letras.add(p.nombre[0].upper())
    letras_iniciales = sorted(list(letras))
    return render_template('admin.html', productos=productos, letras_iniciales=letras_iniciales)

@app.route('/admin/add', methods=['POST'])
@login_required
def admin_add_producto():
    nombre = request.form.get('nombre')
    precio = float(request.form.get('precio', 0))
    stock = int(request.form.get('stock', 0))
    categoria_id = int(request.form.get('categoria_id'))
    desc = request.form.get('desc')
    materiales = request.form.get('materiales', '')
    colores_raw = request.form.get('colores', '')
    # Sort colors alphabetically
    if colores_raw.strip():
        colores = ', '.join(sorted([c.strip() for c in colores_raw.split(',') if c.strip()], key=lambda x: x.lower()))
    else:
        colores = ''

    file = request.files.get('img')
    img_filename = 'placeholder1.png'
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        img_filename = filename

    nuevo_producto = Producto(
        nombre=nombre,
        precio=precio,
        stock=stock,
        categoria_id=categoria_id,
        desc=desc,
        materiales=materiales,
        colores=colores,
        img=img_filename,
        destacado=False
    )
    db.session.add(nuevo_producto)
    db.session.commit()

    # Handle extra images
    extra_files = request.files.getlist('extra_imgs')
    for idx, f in enumerate(extra_files):
        if f and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            img_secundaria = ImagenSecundaria(filename=fname, producto_id=nuevo_producto.id, orden=idx)
            db.session.add(img_secundaria)
    db.session.commit()

    flash('Prenda añadida correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<int:id>', methods=['POST'])
@login_required
def admin_edit_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.nombre = request.form.get('nombre')
    producto.precio = float(request.form.get('precio', 0))
    producto.stock = int(request.form.get('stock', 0))
    producto.desc = request.form.get('desc')
    producto.materiales = request.form.get('materiales', '')
    producto.colores = ', '.join(sorted([c.strip() for c in request.form.get('colores', '').split(',') if c.strip()], key=lambda x: x.lower())) if request.form.get('colores', '').strip() else ''
    producto.destacado = True if request.form.get('destacado') == 'on' else False
    
    file = request.files.get('img')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        producto.img = filename
        
    extra_files = request.files.getlist('extra_imgs')
    for f in extra_files:
        if f and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_secundaria = ImagenSecundaria(filename=filename, producto_id=producto.id)
            db.session.add(img_secundaria)
        
    db.session.commit()
    flash('Producto actualizado correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_image/<int:id>', methods=['POST'])
@login_required
def admin_delete_image(id):
    img = ImagenSecundaria.query.get_or_404(id)
    db.session.delete(img)
    db.session.commit()
    
    # Check if it's an AJAX request
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True, 'message': 'Imagen eliminada correctamente.'}
    
    flash('Imagen secundaria eliminada.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_producto(id):
    producto = Producto.query.get_or_404(id)
    nombre = producto.nombre
    db.session.delete(producto)
    db.session.commit()
    
    # Check if it's an AJAX request
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True, 'message': f'Producto "{nombre}" eliminado correctamente.'}
    
    flash('Producto eliminado.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_visibility/<int:id>', methods=['POST'])
@login_required
def admin_toggle_visibility(id):
    producto = Producto.query.get_or_404(id)
    producto.oculto = not producto.oculto
    db.session.commit()
    estado = 'ocultado' if producto.oculto else 'mostrado'
    
    # Check if it's an AJAX request
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'success': True, 'oculto': producto.oculto, 'message': f'Producto {estado} correctamente.'}
    
    flash(f'Producto {estado} correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reorder_images/<int:product_id>', methods=['POST'])
@login_required
def admin_reorder_images(product_id):
    data = request.get_json()
    new_order = data.get('order', [])
    for index, img_id in enumerate(new_order):
        img = ImagenSecundaria.query.get(int(img_id))
        if img and img.producto_id == product_id:
            img.orden = index
    db.session.commit()
    return {'ok': True}

@app.route('/sitemap.xml')
def sitemap():
    from flask import Response
    import datetime
    from urllib.parse import quote
    productos = Producto.query.all()
    pages = [
        ('https://www.tejidosmargot.com.ar/', '1.0', 'weekly'),
        ('https://www.tejidosmargot.com.ar/productos', '0.9', 'weekly'),
    ]
    for p in productos:
        url = f"https://www.tejidosmargot.com.ar/producto/{quote(p.nombre)}"
        pages.append((url, '0.8', 'monthly'))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    today = datetime.date.today().isoformat()
    for loc, priority, changefreq in pages:
        xml += f'  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>{changefreq}</changefreq>\n    <priority>{priority}</priority>\n  </url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    from flask import Response
    txt = "User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: https://www.tejidosmargot.com.ar/sitemap.xml"
    return Response(txt, mimetype='text/plain')

@app.template_filter('sort_colors')
def sort_colors_filter(colores_str):
    if not colores_str:
        return colores_str
    colors = [c.strip() for c in colores_str.split(',') if c.strip()]
    return ', '.join(sorted(colors, key=lambda x: x.lower()))

@app.route('/admin/add_categoria', methods=['POST'])
@login_required
def admin_add_categoria():
    nombre = request.form.get('nombre_categoria', '').strip()
    if nombre:
        existing = Categoria.query.filter(Categoria.nombre.ilike(nombre)).first()
        if existing:
            flash(f'La categoría "{nombre}" ya existe.', 'error')
        else:
            nueva = Categoria(nombre=nombre)
            db.session.add(nueva)
            db.session.commit()
            flash(f'Categoría "{nombre}" creada correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.context_processor
def inject_categorias():
    return dict(todas_las_categorias=Categoria.query.all())

init_db()

if __name__ == '__main__':
    app.run(debug=DEBUG_MODE)