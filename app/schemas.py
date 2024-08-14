from pydantic import BaseModel
from datetime import date
from typing import Optional

class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    role: str
    company_name: str
    cargo: Optional[str] = None  # Nuevo campo
    dni: Optional[str] = None  # Nuevo campo
    zona_venta: Optional[str] = None
    jefe_id: Optional[int] = None  # Nuevo campo

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
    archivo: Optional[str] = None
    tipo_cambio: Optional[float] = None  # Nuevo campo agregado
    afecto: Optional[float] = None  # Nuevo campo agregado
    inafecto: Optional[float] = None  # Nuevo campo agregado
    rubro: Optional[str] = None  # Nuevo campo agregado
    cuenta_contable: Optional[int] = None  # Nuevo campo agregado


class DocumentoCreate(DocumentoBase):
    pass

class Documento(DocumentoBase):
    id: int

    class Config:
        from_attributes = True

# Nuevo esquema para actualización parcial
class DocumentoUpdate(BaseModel):
    estado: Optional[str] = None

class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int

    class Config:
        from_attributes = True

class UserWithPendingDocuments(BaseModel):
    username: str
    full_name: str
    email: str
    company_name: str
    cantidad_documentos_pendientes: int
