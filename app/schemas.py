from pydantic import BaseModel
from datetime import date,datetime
from typing import Optional, Union

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
    username: str
    email: str
    password: Optional[str] = None
    id_empresa: Optional[int] = None  # Agregar el campo id_empresa
    estado: Optional[bool] = None
    id_user :Optional[int] = None

class User(UserBase):
    id: int
    id_empresa : int

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
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
    gerencia: Optional[str] = None
    jefe_id: Optional[int] = None
    cuenta_bancaria: Optional[str] = None
    banco: Optional[str] = None
    id_empresa: Optional[int] = None
    estado: Optional[bool] = None
    password: Optional[str] = None

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
    id_user: Optional[int] = None
    id_numero_rendicion: Optional[int] = None

class DocumentoCreate(DocumentoBase):
    id_empresa : int

class Documento(DocumentoBase):
    id: int

    class Config:
        from_attributes = True

class DocumentoUpdate(BaseModel):
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


class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None
    id_user: int

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int

    class Config:
        from_attributes = True

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class UserWithCompanyDescription(User):
    description: Optional[str] = None
    
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
    tipo: Optional[str] = None  # Nuevo campo tipo
    estado: Optional[str] = None  # Nuevo campo estado

class RendicionUpdate(BaseModel):
    nombre: Optional[str]
    tipo: Optional[str]
    estado: Optional[str]

class RendicionCreate(RendicionBase):
    id_user: int

class Rendicion(RendicionBase):
    id: int
    id_user: int

    class Config:
        from_attributes = True

class RendicionCreateResponse(BaseModel):
    id: int
    id_user: int
    nombre: str
    tipo: Optional[str] = None  # Nuevo campo tipo
    estado: Optional[str] = None  # Nuevo campo estado
    

    class Config:
        from_attributes = True

class RendicionCreateRequest(BaseModel):
    id_user: int
    id_empresa: int
class SolicitudCreateRequest(BaseModel):
    id_user: int
    id_empresa: int

#######################

class SolicitudBase(BaseModel):
    id_user: Optional[int]
    nombre: Optional[str]
    tipo: Optional[str]
    estado: Optional[str]
    fecha_registro: Optional[str]  # Fecha en formato YYYY-MM-DD
    fecha_actualizacion: Optional[str]

class SolicitudUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    estado: Optional[str] = None
    id_aprobador: Optional[int] = None
    id_contador: Optional[int] = None
    nom_aprobador: Optional[str] = None
    nom_contador: Optional[str] = None

class SolicitudCreate(SolicitudBase):
    id_user: int

class Solicitud(SolicitudBase):
    id: int
    id_user: int

    class Config:
        from_attributes = True

class SolicitudCreateResponse(BaseModel):
    id: Optional[int]
    id_user: Optional[int]
    nombre: Optional[str]
    tipo: Optional[str]
    estado: Optional[str]

class ErrorResponse(BaseModel):
    detail: str

class SolicitudResponse(BaseModel):
    id: int
    id_user: int
    nombre: str
    tipo: str
    estado: Optional[str] = None

    class Config:
        orm_mode = True


class RendicionResponse(BaseModel):
    id: int
    id_user: int
    nombre: str
    tipo: str
    estado: Optional[str] = None

    class Config:
        orm_mode = True


class RendicionSolicitudCreate(BaseModel):
    rendicion_id: int
    solicitud_id: int
    estado: Optional[str] = None

class RendicionSolicitudResponse(BaseModel):
    id: int
    rendicion_id: int
    solicitud_id: int
    fecha_creacion: Optional[datetime] = None  # Hacer el campo opcional
    fecha_actualizacion: Optional[datetime] = None
    estado: Optional[str] = None

class Config:
    from_attributes = True

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class RequestPasswordReset(BaseModel):
    email: str


