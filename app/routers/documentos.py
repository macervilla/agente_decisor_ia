from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.services.rag_service import ErrorRAG, guardar_pdf, preguntar_documentos

router = APIRouter(prefix="/documentos", tags=["Documentos RAG"])


class PreguntaDocumento(BaseModel):
    usuario: str = Field(min_length=1)
    pregunta: str = Field(min_length=1)
    documento_id: str | None = None
    conversacion_id: str | None = None


@router.post("/cargar", status_code=status.HTTP_201_CREATED)
async def cargar_documento(archivo: UploadFile = File(...)):
    if archivo.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF",
        )

    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo estÃ¡ vacÃ­o",
        )

    try:
        return guardar_pdf(archivo.filename or "documento.pdf", contenido)
    except ErrorRAG as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error


@router.post("/preguntar")
def preguntar_documento(datos: PreguntaDocumento):
    try:
        return preguntar_documentos(
            usuario=datos.usuario,
            pregunta=datos.pregunta,
            documento_id=datos.documento_id,
            conversacion_id=datos.conversacion_id,
        )
    except ErrorRAG as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error