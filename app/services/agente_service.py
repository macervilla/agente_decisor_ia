import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv

from app.database import base_datos
from app.services.api_externa_service import ErrorAPIExterna
from app.services.decisor_service import decidir_herramientas
from app.services.ejecutor_service import (
    ErrorEjecutor,
    construir_contexto,
    ejecutar_herramientas,
)
from app.services.ia_service import ErrorIA, generar_respuesta
from app.services.rag_service import ErrorRAG

load_dotenv()

OLLAMA_MODELO = os.getenv("OLLAMA_MODELO", "llama3.2:3b")

coleccion_conversaciones = base_datos["conversaciones"]


class ErrorAgente(Exception):
    pass


def _guardar_intercambio(
    usuario: str,
    conversacion_id: str,
    pregunta: str,
    respuesta: str,
    herramientas: list[str],
) -> None:
    coleccion_conversaciones.insert_one(
        {
            "usuario": usuario,
            "conversacion_id": conversacion_id,
            "tipo": "agente",
            "herramienta": (
                " + ".join(herramientas) if herramientas else "directa"
            ),
            "herramientas": herramientas,
            "pregunta": pregunta,
            "respuesta": respuesta,
            "modelo": OLLAMA_MODELO,
            "fecha": datetime.now(timezone.utc),
        }
    )


def _preparar_pregunta(pregunta: str, contexto: str) -> str:
    if not contexto:
        return pregunta

    return (
        "Respondé la pregunta usando la información obtenida por las "
        "herramientas. Si las fuentes no alcanzan, indicá qué información "
        "falta. No inventes datos.\n\n"
        f"{contexto}\n\n"
        f"Pregunta original: {pregunta}"
    )


def consultar_agente(
    usuario: str,
    pregunta: str,
    documento_id: str | None = None,
    conversacion_id: str | None = None,
) -> dict:
    usuario = usuario.strip()
    pregunta = pregunta.strip()
    if not usuario:
        raise ErrorAgente("El usuario no puede estar vacío")
    if not pregunta:
        raise ErrorAgente("La pregunta no puede estar vacía")

    conversacion_id = conversacion_id or str(uuid4())
    decision = decidir_herramientas(pregunta, documento_id)
    herramientas = decision["herramientas"]

    try:
        ejecucion = ejecutar_herramientas(
            herramientas=herramientas,
            usuario=usuario,
            pregunta=pregunta,
            conversacion_id=conversacion_id,
            documento_id=documento_id,
        )
        contexto = construir_contexto(ejecucion["contextos"])
        pregunta_modelo = _preparar_pregunta(pregunta, contexto)
        resultado_ia = generar_respuesta(
            pregunta_modelo,
            ejecucion["historial"],
        )
        respuesta = resultado_ia["texto"].strip()
    except (
        ErrorIA,
        ErrorRAG,
        ErrorAPIExterna,
        ErrorEjecutor,
    ) as error:
        raise ErrorAgente(str(error)) from error

    _guardar_intercambio(
        usuario,
        conversacion_id,
        pregunta,
        respuesta,
        herramientas,
    )

    herramienta_utilizada = (
        " + ".join(herramientas) if herramientas else "directa"
    )
    fuentes = ejecucion["fuentes"]

    return {
        "usuario": usuario,
        "pregunta": pregunta,
        "respuesta": respuesta,
        "herramienta_utilizada": herramienta_utilizada,
        "herramientas_seleccionadas": herramientas,
        "motivo_decision": decision["motivo"],
        "conversacion_id": conversacion_id,
        "documento_id": documento_id,
        "fragmentos_utilizados": ejecucion["fragmentos_utilizados"],
        "modelo": resultado_ia.get("modelo", OLLAMA_MODELO),
        "fuente": fuentes[0] if len(fuentes) == 1 else None,
        "fuentes": fuentes,
    }
