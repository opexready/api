from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import re

router = APIRouter()

# Definir el esquema para recibir los datos
class QRData(BaseModel):
    data: str

@router.post("/process-qr/", response_model=dict)
async def process_qr(data: QRData):
    """
    Procesa los datos recibidos de un QR y los devuelve en formato estructurado.
    """
    try:
        qr_data = data.data.split("|")  # Divide los datos en base al separador '|'
        result = {}

        for item in qr_data:
            if re.match(r'^\d{8}$', item):  # Dato de 8 dígitos (DNI)
                result["dni"] = item
            elif re.match(r'^\d{11}$', item):  # Dato de 11 dígitos (RUC)
                result["ruc"] = item
            elif re.match(r'^\d{2}$', item):  # Dato de 2 dígitos (Tipo de Documento)
                tipo_doc_map = {
                    "01": "Factura",
                    "02": "Recibo por Honorarios",
                    "03": "Boleta de Venta",
                    "05": "Boleto Aéreo",
                    "07": "Nota de Crédito",
                    "08": "Nota de Débito",
                    "12": "Ticket o cinta emitido por máquina registradora",
                    "14": "Recibo Servicio Público"
                }
                result["tipo"] = tipo_doc_map.get(item, "Desconocido")
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', item):  # Serie con guion
                serie, numero = item.split('-')
                result["serie"] = serie
                result["numero"] = numero.zfill(8)
            elif re.match(r'^[A-Za-z0-9]{2,4}$', item):  # Serie alfanumérica
                result["serie"] = item
            elif re.match(r'^\d+$', item) and 3 < len(item) < 9:  # Número sin guion
                result["numero"] = item.zfill(8)
            elif re.match(r'^\d+\.\d{2}$', item):  # Valor decimal
                if "total" not in result or float(item) > float(result["total"]):
                    if "total" in result:
                        result["igv"] = result["total"]
                    result["total"] = item
                else:
                    result["igv"] = item
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', item) or re.match(r'^\d{2}/\d{2}/\d{4}$', item):  # Fecha
                result["fecha"] = item

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing QR data: {str(e)}")
