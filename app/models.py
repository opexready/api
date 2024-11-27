from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)
    company_name = Column(String)
    cargo = Column(String)
    dni = Column(String)
    zona_venta = Column(String)
    area = Column(String)
    ceco = Column(String)
    gerencia = Column(String)
    jefe_id = Column(Integer, ForeignKey('users.id'))  # Relación de ForeignKey
    jefe = relationship("User", remote_side=[id])  # Relación para referenciar al jefe
    cuenta_bancaria = Column(String) 
    banco = Column(String) 

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    fecha_solicitud = Column(Date)
    fecha_rendicion = Column(Date)
    dni = Column(String)
    usuario = Column(String)
    gerencia = Column(String)
    ruc = Column(String)
    proveedor = Column(String)
    fecha_emision = Column(Date)
    moneda = Column(String)
    tipo_documento = Column(String)
    serie = Column(String)
    correlativo = Column(String)
    tipo_gasto = Column(String)
    sub_total = Column(Float)
    igv = Column(Float)
    no_gravadas = Column(Float)
    importe_facturado = Column(Float)
    tc = Column(Float)
    anticipo = Column(Float)
    total = Column(Float)
    pago = Column(Float)
    detalle = Column(String)
    estado = Column(String)
    empresa = Column(String)
    archivo = Column(String)
    tipo_solicitud = Column(String)
    tipo_cambio = Column(Float)
    afecto = Column(Float)
    inafecto = Column(Float)
    rubro = Column(String)
    cuenta_contable = Column(Integer)

    # Nuevos campos añadidos
    responsable = Column(String)
    area = Column(String)
    ceco = Column(String)
    tipo_anticipo = Column(String)
    motivo = Column(String)
    fecha_viaje = Column(Date)
    dias = Column(Integer)
    presupuesto = Column(Float)
    banco = Column(String)
    numero_cuenta = Column(String)
    origen = Column(String)
    destino = Column(String)
    numero_rendicion = Column(String)
    tipo_viaje = Column(String)
  

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)

class Rendicion(Base):
    __tablename__ = "rendicion"

    id = Column(Integer, primary_key=True, index=True)
    idUser = Column(Integer, ForeignKey('users.id'), nullable=False)  # Llave foránea a la tabla users
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=True)  # Nuevo campo tipo
    estado = Column(String, nullable=True)  # Nuevo campo estado
    fecha_registro = Column(Date)  # Campo fecha_registro con valor por defecto
    fecha_actualizacion = Column(Date)  # Campo fecha_actualizacion

    # Relación con la tabla users
    user = relationship("User")

class Solicitud(Base):
    __tablename__ = "solicitud"

    id = Column(Integer, primary_key=True, index=True)
    idUser = Column(Integer, ForeignKey('users.id'), nullable=False)  # Llave foránea a la tabla users
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=True)
    estado = Column(String, nullable=True)
    fecha_registro = Column(Date)
    fecha_actualizacion = Column(Date)

    # Relación con la tabla users
    user = relationship("User")

class RendicionSolicitud(Base):
    __tablename__ = "rendicion_solicitud"

    id = Column(Integer, primary_key=True, index=True)
    rendicion_id = Column(Integer, ForeignKey('rendicion.id'), nullable=False)
    solicitud_id = Column(Integer, ForeignKey('solicitud.id'), nullable=False)
    fecha_creacion = Column(Date, default=datetime.utcnow)  # Fecha de creación con valor por defecto
    fecha_actualizacion = Column(Date, onupdate=datetime.utcnow)  # Fecha de actualización con auto-update
    estado = Column(String, nullable=True)  # Campo estado

    # Relaciones
    rendicion = relationship("Rendicion", backref="rendicion_solicitudes")
    solicitud = relationship("Solicitud", backref="rendicion_solicitudes")