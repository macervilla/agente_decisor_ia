import os

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate",
)
OLLAMA_MODELO = os.getenv(
    "OLLAMA_MODELO",
    "llama3.2:3b",
)


class ErrorIA(Exception):
    pass


def generar_respuesta(pregunta: str, historial: list[dict] | None = None) -> dict:
    instrucciones = (
        "Sos un asistente educativo especializado en programación "
        "e inteligencia artificial. Respondé en español de manera "
        "clara, breve y precisa."
    )

    mensajes_anteriores = []
    for mensaje in historial or []:
        mensajes_anteriores.append(f"Usuario: {mensaje['pregunta']}")
        mensajes_anteriores.append(f"Asistente: {mensaje['respuesta']}")

    historial_texto = "\n".join(mensajes_anteriores)
    prompt = f"{instrucciones}\n\n"

    if historial_texto:
        prompt += f"Historial de la conversación:\n{historial_texto}\n\n"

    prompt += f"Usuario: {pregunta}\nAsistente:"

    try:
        respuesta = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODELO,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorIA(
            f"No se pudo consultar Ollama: {error}"
        ) from error

    datos = respuesta.json()

    tokens_entrada = datos.get("prompt_eval_count", 0)
    tokens_salida = datos.get("eval_count", 0)

    return {
        "texto": datos["response"],
        "modelo": datos["model"],
        "tokens_entrada": tokens_entrada,
        "tokens_salida": tokens_salida,
        "tokens_total": tokens_entrada + tokens_salida,
    }
