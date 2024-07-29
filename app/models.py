from sqlalchemy import Column, Integer, String, Date, Float
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)
    company_name = Column(String)

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    fecha_solicitud = Column(Date)
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
    archivo = Column(String)  # Nuevo campo para almacenar la ruta del archivo
