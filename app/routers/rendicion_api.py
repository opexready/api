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
from sqlalchemy.orm import joinedload
from fastapi.logger import logger

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
                select(models.Documento).where(models.Documento.numero_rendicion == resultado_item.nombre,
                models.Documento.id_user == resultado_item.id_user                              
                                               )
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
# @router.get("/rendiciones-solicitudes3/con-documentos/", response_model=List[dict])
# async def get_rendiciones_y_solicitudes_con_documentos(
#     tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
#     estado: Optional[str] = Query(None, description="Filtrar por estado"),
#     fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
#     fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
#     fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
#     fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
#     id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Devuelve una lista combinada de rendiciones y solicitudes con sus documentos asociados, aplicando filtros opcionales.
#     Excluye registros con estado "NUEVO".
#     """
#     try:
#         # Consultas base para rendiciones y solicitudes, excluyendo estado "NUEVO"
#         query_rendiciones = (
#             select(models.Rendicion, models.User.full_name)
#             .join(models.User, models.Rendicion.id_user == models.User.id)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
#             .where(models.Rendicion.estado != "NUEVO")  # Excluir estado "NUEVO"
#             .distinct()
#         )
#         query_solicitudes = (
#             select(models.Solicitud, models.User.full_name)
#             .join(models.User, models.Solicitud.id_user == models.User.id)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Solicitud.nombre)
#             .where(models.Solicitud.estado != "NUEVO")  # Excluir estado "NUEVO"
#             .distinct()
#         )

#         # Aplicar filtros a las consultas
#         if tipo:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.tipo == tipo)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.tipo == tipo)
#         if estado:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.estado == estado)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.estado == estado)
#         if fecha_registro_from:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro >= fecha_registro_from)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro >= fecha_registro_from)
#         if fecha_registro_to:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_registro <= fecha_registro_to)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_registro <= fecha_registro_to)
#         if fecha_actualizacion_from:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
#         if fecha_actualizacion_to:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
#         if id_user:
#             query_rendiciones = query_rendiciones.where(models.Rendicion.id_user == id_user)
#             query_solicitudes = query_solicitudes.where(models.Solicitud.id_user == id_user)

#         # Ejecutar las consultas
#         rendiciones_query = await db.execute(query_rendiciones)
#         solicitudes_query = await db.execute(query_solicitudes)

#         rendiciones = rendiciones_query.all()  # Incluye (Rendicion, full_name)
#         solicitudes = solicitudes_query.all()  # Incluye (Solicitud, full_name)

#         # Combinar resultados y transformar al formato esperado
#         resultado = []

#         # Procesar rendiciones
#         for rendicion, full_name in rendiciones:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(models.Documento.numero_rendicion == rendicion.nombre)
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": rendicion.id,
#                         "id_user": rendicion.id_user,
#                         "nombre": rendicion.nombre,
#                         "tipo": rendicion.tipo,
#                         "estado": rendicion.estado,
#                         "fecha_registro": rendicion.fecha_registro,
#                         "fecha_actualizacion": rendicion.fecha_actualizacion,
#                         "nombre_usuario": full_name,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             "fecha_solicitud": doc.fecha_solicitud,
#                             "fecha_rendicion": doc.fecha_rendicion,
#                             "dni": doc.dni,
#                             "usuario": doc.usuario,
#                             "gerencia": doc.gerencia,
#                             "ruc": doc.ruc,
#                             "proveedor": doc.proveedor,
#                             "fecha_emision": doc.fecha_emision,
#                             "moneda": doc.moneda,
#                             "tipo_documento": doc.tipo_documento,
#                             "serie": doc.serie,
#                             "correlativo": doc.correlativo,
#                             "tipo_gasto": doc.tipo_gasto,
#                             "sub_total": doc.sub_total,
#                             "igv": doc.igv,
#                             "no_gravadas": doc.no_gravadas,
#                             "importe_facturado": doc.importe_facturado,
#                             "tc": doc.tc,
#                             "anticipo": doc.anticipo,
#                             "total": doc.total,
#                             "pago": doc.pago,
#                             "detalle": doc.detalle,
#                             "estado": doc.estado,
#                             "empresa": doc.empresa,
#                             "archivo": doc.archivo,
#                             "tipo_solicitud": doc.tipo_solicitud,
#                             "tipo_cambio": doc.tipo_cambio,
#                             "afecto": doc.afecto,
#                             "inafecto": doc.inafecto,
#                             "rubro": doc.rubro,
#                             "cuenta_contable": doc.cuenta_contable,
#                             "responsable": doc.responsable,
#                             "area": doc.area,
#                             "ceco": doc.ceco,
#                             "tipo_anticipo": doc.tipo_anticipo,
#                             "motivo": doc.motivo,
#                             "fecha_viaje": doc.fecha_viaje,
#                             "dias": doc.dias,
#                             "presupuesto": doc.presupuesto,
#                             "banco": doc.banco,
#                             "numero_cuenta": doc.numero_cuenta,
#                             "origen": doc.origen,
#                             "destino": doc.destino,
#                             "numero_rendicion": doc.numero_rendicion,
#                             "tipo_viaje": doc.tipo_viaje,
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         # Procesar solicitudes
#         for solicitud, full_name in solicitudes:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(models.Documento.numero_rendicion == solicitud.nombre)
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "solicitud": {
#                         "id": solicitud.id,
#                         "id_user": solicitud.id_user,
#                         "nombre": solicitud.nombre,
#                         "tipo": solicitud.tipo,
#                         "estado": solicitud.estado,
#                         "fecha_registro": solicitud.fecha_registro,
#                         "fecha_actualizacion": solicitud.fecha_actualizacion,
#                         "nombre_usuario": full_name,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             **{key: getattr(doc, key) for key in models.Documento.__table__.columns.keys()}
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         return resultado

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    

# ##################
# @router.get("/rendiciones-solicitudes/con-documentos2/", response_model=List[dict])
# async def get_rendiciones_y_solicitudes_con_documentos(
#     tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
#     estado: Optional[str] = Query(None, description="Filtrar por estado"),
#     fecha_registro_from: Optional[date] = Query(
#         None, description="Filtrar desde esta fecha de registro"),
#     fecha_registro_to: Optional[date] = Query(
#         None, description="Filtrar hasta esta fecha de registro"),
#     fecha_actualizacion_from: Optional[date] = Query(
#         None, description="Filtrar desde esta fecha de actualización"),
#     fecha_actualizacion_to: Optional[date] = Query(
#         None, description="Filtrar hasta esta fecha de actualización"),
#     id_user: Optional[int] = Query(
#         None, description="Filtrar por ID de usuario"),
#     id_empresa: Optional[int] = Query(
#         None, description="Filtrar por ID de empresa"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Devuelve una lista combinada de rendiciones y solicitudes con sus documentos asociados, aplicando filtros opcionales.
#     """
#     try:
#         # Consultas base para rendiciones y solicitudes
#         query_rendiciones = (
#             select(models.Rendicion, models.User.full_name)
#             .join(models.User, models.Rendicion.id_user == models.User.id)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Rendicion.nombre)
#             .where(models.Rendicion.estado != "NUEVO")
#             .distinct()
#         )
#         query_solicitudes = (
#             select(models.Solicitud, models.User.full_name)
#             .join(models.User, models.Solicitud.id_user == models.User.id)
#             .join(models.Documento, models.Documento.numero_rendicion == models.Solicitud.nombre)
#             .where(models.Solicitud.estado != "NUEVO")
#             .distinct()
#         )

#         # Aplicar filtros a las consultas
#         if tipo:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.tipo == tipo)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.tipo == tipo)
#         if estado:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.estado == estado)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.estado == estado)
#         if fecha_registro_from:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.fecha_registro >= fecha_registro_from)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.fecha_registro >= fecha_registro_from)
#         if fecha_registro_to:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.fecha_registro <= fecha_registro_to)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.fecha_registro <= fecha_registro_to)
#         if fecha_actualizacion_from:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
#         if fecha_actualizacion_to:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
#         if id_user:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.id_user == id_user)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.id_user == id_user)
#         if id_empresa:
#             query_rendiciones = query_rendiciones.where(
#                 models.Rendicion.id_empresa == id_empresa)
#             query_solicitudes = query_solicitudes.where(
#                 models.Solicitud.id_empresa == id_empresa)

#         # Ejecutar las consultas
#         rendiciones_query = await db.execute(query_rendiciones)
#         solicitudes_query = await db.execute(query_solicitudes)

#         rendiciones = rendiciones_query.all()  # Incluye (Rendicion, full_name)
#         solicitudes = solicitudes_query.all()  # Incluye (Solicitud, full_name)

#         # Combinar resultados y transformar al formato esperado
#         resultado = []

#         # Procesar rendiciones
#         for rendicion, full_name in rendiciones:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(
#                     models.Documento.id_numero_rendicion == rendicion.id,
#                     models.Documento.estado != "RECHAZADO"  # Filtro añadido
#                 )
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": rendicion.id,
#                         "id_user": rendicion.id_user,
#                         "nombre": rendicion.nombre,
#                         "tipo": rendicion.tipo,
#                         "estado": rendicion.estado,
#                         "fecha_registro": rendicion.fecha_registro,
#                         "fecha_actualizacion": rendicion.fecha_actualizacion,
#                         "nombre_usuario": full_name,
#                         "id_empresa": rendicion.id_empresa,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             "fecha_solicitud": doc.fecha_solicitud,
#                             "fecha_rendicion": doc.fecha_rendicion,
#                             "dni": doc.dni,
#                             "usuario": doc.usuario,
#                             "gerencia": doc.gerencia,
#                             "ruc": doc.ruc,
#                             "proveedor": doc.proveedor,
#                             "fecha_emision": doc.fecha_emision,
#                             "moneda": doc.moneda,
#                             "tipo_documento": doc.tipo_documento,
#                             "serie": doc.serie,
#                             "correlativo": doc.correlativo,
#                             "tipo_gasto": doc.tipo_gasto,
#                             "sub_total": doc.sub_total,
#                             "igv": doc.igv,
#                             "no_gravadas": doc.no_gravadas,
#                             "importe_facturado": doc.importe_facturado,
#                             "tc": doc.tc,
#                             "anticipo": doc.anticipo,
#                             "total": doc.total,
#                             "pago": doc.pago,
#                             "detalle": doc.detalle,
#                             "estado": doc.estado,
#                             "empresa": doc.empresa,
#                             "archivo": doc.archivo,
#                             "tipo_solicitud": doc.tipo_solicitud,
#                             "tipo_cambio": doc.tipo_cambio,
#                             "afecto": doc.afecto,
#                             "inafecto": doc.inafecto,
#                             "rubro": doc.rubro,
#                             "cuenta_contable": doc.cuenta_contable,
#                             "responsable": doc.responsable,
#                             "area": doc.area,
#                             "ceco": doc.ceco,
#                             "tipo_anticipo": doc.tipo_anticipo,
#                             "motivo": doc.motivo,
#                             "fecha_viaje": doc.fecha_viaje,
#                             "dias": doc.dias,
#                             "presupuesto": doc.presupuesto,
#                             "banco": doc.banco,
#                             "numero_cuenta": doc.numero_cuenta,
#                             "origen": doc.origen,
#                             "destino": doc.destino,
#                             "numero_rendicion": doc.numero_rendicion,
#                             "tipo_viaje": doc.tipo_viaje,
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         # Procesar solicitudes
#         for solicitud, full_name in solicitudes:
#             documentos_query = await db.execute(
#                 select(models.Documento).where(
#                     models.Documento.id_numero_rendicion == solicitud.id,
#                     models.Documento.estado != "RECHAZADO"  # Filtro añadido
#                 )
#             )
#             documentos = documentos_query.scalars().all()

#             if documentos:
#                 resultado.append({
#                     "rendicion": {
#                         "id": solicitud.id,
#                         "id_user": solicitud.id_user,
#                         "nombre": solicitud.nombre,
#                         "tipo": solicitud.tipo,
#                         "estado": solicitud.estado,
#                         "fecha_registro": solicitud.fecha_registro,
#                         "fecha_actualizacion": solicitud.fecha_actualizacion,
#                         "nombre_usuario": full_name,
#                         "id_empresa": solicitud.id_empresa,
#                     },
#                     "documentos": [
#                         {
#                             "id": doc.id,
#                             **{key: getattr(doc, key) for key in models.Documento.__table__.columns.keys()}
#                         }
#                         for doc in documentos
#                     ]
#                 })

#         return resultado

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

###################

###################################################
@router.get("/rendiciones-solicitudes/con-documentos/", response_model=List[dict])
async def get_rendiciones_y_solicitudes_con_documentos(
    tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    fecha_registro_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de registro"),
    fecha_registro_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de registro"),
    fecha_actualizacion_from: Optional[date] = Query(None, description="Filtrar desde esta fecha de actualización"),
    fecha_actualizacion_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha de actualización"),
    id_user: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por ID de empresa"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1) Consultar padres Rendición
        q_rend = select(models.Rendicion, models.User.full_name) \
            .join(models.User, models.Rendicion.id_user == models.User.id) \
            .where(models.Rendicion.estado != "NUEVO")
        if estado:
            q_rend = q_rend.where(models.Rendicion.estado == estado)
        if fecha_registro_from:
            q_rend = q_rend.where(models.Rendicion.fecha_registro >= fecha_registro_from)
        if fecha_registro_to:
            q_rend = q_rend.where(models.Rendicion.fecha_registro <= fecha_registro_to)
        if fecha_actualizacion_from:
            q_rend = q_rend.where(models.Rendicion.fecha_actualizacion >= fecha_actualizacion_from)
        if fecha_actualizacion_to:
            q_rend = q_rend.where(models.Rendicion.fecha_actualizacion <= fecha_actualizacion_to)
        if id_user:
            q_rend = q_rend.where(models.Rendicion.id_user == id_user)
        if id_empresa:
            q_rend = q_rend.where(models.Rendicion.id_empresa == id_empresa)
        if tipo:
            q_rend = q_rend.where(models.Rendicion.tipo == tipo)

        rendiciones = (await db.execute(q_rend)).all()

        # 2) Consultar padres Solicitud
        q_sol = select(models.Solicitud, models.User.full_name) \
            .join(models.User, models.Solicitud.id_user == models.User.id) \
            .where(models.Solicitud.estado != "NUEVO")
        if estado:
            q_sol = q_sol.where(models.Solicitud.estado == estado)
        if fecha_registro_from:
            q_sol = q_sol.where(models.Solicitud.fecha_registro >= fecha_registro_from)
        if fecha_registro_to:
            q_sol = q_sol.where(models.Solicitud.fecha_registro <= fecha_registro_to)
        if fecha_actualizacion_from:
            q_sol = q_sol.where(models.Solicitud.fecha_actualizacion >= fecha_actualizacion_from)
        if fecha_actualizacion_to:
            q_sol = q_sol.where(models.Solicitud.fecha_actualizacion <= fecha_actualizacion_to)
        if id_user:
            q_sol = q_sol.where(models.Solicitud.id_user == id_user)
        if id_empresa:
            q_sol = q_sol.where(models.Solicitud.id_empresa == id_empresa)
        if tipo:
            q_sol = q_sol.where(models.Solicitud.tipo == tipo)

        solicitudes = (await db.execute(q_sol)).all()

        resultado = []

        # 3) Procesar Rendiciones
        for rend, full_name in rendiciones:
            docs = (await db.execute(
                select(models.Documento).where(
                    models.Documento.id_numero_rendicion == rend.id,
                    models.Documento.tipo_solicitud == rend.tipo,
                    models.Documento.estado != "RECHAZADO"
                )
            )).scalars().all()
            if docs:
                resultado.append({
                    "rendicion": {
                        "id": rend.id,
                        "id_user": rend.id_user,
                        "nombre": rend.nombre,
                        "tipo": rend.tipo,
                        "estado": rend.estado,
                        "fecha_registro": rend.fecha_registro,
                        "fecha_actualizacion": rend.fecha_actualizacion,
                        "nombre_usuario": full_name,
                        "id_empresa": rend.id_empresa,
                    },
                    "documentos": [
                        {
                            key: getattr(doc, key)
                            for key in models.Documento.__table__.columns.keys()
                        }
                        for doc in docs
                    ]
                })

        # 4) Procesar Solicitudes
        for sol, full_name in solicitudes:
            docs = (await db.execute(
                select(models.Documento).where(
                    models.Documento.id_numero_rendicion == sol.id,
                    models.Documento.tipo_solicitud == sol.tipo,
                    models.Documento.estado != "RECHAZADO"
                )
            )).scalars().all()
            if docs:
                resultado.append({
                    "rendicion": {
                        "id": sol.id,
                        "id_user": sol.id_user,
                        "nombre": sol.nombre,
                        "tipo": sol.tipo,
                        "estado": sol.estado,
                        "fecha_registro": sol.fecha_registro,
                        "fecha_actualizacion": sol.fecha_actualizacion,
                        "nombre_usuario": full_name,
                        "id_empresa": sol.id_empresa,
                    },
                    "documentos": [
                        {
                            key: getattr(doc, key)
                            for key in models.Documento.__table__.columns.keys()
                        }
                        for doc in docs
                    ]
                })

        return resultado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener datos: {e}")
#################################################
    

@router.get("/rendiciones/", response_model=list[schemas.Rendicion])
async def read_rendiciones(db: AsyncSession = Depends(get_db)):
    return await crud.get_rendiciones(db)


@router.post("/rendicion/", response_model=schemas.RendicionCreateResponse)
async def create_rendicion(rendicion_request: schemas.RendicionCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        id_user = rendicion_request.id_user
        id_empresa = rendicion_request.id_empresa
        new_rendicion = await create_rendicion_with_increment(db, id_user, id_empresa)
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
    id_aprobador: Optional[int] = None
    id_contador: Optional[int] = None
    nom_aprobador: Optional[str] = None
    nom_contador: Optional[str] = None
    
# @router.put("/rendicion/{rendicion_id}", response_model=dict)
# async def update_rendicion(
#     rendicion_id: int,
#     rendicion_data: RendicionUpdate,  # Cambia esto de schemas.RendicionUpdate a RendicionUpdate
#     db: AsyncSession = Depends(get_db)
# ):
#     # Buscar la rendición por ID
#     result = await db.execute(select(models.Rendicion).where(models.Rendicion.id == rendicion_id))
#     db_rendicion = result.scalars().first()

#     if not db_rendicion:
#         raise HTTPException(status_code=404, detail="Rendición no encontrada")

#     # Actualizar solo los campos proporcionados
#     update_data = rendicion_data.dict(exclude_unset=True)
#     for key, value in update_data.items():
#         setattr(db_rendicion, key, value)

#     # Guardar cambios
#     await db.commit()
#     await db.refresh(db_rendicion)

#     return {"detail": "Rendición actualizada exitosamente"}

@router.put("/rendicion/{rendicion_id}", response_model=dict)
async def update_rendicion(
    rendicion_id: int,
    rendicion_data: RendicionUpdate,
    db: AsyncSession = Depends(get_db)
):
    # Log the incoming request data
    logger.info(f"Received update request for rendicion_id: {rendicion_id}")
    logger.info(f"Request body: {rendicion_data.dict()}")
    
    # Buscar la rendición por ID
    result = await db.execute(
        select(models.Rendicion)
        .where(models.Rendicion.id == rendicion_id)
        .options(
            joinedload(models.Rendicion.aprobador),
            joinedload(models.Rendicion.contador)
        )
    )
    db_rendicion = result.scalars().first()

    if not db_rendicion:
        logger.error(f"Rendición no encontrada con ID: {rendicion_id}")
        raise HTTPException(status_code=404, detail="Rendición no encontrada")

    # Log current state before update
    logger.info(f"Current rendicion state before update:")
    logger.info(f"Nombre: {db_rendicion.nombre}")
    logger.info(f"Tipo: {db_rendicion.tipo}")
    logger.info(f"Estado: {db_rendicion.estado}")
    logger.info(f"ID Aprobador: {db_rendicion.id_aprobador}")
    logger.info(f"Nom Aprobador: {db_rendicion.nom_aprobador}")
    logger.info(f"ID Contador: {db_rendicion.id_contador}")
    logger.info(f"Nom Contador: {db_rendicion.nom_contador}")

    # Actualizar solo los campos proporcionados
    update_data = rendicion_data.dict(exclude_unset=True)
    logger.info(f"Update data received: {update_data}")
    
    # Verificar si nom_aprobador viene directamente en el request
    if 'nom_aprobador' in update_data:
        logger.info(f"Direct nom_aprobador update received: {update_data['nom_aprobador']}")
        # Si viene directamente, lo usamos sin buscar por ID
        pass
    
    # Actualizar nombres si se proporcionan IDs
    if 'id_aprobador' in update_data:
        logger.info(f"id_aprobador received: {update_data['id_aprobador']}")
        if update_data['id_aprobador'] is not None:
            user_result = await db.execute(select(models.User).where(models.User.id == update_data['id_aprobador']))
            aprobador = user_result.scalars().first()
            if aprobador:
                update_data['nom_aprobador'] = aprobador.full_name
                logger.info(f"Found aprobador user: {aprobador.full_name}")
            else:
                logger.warning(f"No user found for id_aprobador: {update_data['id_aprobador']}")
        else:
            update_data['nom_aprobador'] = None
            logger.info("id_aprobador is None, setting nom_aprobador to None")
    
    if 'id_contador' in update_data:
        logger.info(f"id_contador received: {update_data['id_contador']}")
        if update_data['id_contador'] is not None:
            user_result = await db.execute(select(models.User).where(models.User.id == update_data['id_contador']))
            contador = user_result.scalars().first()
            if contador:
                update_data['nom_contador'] = contador.full_name
                logger.info(f"Found contador user: {contador.full_name}")
            else:
                logger.warning(f"No user found for id_contador: {update_data['id_contador']}")
        else:
            update_data['nom_contador'] = None
            logger.info("id_contador is None, setting nom_contador to None")

    # Log what will be updated
    logger.info(f"Fields to be updated: {list(update_data.keys())}")
    
    # Aplicar las actualizaciones
    for key, value in update_data.items():
        logger.info(f"Updating {key} from {getattr(db_rendicion, key)} to {value}")
        setattr(db_rendicion, key, value)

    # Guardar cambios
    await db.commit()
    await db.refresh(db_rendicion)
    
    # Log state after update
    logger.info(f"Rendicion state after update:")
    logger.info(f"Nombre: {db_rendicion.nombre}")
    logger.info(f"Tipo: {db_rendicion.tipo}")
    logger.info(f"Estado: {db_rendicion.estado}")
    logger.info(f"ID Aprobador: {db_rendicion.id_aprobador}")
    logger.info(f"Nom Aprobador: {db_rendicion.nom_aprobador}")
    logger.info(f"ID Contador: {db_rendicion.id_contador}")
    logger.info(f"Nom Contador: {db_rendicion.nom_contador}")

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



