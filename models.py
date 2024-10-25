from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    
    gastos = db.relationship('Gasto', backref='usuario', lazy=True)  # Relación entre la class usuario y class gastos
    ingresos = db.relationship('Ingreso', backref='usuario', lazy=True) # Relación entre la class usuario e class ingresos
    presupuesto = db.relationship('Presupuesto', backref='usuario', lazy=True) # Relación entre Usuario y Presupuesto

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))  
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Presupuesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)  # Nombre del presupuesto
    descripcion = db.Column(db.String(500))  # Descripción del presupuesto
    monto_total = db.Column(db.Float, nullable=False)  # Monto total asignado
    fecha_inicio = db.Column(db.Date, nullable=False)  # Fecha de inicio
    fecha_fin = db.Column(db.Date, nullable=False)  # Fecha de fin
    estado = db.Column(db.String(20), default='Activo')  # Estado del presupuesto (Activo, Completado, Cancelado)

    # Relación con los detalles del presupuesto
    detalles = db.relationship(
        'PresupuestoDetalle', 
        backref='presupuesto', 
        lazy=True,
        cascade='all, delete-orphan'
    )

    def calcular_monto_gastado(self):
        # Sumar todos los montos donde tipo es 0 (gastos)
        return sum(detalle.monto for detalle in self.detalles if detalle.tipo == 0)
    
    def calcular_monto_ingresado(self):
        # Sumar todos los montos donde tipo es 1 (ingresos)
        return sum(detalle.monto for detalle in self.detalles if detalle.tipo == 1)

    def calcular_monto_restante(self):
        # Restar el monto gastado del monto total asignado
        return self.monto_total + self.calcular_monto_ingresado() - self.calcular_monto_gastado()

    def __repr__(self):
        return f'<Presupuesto {self.nombre}, Usuario {self.user_id}>'


class PresupuestoDetalle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    presupuesto_id = db.Column(db.Integer, db.ForeignKey('presupuesto.id'), nullable=False)
    tipo = db.Column(db.Integer, nullable=False)  # Tipo: 0 = Gasto, 1 = Ingreso
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_asignacion = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f'<Detalle Presupuesto {self.presupuesto_id}, Tipo {self.tipo}>'


class LoginHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))  
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, ip_address):
        self.ip_address = ip_address



