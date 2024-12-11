from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.models import Solicitud
from app.schemas import SolicitudResponse, SolicitudUpdate
from app.database import get_db
from sqlalchemy.orm import joinedload

router = APIRouter()


@router.get("/solicitud/nombres", response_model=List[SolicitudResponse])
async def get_unique_solicitud_names(
    user_id: int,
    estado: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Solicitud).where(
            Solicitud.idUser == user_id,
            Solicitud.estado == estado
        )

        if estado:
            query = query.where(Solicitud.estado == estado)

        result = await db.execute(query)
        solicitudes = result.scalars().all()

        if not solicitudes:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron solicitudes para este usuario con los filtros especificadosee"
            )

        return solicitudes

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3

@router.put("/solicitud/{solicitud_id}")
async def update_solicitud(solicitud_id: int, solicitud_data: SolicitudUpdate, db: AsyncSession = Depends(get_db)):
    """
    Actualiza una solicitud con los datos proporcionados.
    """
    try:
        # Buscar la solicitud por ID
        query = select(Solicitud).where(
            Solicitud.id == solicitud_id).options(joinedload(Solicitud.user))
        result = await db.execute(query)
        solicitud = result.scalars().first()

        # Verificar si existe
        if not solicitud:
            raise HTTPException(
                status_code=404, detail="Solicitud no encontrada")

        # Actualizar solo los campos proporcionados
        for key, value in solicitud_data.dict(exclude_unset=True).items():
            setattr(solicitud, key, value)

        # Guardar cambios en la base de datos
        await db.commit()
        await db.refresh(solicitud)

        return {"message": "Solicitud actualizada exitosamente", "solicitud": solicitud}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al actualizar la solicitud: {str(e)}")
