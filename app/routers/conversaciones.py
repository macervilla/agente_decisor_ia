# Router para manejar las conversaciones en la base de datos

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.database import base_datos
from app.schemas.conversacion import ConversacionCrear, ConsultaIACrear
from app.services.ia_service import ErrorIA, generar_respuesta


router = APIRouter(
    prefix="/conversaciones",
    tags=["Conversaciones"],
)

coleccion_conversaciones = base_datos["conversaciones"]


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_conversacion(datos: ConversacionCrear):
    documento = {
        "usuario": datos.usuario,
        "pregunta": datos.pregunta,
        "respuesta": datos.respuesta,
        "fecha_creacion": datetime.now(timezone.utc),
    }

    resultado = coleccion_conversaciones.insert_one(documento)

    return {
        "mensaje": "Conversación guardada",
        "id": str(resultado.inserted_id),
    }


@router.get("/")
def listar_conversaciones():
    conversaciones = []

    for documento in coleccion_conversaciones.find():
        conversaciones.append(
            {
                "id": str(documento["_id"]),
                "conversacion_id": documento.get("conversacion_id"),
                "usuario": documento["usuario"],
                "pregunta": documento["pregunta"],
                "respuesta": documento["respuesta"],
                "fecha_creacion": documento["fecha_creacion"],
            }
        )

    return conversaciones


@router.post("/consultar", status_code=status.HTTP_201_CREATED)
def consultar_ia(datos: ConsultaIACrear):
    try:
        conversacion_id = datos.conversacion_id or str(uuid4())

        historial = list(
            coleccion_conversaciones.find(
                {
                    "conversacion_id": conversacion_id,
                    "usuario": datos.usuario,
                },
                {
                    "_id": 0,
                    "pregunta": 1,
                    "respuesta": 1,
                },
            ).sort("fecha_creacion", 1)
        )

        resultado_ia = generar_respuesta(datos.pregunta, historial)

        documento = {
            "conversacion_id": conversacion_id,
            "usuario": datos.usuario,
            "pregunta": datos.pregunta,
            "respuesta": resultado_ia["texto"],
            "modelo": resultado_ia["modelo"],
            "tokens_entrada": resultado_ia["tokens_entrada"],
            "tokens_salida": resultado_ia["tokens_salida"],
            "tokens_total": resultado_ia["tokens_total"],
            "fecha_creacion": datetime.now(timezone.utc),
        }

        resultado_mongo = coleccion_conversaciones.insert_one(documento)

        return {
            "id": str(resultado_mongo.inserted_id),
            "conversacion_id": conversacion_id,
            **resultado_ia,
        }

    except ErrorIA as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al consultar el modelo de IA: {error}",
        ) from error
