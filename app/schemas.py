# app/schemas.py
from pydantic import BaseModel
from datetime import date

class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    role: str
    company_name: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str
    password: str

class DocumentoBase(BaseModel):
    fecha_solicitud: date
    dni: str
    usuario: str
    gerencia: str
    ruc: str
    proveedor: str
    fecha_emision: date
    moneda: str
    tipo_documento: str
    serie: str
    correlativo: str
    tipo_gasto: str
    sub_total: float
    igv: float
    no_gravadas: float
    importe_facturado: float
    tc: float
    anticipo: float
    total: float
    pago: float
    detalle: str
    estado: str
    empresa: str

class DocumentoCreate(DocumentoBase):
    pass

class Documento(DocumentoBase):
    id: int

    class Config:
        from_attributes = True
