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
    Procesa los datos recibidos de un QR replicando exactamente la lógica de /decode-qr/
    """
    try:
        raw_qr_data = data.data
        print("\nDatos crudos del QR:", raw_qr_data)
        
        qr_data = [data.strip() for data in raw_qr_data.split("|")]
        result = {}
        monetary_values = []  # Lista para almacenar todos los valores monetarios
        has_serie = False  # Bandera para indicar si ya se detectó la serie
        
        # El primer elemento es siempre el RUC
        if len(qr_data) > 0 and re.match(r'^\d{11}$', qr_data[0]):
            result["ruc"] = qr_data[0]
            print(f"RUC detectado (primer elemento): {qr_data[0]}")
        
        for i, data in enumerate(qr_data[1:]):  # Procesamos desde el segundo elemento
            if re.match(r'^\d{8}$', data) and not has_serie and 'numero' not in result:
                # Si es un número de 8 dígitos y aún no se ha detectado serie ni número,
                # podría ser el número de documento (no necesariamente DNI)
                result["numero"] = data.zfill(8)
                print(f"Número detectado: {data.zfill(8)}")
            elif re.match(r'^\d{8}$', data) and 'numero' in result:
                # Si ya tenemos un número y aparece otro de 8 dígitos, es el DNI
                result["dni"] = data
                print(f"DNI detectado: {data}")
            elif re.match(r'^\d{2}$', data):  # Tipo de Documento
                tipo_doc_map = {
                    "01": "Factura", "02": "Recibo por Honorarios", "03": "Boleta de Venta",
                    "05": "Boleto Aéreo", "07": "Nota de Crédito", "08": "Nota de Débito",
                    "12": "Ticket", "14": "Recibo Servicio Público"
                }
                result["tipo"] = tipo_doc_map.get(data, "Desconocido")
                print(f"Tipo de documento detectado: {result['tipo']} ({data})")
            elif re.match(r'^[A-Za-z0-9]{4}-\d{7,8}$', data):  # Serie con guión
                serie, numero = data.split('-')
                result["serie"] = serie
                result["numero"] = numero.zfill(8)
                has_serie = True
                print(f"Serie y número detectados: {serie}-{numero.zfill(8)}")
            elif re.match(r'^[A-Za-z]{1,3}\d{1,3}$', data):  # Serie sin guión (formato B205, B003, etc.)
                result["serie"] = data
                has_serie = True
                print(f"Serie detectada: {data}")
            elif re.match(r'^\d+$', data) and 4 <= len(data) <= 8 and 'numero' not in result:
                # Número sin guión (solo si no hemos detectado número antes)
                # Solo si tiene entre 4 y 8 dígitos
                result["numero"] = data.zfill(8)
                print(f"Número detectado: {data.zfill(8)}")
            elif re.match(r'^\d+\.\d{1,2}$', data):  # Valor monetario (1 o 2 decimales)
                monetary_values.append(data)
                print(f"Valor monetario detectado: {data}")
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', data) or re.match(r'^\d{2}/\d{2}/\d{4}$', data):  # Fecha
                result["fecha"] = data
                print(f"Fecha detectada: {data}")
        
        # Asignación inteligente de valores monetarios
        if monetary_values:
            monetary_values_sorted = sorted(monetary_values, key=lambda x: float(x), reverse=True)
            result["total"] = monetary_values_sorted[0]
            
            if len(monetary_values_sorted) > 1:
                result["igv"] = monetary_values_sorted[1]
            
            if len(monetary_values_sorted) > 2:
                result["sub_total"] = monetary_values_sorted[2]
        
        print("\nResultado final procesado:", result)
        return result
    except Exception as e:
        print(f"\nError al procesar QR: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process QR data: {str(e)}")