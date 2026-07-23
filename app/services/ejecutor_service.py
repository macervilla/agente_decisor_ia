from app.database import base_datos
from app.services.api_externa_service import (
    consultar_pais,
    formatear_respuesta_pais,
)
from app.services.rag_service import buscar_fragmentos


coleccion_conversaciones = base_datos["conversaciones"]


class ErrorEjecutor(Exception):
    pass


def _consultar_mongodb(
    usuario: str,
    conversacion_id: str,
) -> list[dict]:
    historial = list(
        coleccion_conversaciones.find(
            {
                "usuario": usuario,
                "conversacion_id": conversacion_id,
            },
            {"_id": 0, "pregunta": 1, "respuesta": 1},
        ).sort("fecha", -1).limit(10)
    )
    historial.reverse()
    return historial


def ejecutar_herramientas(
    herramientas: list[str],
    usuario: str,
    pregunta: str,
    conversacion_id: str,
    documento_id: str | None = None,
) -> dict:
    contextos = []
    historial = []
    fragmentos_utilizados = 0
    fuentes = []

    for herramienta in herramientas:
        if herramienta == "mongodb":
            historial = _consultar_mongodb(usuario, conversacion_id)
            contextos.append(
                {
                    "herramienta": "mongodb",
                    "contenido": historial,
                }
            )

        elif herramienta == "documentos":
            fragmentos = buscar_fragmentos(pregunta, documento_id)
            fragmentos_utilizados += len(fragmentos)
            contextos.append(
                {
                    "herramienta": "documentos",
                    "contenido": fragmentos,
                }
            )

        elif herramienta == "api_externa":
            datos_pais = consultar_pais(pregunta)
            fuentes.append(datos_pais["fuente"])
            contextos.append(
                {
                    "herramienta": "api_externa",
                    "contenido": formatear_respuesta_pais(datos_pais),
                }
            )

        else:
            raise ErrorEjecutor(
                f'La herramienta "{herramienta}" no está disponible'
            )

    return {
        "contextos": contextos,
        "historial": historial,
        "fragmentos_utilizados": fragmentos_utilizados,
        "fuentes": fuentes,
    }


def construir_contexto(contextos: list[dict]) -> str:
    secciones = []

    for contexto in contextos:
        herramienta = contexto["herramienta"]
        contenido = contexto["contenido"]

        if herramienta == "mongodb":
            lineas = []
            for intercambio in contenido:
                lineas.append(f'Usuario: {intercambio.get("pregunta", "")}')
                lineas.append(
                    f'Asistente: {intercambio.get("respuesta", "")}'
                )
            texto = "\n".join(lineas)
        elif herramienta == "documentos":
            texto = "\n\n---\n\n".join(contenido)
        else:
            texto = str(contenido)

        if texto.strip():
            secciones.append(
                f"Información obtenida de {herramienta}:\n{texto}"
            )

    return "\n\n".join(secciones)
