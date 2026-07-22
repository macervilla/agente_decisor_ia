import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import chromadb
import fitz
import httpx
from dotenv import load_dotenv

from app.database import base_datos

load_dotenv()

OLLAMA_EMBED_URL = os.getenv(
    "OLLAMA_EMBED_URL",
    "http://localhost:11434/api/embed",
)
OLLAMA_MODELO_EMBEDDING = os.getenv(
    "OLLAMA_MODELO_EMBEDDING",
    "nomic-embed-text",
)
OLLAMA_CHAT_URL = os.getenv(
    "OLLAMA_CHAT_URL",
    "http://localhost:11434/api/chat",
)
OLLAMA_MODELO_CHAT = os.getenv("OLLAMA_MODELO", "llama3.2:3b")
CHROMA_RUTA = os.getenv("CHROMA_RUTA", "./chroma_db")
CHROMA_COLECCION = os.getenv("CHROMA_COLECCION", "documentos")

cliente_chroma = chromadb.PersistentClient(path=CHROMA_RUTA)
coleccion_documentos = cliente_chroma.get_or_create_collection(
    name=CHROMA_COLECCION,
    metadata={"hnsw:space": "cosine"},
)
coleccion_conversaciones = base_datos["conversaciones"]


class ErrorRAG(Exception):
    pass


def extraer_texto_pdf(contenido: bytes) -> str:
    try:
        with fitz.open(stream=contenido, filetype="pdf") as documento:
            texto = "\n".join(pagina.get_text() for pagina in documento)
    except Exception as error:
        raise ErrorRAG("No se pudo leer el archivo PDF") from error

    texto = " ".join(texto.split())
    if not texto:
        raise ErrorRAG("El PDF no contiene texto extraÃ­ble")

    return texto


def dividir_texto(
    texto: str,
    tamanio: int = 1000,
    solapamiento: int = 200,
) -> list[str]:
    fragmentos = []
    inicio = 0

    while inicio < len(texto):
        fin = min(inicio + tamanio, len(texto))
        fragmento = texto[inicio:fin].strip()
        if fragmento:
            fragmentos.append(fragmento)

        if fin == len(texto):
            break
        inicio = fin - solapamiento

    return fragmentos


def generar_embeddings(fragmentos: list[str]) -> list[list[float]]:
    try:
        respuesta = httpx.post(
            OLLAMA_EMBED_URL,
            json={
                "model": OLLAMA_MODELO_EMBEDDING,
                "input": fragmentos,
            },
            timeout=300,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorRAG(
            f"No se pudieron generar los embeddings con Ollama: {error}"
        ) from error

    embeddings = respuesta.json().get("embeddings", [])
    if len(embeddings) != len(fragmentos):
        raise ErrorRAG("Ollama no devolviÃ³ todos los embeddings esperados")

    return embeddings


def guardar_pdf(nombre_archivo: str, contenido: bytes) -> dict:
    texto = extraer_texto_pdf(contenido)
    fragmentos = dividir_texto(texto)
    embeddings = generar_embeddings(fragmentos)
    documento_id = str(uuid4())
    nombre_seguro = Path(nombre_archivo).name

    ids = [f"{documento_id}-{indice}" for indice in range(len(fragmentos))]
    metadatos = [
        {
            "documento_id": documento_id,
            "archivo": nombre_seguro,
            "fragmento": indice,
        }
        for indice in range(len(fragmentos))
    ]

    coleccion_documentos.add(
        ids=ids,
        documents=fragmentos,
        embeddings=embeddings,
        metadatas=metadatos,
    )

    return {
        "documento_id": documento_id,
        "archivo": nombre_seguro,
        "fragmentos_guardados": len(fragmentos),
        "modelo_embedding": OLLAMA_MODELO_EMBEDDING,
    }


def buscar_fragmentos(
    pregunta: str,
    documento_id: str | None = None,
    cantidad: int = 4,
) -> list[str]:
    embedding_pregunta = generar_embeddings([pregunta])[0]
    parametros = {
        "query_embeddings": [embedding_pregunta],
        "n_results": cantidad,
        "include": ["documents", "metadatas", "distances"],
    }

    if documento_id:
        parametros["where"] = {"documento_id": documento_id}

    try:
        resultado = coleccion_documentos.query(**parametros)
    except Exception as error:
        raise ErrorRAG("No se pudo consultar ChromaDB") from error

    documentos = resultado.get("documents") or []
    fragmentos = documentos[0] if documentos else []
    if not fragmentos:
        if documento_id:
            raise ErrorRAG("No se encontraron fragmentos para ese documento_id")
        raise ErrorRAG("No hay documentos cargados para realizar la consulta")

    return fragmentos


def generar_respuesta_rag(
    pregunta: str,
    fragmentos: list[str],
    historial: list[dict] | None = None,
) -> str:
    contexto = "\n\n---\n\n".join(fragmentos)
    mensaje_sistema = (
        "RespondÃ© Ãºnicamente con la informaciÃ³n del contexto proporcionado. "
        "Si la respuesta no estÃ¡ en el contexto, indicÃ¡ que no encontraste "
        "esa informaciÃ³n en los documentos."
    )

    mensajes = [{"role": "system", "content": mensaje_sistema}]
    for intercambio in historial or []:
        mensajes.append({"role": "user", "content": intercambio["pregunta"]})
        mensajes.append(
            {"role": "assistant", "content": intercambio["respuesta"]}
        )

    mensajes.append(
        {
            "role": "user",
            "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}",
        }
    )

    try:
        respuesta = httpx.post(
            OLLAMA_CHAT_URL,
            json={
                "model": OLLAMA_MODELO_CHAT,
                "stream": False,
                "messages": mensajes,
            },
            timeout=300,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorRAG(
            f"No se pudo generar la respuesta con Ollama: {error}"
        ) from error

    texto = respuesta.json().get("message", {}).get("content", "").strip()
    if not texto:
        raise ErrorRAG("Ollama no devolviÃ³ una respuesta")

    return texto


def preguntar_documentos(
    usuario: str,
    pregunta: str,
    documento_id: str | None = None,
    conversacion_id: str | None = None,
) -> dict:
    usuario = usuario.strip()
    pregunta = pregunta.strip()
    if not usuario:
        raise ErrorRAG("El usuario no puede estar vacÃ­o")
    if not pregunta:
        raise ErrorRAG("La pregunta no puede estar vacÃ­a")

    conversacion_id = conversacion_id or str(uuid4())
    filtro_historial = {
        "usuario": usuario,
        "conversacion_id": conversacion_id,
        "tipo": "rag",
    }
    if documento_id:
        filtro_historial["documento_id"] = documento_id

    historial = list(
        coleccion_conversaciones.find(filtro_historial, {"_id": 0}).sort(
            "fecha", 1
        )
    )

    preguntas_anteriores = [item["pregunta"] for item in historial[-3:]]
    pregunta_busqueda = "\n".join([*preguntas_anteriores, pregunta])
    fragmentos = buscar_fragmentos(pregunta_busqueda, documento_id)
    respuesta = generar_respuesta_rag(pregunta, fragmentos, historial)

    coleccion_conversaciones.insert_one(
        {
            "usuario": usuario,
            "conversacion_id": conversacion_id,
            "tipo": "rag",
            "documento_id": documento_id,
            "pregunta": pregunta,
            "respuesta": respuesta,
            "modelo": OLLAMA_MODELO_CHAT,
            "fecha": datetime.now(timezone.utc),
        }
    )

    return {
        "usuario": usuario,
        "pregunta": pregunta,
        "respuesta": respuesta,
        "conversacion_id": conversacion_id,
        "documento_id": documento_id,
        "fragmentos_utilizados": len(fragmentos),
        "modelo": OLLAMA_MODELO_CHAT,
    }