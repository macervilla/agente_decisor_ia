from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.agente_service import ErrorAgente, consultar_agente

router = APIRouter(prefix="/agente", tags=["Agente"])


class ConsultaAgente(BaseModel):
    usuario: str = Field(min_length=1)
    pregunta: str = Field(min_length=1)
    documento_id: str | None = None
    conversacion_id: str | None = None


@router.post("/consultar", status_code=status.HTTP_200_OK)
def consultar(datos: ConsultaAgente):
    try:
        return consultar_agente(
            usuario=datos.usuario,
            pregunta=datos.pregunta,
            documento_id=datos.documento_id,
            conversacion_id=datos.conversacion_id,
        )
    except ErrorAgente as error:
        raise HTTPException(status_code=502, detail=str(error)) from error