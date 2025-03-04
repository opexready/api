from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.schemas import CompanyCreate, Company
from app.models import Company as CompanyModel

router = APIRouter()

# Crear una nueva compañía
@router.post("/companies/", response_model=Company, status_code=201)
async def create_company(
    company: CompanyCreate, db: AsyncSession = Depends(get_db)
):
    """
    Crea una nueva compañía en la base de datos.
    """
    db_company = CompanyModel(**company.dict())
    try:
        db.add(db_company)
        await db.commit()
        await db.refresh(db_company)
        return db_company
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="La compañía ya existe")


# Obtener una compañía por ID
@router.get("/companies/{company_id}", response_model=Company)
async def read_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene una compañía específica por su ID.
    """
    result = await db.execute(select(CompanyModel).where(CompanyModel.id == company_id))
    company = result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Compañía no encontrada")
    return company


# Obtener una compañía por ID
@router.get("/companies/user/{id_user}", response_model=List[Company])
async def read_companies_by_user(id_user: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene una lista de compañías asociadas a un ID de usuario específico.
    """
    result = await db.execute(select(CompanyModel).where(CompanyModel.id_user == id_user))
    companies = result.scalars().all()

    if not companies:
        raise HTTPException(status_code=404, detail="No se encontraron compañías para este usuario")

    return companies


# Listar todas las compañías
@router.get("/companies/", response_model=list[Company])
async def read_companies(db: AsyncSession = Depends(get_db)):
    """
    Obtiene una lista de todas las compañías.
    """
    result = await db.execute(select(CompanyModel))
    companies = result.scalars().all()
    return companies


# Actualizar una compañía
@router.put("/companies/{company_id}", response_model=Company)
async def update_company(
    company_id: int, company: CompanyCreate, db: AsyncSession = Depends(get_db)
):
    """
    Actualiza los detalles de una compañía específica.
    """
    result = await db.execute(select(CompanyModel).where(CompanyModel.id == company_id))
    db_company = result.scalars().first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Compañía no encontrada")

    for key, value in company.dict().items():
        setattr(db_company, key, value)

    try:
        await db.commit()
        await db.refresh(db_company)
        return db_company
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Error al actualizar la compañía")


# Eliminar una compañía
@router.delete("/companies/{company_id}", response_model=dict)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """
    Elimina una compañía específica por su ID.
    """
    result = await db.execute(select(CompanyModel).where(CompanyModel.id == company_id))
    db_company = result.scalars().first()
    if not db_company:
        raise HTTPException(status_code=404, detail="Compañía no encontrada")

    await db.delete(db_company)
    await db.commit()
    return {"detail": "Compañía eliminada exitosamente"}
