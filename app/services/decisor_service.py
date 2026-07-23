import json
import os
import unicodedata

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_CHAT_URL = os.getenv(
    "OLLAMA_CHAT_URL",
    "http://localhost:11434/api/chat",
)
OLLAMA_MODELO = os.getenv("OLLAMA_MODELO", "llama3.2:3b")

HERRAMIENTAS_VALIDAS = {"documentos", "mongodb", "api_externa"}


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def _pregunta_sobre_memoria(pregunta: str) -> bool:
    pregunta_normalizada = _normalizar_texto(pregunta)
    expresiones_memoria = (
        "pregunta anterior",
        "pregunte antes",
        "te pregunte",
        "que hablamos",
        "de que hablamos",
        "que conversamos",
        "conversacion anterior",
        "historial",
        "que te dije",
        "te habia dicho",
        "recordas",
        "recuerdas",
        "que recuerdas",
        "que sabes de mi",
    )
    return any(
        expresion in pregunta_normalizada
        for expresion in expresiones_memoria
    )


def _pregunta_sobre_pais(pregunta: str) -> bool:
    pregunta_normalizada = _normalizar_texto(pregunta)
    datos_pais = (
        "capital",
        "moneda",
        "poblacion",
        "idioma",
        "region",
        "subregion",
        "pais",
    )
    return any(dato in pregunta_normalizada for dato in datos_pais)


def _consultar_decision_ia(pregunta: str) -> dict:
    mensaje_sistema = (
        "Seleccioná todas las herramientas necesarias para responder. "
        "Herramientas disponibles: documentos, mongodb y api_externa. "
        "Usá documentos para consultar PDFs; mongodb para recordar "
        "conversaciones; api_externa para datos de países como capital, "
        "moneda, población, idioma o región. Si la pregunta puede "
        "responderse solo con conocimiento general, devolvé una lista vacía. "
        "Respondé únicamente JSON con este formato: "
        '{"herramientas":["documentos","mongodb","api_externa"],'
        '"motivo":"explicación breve"}'
    )

    try:
        respuesta = httpx.post(
            OLLAMA_CHAT_URL,
            json={
                "model": OLLAMA_MODELO,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": mensaje_sistema},
                    {"role": "user", "content": pregunta},
                ],
            },
            timeout=120,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json()["message"]["content"]
        decision = json.loads(contenido)
    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {"herramientas": [], "motivo": ""}

    herramientas = decision.get("herramientas", [])
    if not isinstance(herramientas, list):
        herramientas = []

    return {
        "herramientas": [
            herramienta
            for herramienta in herramientas
            if herramienta in HERRAMIENTAS_VALIDAS
        ],
        "motivo": str(decision.get("motivo", "")).strip(),
    }


def decidir_herramientas(
    pregunta: str,
    documento_id: str | None = None,
) -> dict:
    herramientas = []
    motivos = []

    if documento_id:
        herramientas.append("documentos")
        motivos.append("Se indicó un documento para consultar.")

    if _pregunta_sobre_memoria(pregunta):
        herramientas.append("mongodb")
        motivos.append("La pregunta requiere recordar la conversación.")

    if _pregunta_sobre_pais(pregunta):
        herramientas.append("api_externa")
        motivos.append("La pregunta solicita datos de un país.")

    decision_ia = _consultar_decision_ia(pregunta)
    for herramienta in decision_ia["herramientas"]:
        if herramienta not in herramientas:
            herramientas.append(herramienta)

    if decision_ia["motivo"]:
        motivos.append(decision_ia["motivo"])

    if not motivos:
        motivos.append(
            "La pregunta puede responderse directamente con el modelo."
        )

    return {
        "herramientas": herramientas,
        "motivo": " ".join(motivos),
    }
