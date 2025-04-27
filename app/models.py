from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, index=True)
    hashed_password = Column(String)
    role = Column(String)
    company_name = Column(String)
    cargo = Column(String)
    dni = Column(String)
    zona_venta = Column(String)
    area = Column(String)
    ceco = Column(String)
    gerencia = Column(String)
    jefe_id = Column(Integer, ForeignKey('users.id'))
    jefe = relationship("User", remote_side=[id])
    cuenta_bancaria = Column(String)
    banco = Column(String)
    id_empresa = Column(Integer, ForeignKey('companies.id'), nullable=True)
    # Especifica la clave foránea en la relación con Empresa
    empresa = relationship("Company", back_populates="usuarios", foreign_keys=[id_empresa]) 
    estado = Column(Boolean, default=True)

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    fecha_solicitud = Column(Date, server_default=func.now())
    fecha_rendicion = Column(Date, nullable=True)
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
    id_user = Column(Integer, ForeignKey('users.id'))  
    id_numero_rendicion = Column(Integer)
    id_empresa = Column(Integer, ForeignKey('companies.id'), nullable=True)

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    id_user = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Specify the foreign key in the relationship
    usuarios = relationship("User", back_populates="empresa", foreign_keys='User.id_empresa')

class Rendicion(Base):
    __tablename__ = "rendicion"

    id = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, ForeignKey('users.id'), nullable=False)  
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=True)  
    estado = Column(String, nullable=True)  
    fecha_registro = Column(Date, server_default=func.now())  
    fecha_actualizacion = Column(Date, onupdate=func.now())  
    id_empresa = Column(Integer, ForeignKey('companies.id'), nullable=True)
   # Nuevos campos (todos nullable=True)
    id_aprobador = Column(Integer, ForeignKey('users.id'), nullable=True)  
    nom_aprobador = Column(String, nullable=True)  
    id_contador = Column(Integer, ForeignKey('users.id'), nullable=True)  
    nom_contador = Column(String, nullable=True)  

    # Relaciones (ESPECIFICA foreign_keys para evitar ambigüedad)
    user = relationship("User", foreign_keys=[id_user])
    aprobador = relationship("User", foreign_keys=[id_aprobador])
    contador = relationship("User", foreign_keys=[id_contador])

class Solicitud(Base):
    __tablename__ = "solicitud"

    id = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, ForeignKey('users.id'), nullable=False)  
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=True)
    estado = Column(String, nullable=True)
    fecha_registro = Column(Date, server_default=func.now())
    fecha_actualizacion = Column(Date, onupdate=func.now())
    id_empresa = Column(Integer, ForeignKey('companies.id'), nullable=True)
    # Nuevos campos (todos nullable=True)
    id_aprobador = Column(Integer, ForeignKey('users.id'), nullable=True)  
    nom_aprobador = Column(String, nullable=True)  
    id_contador = Column(Integer, ForeignKey('users.id'), nullable=True)  
    nom_contador = Column(String, nullable=True)  

    # Relaciones (ESPECIFICA foreign_keys para evitar ambigüedad)
    user = relationship("User", foreign_keys=[id_user])
    aprobador = relationship("User", foreign_keys=[id_aprobador])
    contador = relationship("User", foreign_keys=[id_contador])

class RendicionSolicitud(Base):
    __tablename__ = "rendicion_solicitud"

    id = Column(Integer, primary_key=True, index=True)
    rendicion_id = Column(Integer, ForeignKey('rendicion.id'), nullable=False)
    solicitud_id = Column(Integer, ForeignKey('solicitud.id'), nullable=False)
    fecha_creacion = Column(Date, server_default=func.now())  
    fecha_actualizacion = Column(Date, onupdate=func.now())  
    estado = Column(String, nullable=True)  

    rendicion = relationship("Rendicion", backref="rendicion_solicitudes")
    solicitud = relationship("Solicitud", backref="rendicion_solicitudes")
