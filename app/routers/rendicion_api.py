from datetime import date
from app import crud
from app.crud import create_rendicion_with_increment
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, not_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app import models, schemas
from sqlalchemy import distinct
from app.database import get_db  # Asegúrate de tener esta dependencia
from pydantic import BaseModel

router = APIRouter()


@router.get("/rendiciones/con-documentos/", response_model=list[dict])
async def get_rendiciones_con_documentos_filtradas(
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de rendición o solicitud"),
    estado: Optional[str] = Query(None, description="Filtrar por estado de la rendición o solicitud"),
    fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
    fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
    fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
    fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
    id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve una lista de rendiciones o solicitudes que tienen documentos asociados, aplicando filtros opcionales.
    Excluye rendiciones o solicitudes con estado "NUEVO".
    """
    try:
        # Determinar si se debe consultar la tabla rendicion o solicitud
        if tipo == "ANTICIPO":
            model = models.Solicitud
            table_name = "solicitud"
        else:
            model = models.Rendicion
            table_name = "rendicion"

        # Construir la consulta base para las rendiciones o solicitudes
        query = (
            select(model)
            .join(models.Documento, models.Documento.numero_rendicion == model.nombre)
            .where(not_(model.estado == "NUEVO"))  # Excluir estado "NUEVO"
            .distinct()
        )

        if tipo:
            query = query.where(model.tipo == tipo)
        if estado:
            query = query.where(model.estado == estado)
        if fecha_registro_from:
            query = query.where(model.fecha_registro >= fecha_registro_from)
        if fecha_registro_to:
            query = query.where(model.fecha_registro <= fecha_registro_to)
        if fecha_actualizacion_from:
            query = query.where(model.fecha_actualizacion >= fecha_actualizacion_from)
        if fecha_actualizacion_to:
            query = query.where(model.fecha_actualizacion <= fecha_actualizacion_to)
        if id_user:
            query = query.where(model.id_user == id_user)

        # Ejecutar la consulta para rendiciones o solicitudes
        resultados_query = await db.execute(query)
        resultados = resultados_query.scalars().all()

        # Crear la respuesta con los documentos relacionados
        resultado = []
        for resultado_item in resultados:
            # Buscar documentos relacionados con el nombre de la rendición o solicitud (numero_rendicion)
            documentos_query = await db.execute(
                select(models.Documento).where(models.Documento.numero_rendicion == resultado_item.nombre)
            )
            documentos = documentos_query.scalars().all()

            # Solo agregar rendiciones o solicitudes con documentos asociados
            if documentos:
                resultado.append({
                    table_name: {
                        "id": resultado_item.id,
                        "id_user": resultado_item.id_user,
                        "nombre": resultado_item.nombre,
                        "tipo": resultado_item.tipo,
                        "estado": resultado_item.estado,
                        "fecha_registro": resultado_item.fecha_registro,
                        "fecha_actualizacion": resultado_item.fecha_actualizacion,
                    },
                    "documentos": [
                        {
                            "id": doc.id,
                            "fecha_solicitud": doc.fecha_solicitud,
                            "fecha_rendicion": doc.fecha_rendicion,
                            "dni": doc.dni,
                            "usuario": doc.usuario,
                            "gerencia": doc.gerencia,
                            "ruc": doc.ruc,
                            "proveedor": doc.proveedor,
                            "fecha_emision": doc.fecha_emision,
                            "moneda": doc.moneda,
                            "tipo_documento": doc.tipo_documento,
                            "serie": doc.serie,
                            "correlativo": doc.correlativo,
                            "tipo_gasto": doc.tipo_gasto,
                            "sub_total": doc.sub_total,
                            "igv": doc.igv,
                            "no_gravadas": doc.no_gravadas,
                            "importe_facturado": doc.importe_facturado,
                            "tc": doc.tc,
                            "anticipo": doc.anticipo,
                            "total": doc.total,
                            "pago": doc.pago,
                            "detalle": doc.detalle,
                            "estado": doc.estado,
                            "empresa": doc.empresa,
                            "archivo": doc.archivo,
                            "tipo_solicitud": doc.tipo_solicitud,
                            "tipo_cambio": doc.tipo_cambio,
                            "afecto": doc.afecto,
                            "inafecto": doc.inafecto,
                            "rubro": doc.rubro,
                            "cuenta_contable": doc.cuenta_contable,
                            "responsable": doc.responsable,
                            "area": doc.area,
                            "ceco": doc.ceco,
                            "tipo_anticipo": doc.tipo_anticipo,
                            "motivo": doc.motivo,
                            "fecha_viaje": doc.fecha_viaje,
                            "dias": doc.dias,
                            "presupuesto": doc.presupuesto,
                            "banco": doc.banco,
                            "numero_cuenta": doc.numero_cuenta,
                            "origen": doc.origen,
                            "destino": doc.destino,
                            "numero_rendicion": doc.numero_rendicion,
                            "tipo_viaje": doc.tipo_viaje,
                        }
                        for doc in documentos
                    ]
                })

        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener rendiciones o solicitudes con documentos: {str(e)}")


########################
@router.get("/rendiciones-solicitudes/con-documentos/", response_model=List[dict])
async def get_rendiciones_y_solicitudes_con_documentos(
    tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
    fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
    fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
    fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
    id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve una lista combinada de rendiciones y solicitudes con sus documentos asociados, aplicando filtros opcionales.
    Excluye registros con estado "NUEVO".
    """
    try:
        # Consultas base para rendiciones y solicitudes, excluyendo estado "NUEVO"
        query_rendiciones = (
            select(models.Rendicion, models.User.full_name)
            .join(models.User, models.Rendicion.id_user == models.User.id)
            .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
            .where(models.Rendicion.estado != "NUEVO")  # Excluir estado "NUEVO"
            .distinct()
        )
        query_solicitudes = (
            select(models.Solicitud, models.User.full_name)
            .join(models.User, models.Solicitud.id_user == models.User.id)
            .join(models.Documento, models.Documento.numero_rendicion == models.Solicitud.nombre)
            .where(models.Solicitud.estado != "NUEVO")  # Excluir estado "NUEVO"
            .distinct()
        )

        # Aplicar filtros a las consultas
        if tipo:
            query_rendiciones = query_rendiciones.where(models.Rendicion.tipo == tipo)
            query_solicitudes = query_solicitudes.where(models.Solicitud.tipo == tipo)
        if estado:
            query_rendiciones = query_rendiciones.where(models.Rendicion.estado == estado)
            query_solicitudes = query_solicitudes.where(models.Solicitud.estado == estado)
        if fecha_registro_from:
            query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro >= fecha_registro_from)
            query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro >= fecha_registro_from)
        if fecha_registro_to:
            query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro <= fecha_registro_to)
            query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro <= fecha_registro_to)
        if fecha_actualizacion_from:
            query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
            query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
        if fecha_actualizacion_to:
            query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
            query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
        if id_user:
            query_rendiciones = query_rendiciones.where(models.Rendicion.id_user == id_user)
            query_solicitudes = query_solicitudes.where(models.Solicitud.id_user == id_user)

        # Ejecutar las consultas
        rendiciones_query = await db.execute(query_rendiciones)
        solicitudes_query = await db.execute(query_solicitudes)

        rendiciones = rendiciones_query.all()  # Incluye (Rendicion, full_name)
        solicitudes = solicitudes_query.all()  # Incluye (Solicitud, full_name)

        # Combinar resultados y transformar al formato esperado
        resultado = []

        # Procesar rendiciones
        for rendicion, full_name in rendiciones:
            documentos_query = await db.execute(
                select(models.Documento).where(models.Documento.numero_rendicion == rendicion.nombre)
            )
            documentos = documentos_query.scalars().all()

            if documentos:
                resultado.append({
                    "rendicion": {
                        "id": rendicion.id,
                        "id_user": rendicion.id_user,
                        "nombre": rendicion.nombre,
                        "tipo": rendicion.tipo,
                        "estado": rendicion.estado,
                        "fecha_registro": rendicion.fecha_registro,
                        "fecha_actualizacion": rendicion.fecha_actualizacion,
                        "nombre_usuario": full_name,
                    },
                    "documentos": [
                        {
                            "id": doc.id,
                            "fecha_solicitud": doc.fecha_solicitud,
                            "fecha_rendicion": doc.fecha_rendicion,
                            "dni": doc.dni,
                            "usuario": doc.usuario,
                            "gerencia": doc.gerencia,
                            "ruc": doc.ruc,
                            "proveedor": doc.proveedor,
                            "fecha_emision": doc.fecha_emision,
                            "moneda": doc.moneda,
                            "tipo_documento": doc.tipo_documento,
                            "serie": doc.serie,
                            "correlativo": doc.correlativo,
                            "tipo_gasto": doc.tipo_gasto,
                            "sub_total": doc.sub_total,
                            "igv": doc.igv,
                            "no_gravadas": doc.no_gravadas,
                            "importe_facturado": doc.importe_facturado,
                            "tc": doc.tc,
                            "anticipo": doc.anticipo,
                            "total": doc.total,
                            "pago": doc.pago,
                            "detalle": doc.detalle,
                            "estado": doc.estado,
                            "empresa": doc.empresa,
                            "archivo": doc.archivo,
                            "tipo_solicitud": doc.tipo_solicitud,
                            "tipo_cambio": doc.tipo_cambio,
                            "afecto": doc.afecto,
                            "inafecto": doc.inafecto,
                            "rubro": doc.rubro,
                            "cuenta_contable": doc.cuenta_contable,
                            "responsable": doc.responsable,
                            "area": doc.area,
                            "ceco": doc.ceco,
                            "tipo_anticipo": doc.tipo_anticipo,
                            "motivo": doc.motivo,
                            "fecha_viaje": doc.fecha_viaje,
                            "dias": doc.dias,
                            "presupuesto": doc.presupuesto,
                            "banco": doc.banco,
                            "numero_cuenta": doc.numero_cuenta,
                            "origen": doc.origen,
                            "destino": doc.destino,
                            "numero_rendicion": doc.numero_rendicion,
                            "tipo_viaje": doc.tipo_viaje,
                        }
                        for doc in documentos
                    ]
                })

        # Procesar solicitudes
        for solicitud, full_name in solicitudes:
            documentos_query = await db.execute(
                select(models.Documento).where(models.Documento.numero_rendicion == solicitud.nombre)
            )
            documentos = documentos_query.scalars().all()

            if documentos:
                resultado.append({
                    "solicitud": {
                        "id": solicitud.id,
                        "id_user": solicitud.id_user,
                        "nombre": solicitud.nombre,
                        "tipo": solicitud.tipo,
                        "estado": solicitud.estado,
                        "fecha_registro": solicitud.fecha_registro,
                        "fecha_actualizacion": solicitud.fecha_actualizacion,
                        "nombre_usuario": full_name,
                    },
                    "documentos": [
                        {
                            "id": doc.id,
                            **{key: getattr(doc, key) for key in models.Documento.__table__.columns.keys()}
                        }
                        for doc in documentos
                    ]
                })

        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    

@router.get("/rendiciones/", response_model=list[schemas.Rendicion])
async def read_rendiciones(db: AsyncSession = Depends(get_db)):
    return await crud.get_rendiciones(db)


@router.post("/rendicion/", response_model=schemas.RendicionCreateResponse)
async def create_rendicion(rendicion_request: schemas.RendicionCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        id_user = rendicion_request.id_user
        new_rendicion = await create_rendicion_with_increment(db, id_user)
        return new_rendicion
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/rendicion/last", response_model=schemas.RendicionCreateResponse)
async def get_last_rendicion(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener la última rendición por id de usuario
        result = await db.execute(
            select(models.Rendicion)
            .where(models.Rendicion.id_user == id_user)
            .where(models.Rendicion.tipo == tipo)
            .order_by(models.Rendicion.id.desc())
            .limit(1)
        )

        last_rendicion = result.scalars().first()

        if not last_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontró ninguna rendición para este usuario")

        return last_rendicion
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
class RendicionUpdate(BaseModel):
        nombre: Optional[str] = None
        tipo: Optional[str] = None
        estado: Optional[str] = None
    
@router.put("/rendicion/{rendicion_id}", response_model=dict)
async def update_rendicion(
    rendicion_id: int,
    rendicion_data: RendicionUpdate,  # Cambia esto de schemas.RendicionUpdate a RendicionUpdate
    db: AsyncSession = Depends(get_db)
):
    # Buscar la rendición por ID
    result = await db.execute(select(models.Rendicion).where(models.Rendicion.id == rendicion_id))
    db_rendicion = result.scalars().first()

    if not db_rendicion:
        raise HTTPException(status_code=404, detail="Rendición no encontrada")

    # Actualizar solo los campos proporcionados
    update_data = rendicion_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rendicion, key, value)

    # Guardar cambios
    await db.commit()
    await db.refresh(db_rendicion)

    return {"detail": "Rendición actualizada exitosamente"}

@router.get("/rendicion/nombres", response_model=list[str])
async def get_unique_rendicion_names(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener los nombres de las rendiciones sin repetir, filtradas por id_user y tipo
        result = await db.execute(
            select(distinct(models.Rendicion.nombre))
            .where(models.Rendicion.id_user == id_user, models.Rendicion.tipo == tipo)
        )

        # Obtener todos los nombres únicos de la consulta
        nombres_rendicion = result.scalars().all()

        if not nombres_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontraron rendiciones para este usuario con el tipo especificado")

        return nombres_rendicion

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/rendiciones/nombres", response_model=list[schemas.RendicionResponse])
async def get_unique_rendicion_names(id_user: int, tipo: str, db: AsyncSession = Depends(get_db)):
    try:
        # Consulta para obtener los nombres de las rendiciones sin repetir, filtradas por id_user y tipo
        result = await db.execute(
            select(models.Rendicion)
            .where(models.Rendicion.id_user == id_user, models.Rendicion.tipo == tipo)
        )

        # Obtener todos los nombres únicos de la consulta
        nombres_rendicion = result.scalars().all()

        if not nombres_rendicion:
            raise HTTPException(
                status_code=404, detail="No se encontraron rendiciones para este usuario con el tipo especificado")

        return nombres_rendicion

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RendicionUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    estado: Optional[str] = None
