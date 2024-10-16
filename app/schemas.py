from pydantic import BaseModel
from datetime import date
from typing import Optional

class UserBase(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    company_name: Optional[str] = None
    cargo: Optional[str] = None
    dni: Optional[str] = None
    zona_venta: Optional[str] = None
    area: Optional[str] = None
    ceco: Optional[str] = None
    gerencia:Optional[str] = None
    jefe_id: Optional[int] = None
    cuenta_bancaria:Optional[str] = None
    banco :Optional[str] = None

class UserCreate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str
    password: str

class DocumentoBase(BaseModel):
    id: Optional[int] = None
    fecha_solicitud: Optional[date] = None
    fecha_rendicion: Optional[date] = None
    dni: Optional[str] = None
    usuario: Optional[str] = None
    gerencia: Optional[str] = None
    ruc: Optional[str] = None
    proveedor: Optional[str] = None
    fecha_emision: Optional[date] = None
    moneda: Optional[str] = None
    tipo_documento: Optional[str] = None
    serie: Optional[str] = None
    correlativo: Optional[str] = None
    tipo_gasto: Optional[str] = None
    sub_total: Optional[float] = None
    igv: Optional[float] = None
    no_gravadas: Optional[float] = None
    importe_facturado: Optional[float] = None
    tc: Optional[float] = None
    anticipo: Optional[float] = None
    total: Optional[float] = None
    pago: Optional[float] = None
    detalle: Optional[str] = None
    estado: Optional[str] = None
    empresa: Optional[str] = None
    archivo: Optional[str] = None
    tipo_solicitud: Optional[str] = None
    tipo_cambio: Optional[float] = None
    afecto: Optional[float] = None
    inafecto: Optional[float] = None
    rubro: Optional[str] = None
    cuenta_contable: Optional[int] = None

    # Nuevos campos añadidos
    responsable: Optional[str] = None
    area: Optional[str] = None
    ceco: Optional[str] = None
    tipo_anticipo: Optional[str] = None
    motivo: Optional[str] = None
    fecha_viaje: Optional[date] = None
    dias: Optional[int] = None
    presupuesto: Optional[float] = None
    banco: Optional[str] = None
    numero_cuenta: Optional[str] = None
    destino: Optional[str] = None
    origen: Optional[str] = None
    numero_rendicion: Optional[str] = None
    tipo_viaje: Optional[str] = None

class DocumentoCreate(DocumentoBase):
    pass

class Documento(DocumentoBase):
    id: int

    class Config:
        from_attributes = True

class DocumentoUpdate(BaseModel):
    estado: Optional[str] = None
    fecha_rendicion: Optional[date] = None

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

class TipoCambioResponse(BaseModel):
    precioCompra: float
    precioVenta: float
    moneda: str
    fecha: str

class RendicionBase(BaseModel):
    nombre: str

class RendicionCreate(RendicionBase):
    idUser: int

class Rendicion(RendicionBase):
    id: int
    idUser: int

    class Config:
        from_attributes = True

class RendicionCreateResponse(BaseModel):
    id: int
    idUser: int
    nombre: str

    class Config:
        from_attributes = True

