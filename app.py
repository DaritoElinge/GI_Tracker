import re
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from models import db, Usuario, Gasto, Ingreso, Presupuesto, PresupuestoDetalle, LoginHistory
from flask_migrate import Migrate
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///GI_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)

# Configurar LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirige a la página de login si no estás autenticado

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/', endpoint='inicio')
def index():
    return render_template('inicio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_login = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()
        
        # Verificar la contraseña ingresada
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)  # Iniciar sesión con Flask-Login
            
            # Registrar la IP del usuario
            ip_address = request.remote_addr
            login_entry = LoginHistory(ip_address=ip_address)
            db.session.add(login_entry)
            db.session.commit()

            return redirect(url_for('home'))
        else:
            error_login = "Acceso Inválido. Por favor, inténtelo nuevamente."

    return render_template('login.html', error_login=error_login)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_register = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Verificar si el usuario ya existe
        existing_user = Usuario.query.filter_by(username=username).first()

        if len(password) < 8:
            error_register = "La contraseña debe tener al menos 8 caracteres."
        elif not re.match(r'^[a-zA-Z0-9]*$', password):
            error_register = "La contraseña solo puede contener letras y números."
        elif existing_user:
            error_register = 'El nombre de usuario ya está en uso. Por favor, elige otro.'
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = Usuario(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))

    return render_template('register.html', error_register=error_register)

@app.route('/home')
@login_required  # Asegura que solo usuarios logueados puedan acceder
def home():
    ingresos_totales = db.session.query(db.func.sum(Ingreso.amount)).filter_by(user_id=current_user.id).scalar() or 0
    gastos_totales = db.session.query(db.func.sum(Gasto.amount)).filter_by(user_id=current_user.id).scalar() or 0
    presupuesto_disponible = ingresos_totales - gastos_totales

    return render_template('home.html', ingresos_totales=ingresos_totales, gastos_totales=gastos_totales, 
presupuesto_disponible=presupuesto_disponible)

# Endpoints o Rutas para los diversos módulos de GI-Tracker
# Ruta.- Módulo de gastos
@app.route('/gastos', methods=['GET', 'POST', 'DELETE'])
@login_required
def listar_gastos():
    if request.method == 'POST':
        try:
            date_str = request.form['date']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            new_gasto = Gasto(
                amount=float(request.form['amount']),
                category=request.form['category'],
                description=request.form['description'],
                date=date_obj,
                user_id=current_user.id
            )
            db.session.add(new_gasto)
            db.session.commit()
            
            # Obtener la lista actualizada de gastos y el total
            gastos = Gasto.query.filter_by(user_id=current_user.id).all()
            total_gasto = sum(gasto.amount for gasto in gastos)
            
            # Devolver la respuesta en formato JSON
            gastos_data = [{'id': gasto.id, 'date': gasto.date.strftime('%Y-%m-%d'), 'category': gasto.category, 'description': gasto.description, 'amount': gasto.amount} for gasto in gastos]
            return jsonify({'gastos': gastos_data, 'total_gasto': total_gasto}), 200
        
        except Exception as e:
            db.session.rollback()
            print(e)  # Para depuración
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            gasto_id = int(request.form['id'])
            gasto = Gasto.query.get_or_404(gasto_id)
            if gasto.user_id == current_user.id:
                db.session.delete(gasto)
                db.session.commit()
                
                # Obtener la lista actualizada de gastos y el total
                gastos = Gasto.query.filter_by(user_id=current_user.id).all()
                total_gasto = sum(gasto.amount for gasto in gastos)
                
                # Devolver la respuesta en formato JSON
                gastos_data = [{'id': gasto.id, 'date': gasto.date.strftime('%Y-%m-%d'), 'category': gasto.category, 'description': gasto.description, 'amount': gasto.amount} for gasto in gastos]
                return jsonify({'gastos': gastos_data, 'total_gasto': total_gasto}), 200
            else:
                return jsonify({'message': 'No tienes permiso para eliminar este gasto'}), 403
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
        
    elif request.method == 'GET':
        # Obtener la lista de gastos y el total para devolver al cargar la página
        gastos = Gasto.query.filter_by(user_id=current_user.id).all()
        total_gasto = sum(gasto.amount for gasto in gastos)
        
        # Renderizar la plantilla HTML y pasarle los gastos y el total
        return render_template('listar_gastos.html', gastos=gastos, total_gasto=total_gasto)


#Ruta.- Módulo de ingresos
@app.route('/ingresos', methods=['GET', 'POST', 'DELETE'])
@login_required
def listar_ingresos():
    if request.method == 'POST':
        try:
            date_str = request.form['date']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

            new_ingreso = Ingreso(
                amount=float(request.form['amount']),
                category=request.form['category'],
                date=date_obj,
                user_id=current_user.id
            )
            db.session.add(new_ingreso)
            db.session.commit()

            ingresos = Ingreso.query.filter_by(user_id=current_user.id).all()
            total_ingreso = sum(ingreso.amount for ingreso in ingresos)

            ingresos_data = [{'id': ingreso.id, 'date': ingreso.date.strftime('%Y-%m-%d'), 'category': ingreso.category, 'amount': ingreso.amount} for ingreso in ingresos]
            return jsonify({'ingresos': ingresos_data, 'total_ingreso': total_ingreso}), 200
        
        except Exception as e:
            db.session.rollback()
            print(e)  # Para depuración
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            ingreso_id = int(request.form['id'])
            ingreso = Ingreso.query.get_or_404(ingreso_id)
            if ingreso.user_id == current_user.id:
                db.session.delete(ingreso)
                db.session.commit()

                ingresos = Ingreso.query.filter_by(user_id=current_user.id).all()
                total_ingreso = sum(ingreso.amount for ingreso in ingresos)

                ingresos_data = [{'id': ingreso.id, 'date': ingreso.date.strftime('%Y-%m-%d'), 'category': ingreso.category, 'amount': ingreso.amount} for ingreso in ingresos]
                return jsonify({'ingresos': ingresos_data, 'total_ingreso': total_ingreso}), 200
            else:
                return jsonify({'message': 'No tienes permiso para eliminar este ingreso'}), 403
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    elif request.method == 'GET':
        ingresos = Ingreso.query.filter_by(user_id=current_user.id).all()
        total_ingreso = sum(ingreso.amount for ingreso in ingresos)

        return render_template('listar_ingresos.html', ingresos=ingresos, total_ingreso=total_ingreso)

# Ruta.- Módulo de graficos
@app.route('/grafico')
@login_required
def grafico():
    # Obtener los ingresos y gastos del usuario
    ingresos = round(sum([ingreso.amount for ingreso in current_user.ingresos]),2)
    gastos = round(sum([gasto.amount for gasto in current_user.gastos]),2)
    
    saldo = round(ingresos - gastos, 2)  # Calcula el saldo restante

    # Categorías y montos de los gastos para el gráfico
    categorias_gastos = {}
    for gasto in current_user.gastos:
        if gasto.category in categorias_gastos:
            categorias_gastos[gasto.category] += gasto.amount
        else:
            categorias_gastos[gasto.category] = gasto.amount

    return render_template('grafico.html', ingresos=ingresos, gastos=gastos, saldo=saldo, categorias_gastos=categorias_gastos)

# Ruta.- Módulo de agregar presupuesto
@app.route('/presupuesto', methods=['GET', 'POST', 'DELETE'])
@login_required
def presupuesto():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        monto_total = request.form.get('monto_total')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not nombre or not monto_total or not start_date or not end_date:
            return jsonify({'status': 'error', 'message': 'Todos los campos son obligatorios.'}), 400

        try:
            monto_total = float(monto_total)
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Formato de fecha incorrecto o monto inválido.'}), 400

        nuevo_presupuesto = Presupuesto(
            user_id=current_user.id,
            nombre=nombre,
            descripcion=descripcion,
            monto_total=monto_total,
            fecha_inicio=start_date,
            fecha_fin=end_date
        )
        db.session.add(nuevo_presupuesto)
        db.session.commit()

        presupuestos = Presupuesto.query.filter_by(user_id=current_user.id).all()
        presupuestos_data = [
            {
                'id': p.id,
                'nombre': p.nombre,
                'descripcion': p.descripcion,
                'monto_total': p.monto_total,
                'fecha_inicio': p.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': p.fecha_fin.strftime('%Y-%m-%d'),
            } for p in presupuestos
        ]

        return jsonify({'presupuestos': presupuestos_data})

    elif request.method == 'DELETE':
        data = request.get_json()
        presupuesto_id = data.get('id')
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if presupuesto and presupuesto.user_id == current_user.id:
            db.session.delete(presupuesto)
            db.session.commit()
            presupuestos = Presupuesto.query.filter_by(user_id=current_user.id).all()
            return jsonify({
                'presupuestos': [{
                    'id': p.id,
                    'nombre': p.nombre,
                    'descripcion': p.descripcion,
                    'monto_total': p.monto_total,
                    'fecha_inicio': p.fecha_inicio.strftime('%Y-%m-%d'),
                    'fecha_fin': p.fecha_fin.strftime('%Y-%m-%d'),
                } for p in presupuestos]
            })
        return jsonify({'status': 'error', 'message': 'Presupuesto no encontrado.'}), 404

    presupuestos = Presupuesto.query.filter_by(user_id=current_user.id).all()
    return render_template('presupuesto.html', presupuestos=presupuestos)

# Ruta.- Módulo para manejar detalle de un presupuesto, calcular el monto restante a partir de monto gastado e ingresado
@app.route('/presupuestodetalle/<int:id>', methods=['GET', 'POST', 'DELETE'])
@login_required
def presupuesto_detalle(id):
    presupuesto = Presupuesto.query.get_or_404(id)
    
    # Verificar que el usuario actual sea el propietario del presupuesto
    if presupuesto.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        data = request.get_json()  # Obtener los datos del cuerpo del JSON
        descripcion = data.get('descripcion')
        monto = float(data.get('monto'))
        tipo = int(data.get('tipo'))  # 0 = gasto, 1 = ingreso
        fecha_asignacion = datetime.strptime(data.get('fecha_asignacion'), '%Y-%m-%d').date()

        # Crear el nuevo detalle del presupuesto
        nuevo_detalle = PresupuestoDetalle(
            presupuesto_id=presupuesto.id,
            descripcion=descripcion,
            monto=monto,
            tipo=tipo,
            fecha_asignacion=fecha_asignacion
        )

        db.session.add(nuevo_detalle)
        db.session.commit()

        # Recalcular el monto restante teniendo en cuenta ingresos y gastos
        monto_restante = presupuesto.calcular_monto_restante()

        return jsonify({
            'status': 'success',
            'detalle': {
                'id': nuevo_detalle.id,
                'descripcion': nuevo_detalle.descripcion,
                'monto': nuevo_detalle.monto,
                'tipo': nuevo_detalle.tipo,
                'fecha_asignacion': nuevo_detalle.fecha_asignacion.strftime('%Y-%m-%d')
            },
            'monto_restante': monto_restante
        })

    # Para solicitudes GET, mostramos los detalles del presupuesto
    detalles = PresupuestoDetalle.query.filter_by(presupuesto_id=presupuesto.id).all()
    return render_template('presupuesto_detalle.html', presupuesto=presupuesto, detalles=detalles)

# Ruta para eliminar un detalle
@app.route('/presupuestodetalle/eliminar/<int:detalle_id>', methods=['DELETE'])
@login_required
def eliminar_detalle(detalle_id):
    detalle = PresupuestoDetalle.query.get_or_404(detalle_id)
    
    # Verificar que el detalle pertenece al presupuesto del usuario
    if detalle.presupuesto.user_id != current_user.id:
        abort(403)
    
    # Eliminar el detalle
    db.session.delete(detalle)
    db.session.commit()

    # Recalcular el monto restante después de eliminar el detalle
    presupuesto = detalle.presupuesto
    monto_restante = presupuesto.calcular_monto_restante()

    return jsonify({
        'status': 'success',
        'monto_restante': monto_restante
    })


# Ruta.- Módulo de reporte
@app.route('/seleccionar_reporte')
@login_required
def seleccionar_reporte():
    current_year = datetime.now().year
    years = list(range(current_year - 3, current_year + 1))
    meses = [
        {'nombre': 'Enero', 'numero': 1},
        {'nombre': 'Febrero', 'numero': 2},
        {'nombre': 'Marzo', 'numero': 3},
        {'nombre': 'Abril', 'numero': 4},
        {'nombre': 'Mayo', 'numero': 5},
        {'nombre': 'Junio', 'numero': 6},
        {'nombre': 'Julio', 'numero': 7},
        {'nombre': 'Agosto', 'numero': 8},
        {'nombre': 'Septiembre', 'numero': 9},
        {'nombre': 'Octubre', 'numero': 10},
        {'nombre': 'Noviembre', 'numero': 11},
        {'nombre': 'Diciembre', 'numero': 12}
    ]
    return render_template('seleccionar_reporte.html', meses=meses, years=years)

@app.route('/reporte', methods=['POST'])
@login_required
def reporte():
    year = int(request.form.get('year'))
    month = int(request.form.get('month'))
    
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1).date()

    ingresos = [ingreso for ingreso in current_user.ingresos if start_date <= ingreso.date < end_date]
    gastos = [gasto for gasto in current_user.gastos if start_date <= gasto.date < end_date]

    total_ingresos = sum(ingreso.amount for ingreso in ingresos)
    total_gastos = sum(gasto.amount for gasto in gastos)
    saldo = round(total_ingresos - total_gastos, 2)

    return render_template('reporte.html', ingresos=ingresos, gastos=gastos, total_ingresos=total_ingresos, total_gastos=total_gastos, saldo=saldo, month=month, year=year)

#Módulo de Historial de Login
@app.route('/login_history')
@login_required
def login_history():
    login_entries = LoginHistory.query.all()
    return render_template('login_history.html', login_entries=login_entries)


# Módulo de cerrar sesión con Flask-Login
@app.route('/logout')
@login_required
def logout():
    logout_user()  
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
