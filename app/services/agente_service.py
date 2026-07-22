import json
import os
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from app.database import base_datos
from app.services.api_externa_service import (
    ErrorAPIExterna,
    consultar_pais,
    formatear_respuesta_pais,
)
from app.services.ia_service import ErrorIA, generar_respuesta
from app.services.rag_service import ErrorRAG, preguntar_documentos

load_dotenv()

OLLAMA_CHAT_URL = os.getenv(
    "OLLAMA_CHAT_URL",
    "http://localhost:11434/api/chat",
)
OLLAMA_MODELO = os.getenv("OLLAMA_MODELO", "llama3.2:3b")

coleccion_conversaciones = base_datos["conversaciones"]


class ErrorAgente(Exception):
    pass


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caracter for caracter in texto if unicodedata.category(caracter) != "Mn"
    )


def _pregunta_sobre_memoria(pregunta: str) -> bool:
    pregunta_normalizada = _normalizar_texto(pregunta)
    expresiones_memoria = (
        "pregunta anterior", "pregunte antes", "te pregunte", "que hablamos",
        "de que hablamos", "que conversamos", "conversacion anterior",
        "historial", "que te dije", "te habia dicho", "recordas", "recuerdas",
        "que recuerdas", "que sabes de mi",
    )
    return any(expresion in pregunta_normalizada for expresion in expresiones_memoria)


def _pregunta_sobre_pais(pregunta: str) -> bool:
    pregunta_normalizada = _normalizar_texto(pregunta)
    datos_pais = ("capital", "moneda", "poblacion", "idioma", "region", "subregion", "pais")
    return any(dato in pregunta_normalizada for dato in datos_pais)


def _elegir_herramienta(pregunta: str, documento_id: str | None) -> str:
    if documento_id:
        return "documentos"
    if _pregunta_sobre_memoria(pregunta):
        return "mongodb"
    if _pregunta_sobre_pais(pregunta):
        return "api_externa"

    mensaje_sistema = (
        "Elegí una herramienta para responder la pregunta. "
        "Opciones: documentos, mongodb, api_externa, directa. "
        "Usá documentos para consultar PDFs; mongodb para recordar conversaciones; "
        "api_externa para datos de países como capital, moneda, población, idioma o región; "
        "directa para conocimiento general o saludos. Respondé solo JSON: "
        '{"herramienta":"documentos|mongodb|api_externa|directa"}'
    )
    try:
        respuesta = httpx.post(
            OLLAMA_CHAT_URL,
            json={"model": OLLAMA_MODELO, "stream": False, "format": "json", "messages": [
                {"role": "system", "content": mensaje_sistema},
                {"role": "user", "content": pregunta},
            ]},
            timeout=120,
        )
        respuesta.raise_for_status()
        herramienta = json.loads(respuesta.json()["message"]["content"]).get("herramienta")
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        herramienta = None

    if herramienta in {"documentos", "mongodb", "api_externa", "directa"}:
        return herramienta
    return "directa"


def _obtener_historial(usuario: str, conversacion_id: str | None) -> list[dict]:
    if not conversacion_id:
        return []
    registros = list(
        coleccion_conversaciones.find(
            {"usuario": usuario, "conversacion_id": conversacion_id},
            {"_id": 0, "pregunta": 1, "respuesta": 1},
        ).sort("fecha", -1).limit(10)
    )
    registros.reverse()
    return registros


def _es_pregunta_anterior(pregunta: str) -> bool:
    pregunta_normalizada = _normalizar_texto(pregunta)
    return any(expresion in pregunta_normalizada for expresion in (
        "pregunta anterior", "pregunte antes", "te pregunte", "ultima pregunta"
    ))


def _obtener_pregunta_anterior(historial: list[dict]) -> str | None:
    for intercambio in reversed(historial):
        pregunta = intercambio.get("pregunta", "").strip()
        if pregunta and not _pregunta_sobre_memoria(pregunta):
            return pregunta
    return None


def _guardar_intercambio(usuario: str, conversacion_id: str, pregunta: str, respuesta: str, herramienta: str) -> None:
    coleccion_conversaciones.insert_one({
        "usuario": usuario, "conversacion_id": conversacion_id, "tipo": "agente",
        "herramienta": herramienta, "pregunta": pregunta, "respuesta": respuesta,
        "modelo": OLLAMA_MODELO, "fecha": datetime.now(timezone.utc),
    })


def consultar_agente(usuario: str, pregunta: str, documento_id: str | None = None, conversacion_id: str | None = None) -> dict:
    usuario = usuario.strip()
    pregunta = pregunta.strip()
    if not usuario:
        raise ErrorAgente("El usuario no puede estar vacío")
    if not pregunta:
        raise ErrorAgente("La pregunta no puede estar vacía")

    conversacion_id = conversacion_id or str(uuid4())
    herramienta = _elegir_herramienta(pregunta, documento_id)
    fuente = None

    try:
        if herramienta == "documentos":
            resultado = preguntar_documentos(usuario=usuario, pregunta=pregunta, documento_id=documento_id, conversacion_id=conversacion_id)
            respuesta = resultado["respuesta"]
            fragmentos = resultado["fragmentos_utilizados"]
        elif herramienta == "api_externa":
            datos_pais = consultar_pais(pregunta)
            respuesta = formatear_respuesta_pais(datos_pais)
            fuente = datos_pais["fuente"]
            fragmentos = 0
            _guardar_intercambio(usuario, conversacion_id, pregunta, respuesta, herramienta)
        else:
            historial = _obtener_historial(usuario, conversacion_id) if herramienta == "mongodb" else []
            if herramienta == "mongodb" and _es_pregunta_anterior(pregunta):
                pregunta_anterior = _obtener_pregunta_anterior(historial)
                respuesta = f'Tu pregunta anterior fue: "{pregunta_anterior}".' if pregunta_anterior else "No encontré una pregunta anterior en esta conversación."
            else:
                respuesta = generar_respuesta(pregunta, historial)["texto"].strip()
            fragmentos = 0
            _guardar_intercambio(usuario, conversacion_id, pregunta, respuesta, herramienta)
    except (ErrorIA, ErrorRAG, ErrorAPIExterna) as error:
        raise ErrorAgente(str(error)) from error

    return {
        "usuario": usuario, "pregunta": pregunta, "respuesta": respuesta,
        "herramienta_utilizada": herramienta, "conversacion_id": conversacion_id,
        "documento_id": documento_id, "fragmentos_utilizados": fragmentos,
        "modelo": OLLAMA_MODELO, "fuente": fuente,
    }
