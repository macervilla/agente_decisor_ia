from unittest.mock import MagicMock

import pytest

from app.services import ejecutor_service


def test_ejecuta_documentos_y_api_externa(monkeypatch):
    monkeypatch.setattr(
        ejecutor_service,
        "buscar_fragmentos",
        lambda pregunta, documento_id: ["fragmento uno", "fragmento dos"],
    )
    monkeypatch.setattr(
        ejecutor_service,
        "consultar_pais",
        lambda pregunta: {
            "pais": "Argentina",
            "capital": "Buenos Aires",
            "monedas": ["Peso argentino ($)"],
            "idiomas": ["Español"],
            "poblacion": 46000000,
            "region": "América",
            "subregion": "América del Sur",
            "fuente": "countries.dev",
        },
    )

    resultado = ejecutor_service.ejecutar_herramientas(
        herramientas=["documentos", "api_externa"],
        usuario="alejandro",
        pregunta="Según el documento, ¿cuál es la capital de Argentina?",
        conversacion_id="conv-1",
        documento_id="doc-1",
    )

    assert [item["herramienta"] for item in resultado["contextos"]] == [
        "documentos",
        "api_externa",
    ]
    assert resultado["fragmentos_utilizados"] == 2
    assert resultado["fuentes"] == ["countries.dev"]


def test_ejecuta_mongodb_y_respeta_orden_cronologico(monkeypatch):
    cursor = MagicMock()
    cursor.sort.return_value.limit.return_value = [
        {"pregunta": "Segunda", "respuesta": "Respuesta 2"},
        {"pregunta": "Primera", "respuesta": "Respuesta 1"},
    ]
    coleccion = MagicMock()
    coleccion.find.return_value = cursor
    monkeypatch.setattr(
        ejecutor_service,
        "coleccion_conversaciones",
        coleccion,
    )

    resultado = ejecutor_service.ejecutar_herramientas(
        herramientas=["mongodb"],
        usuario="alejandro",
        pregunta="¿Qué hablamos?",
        conversacion_id="conv-1",
    )

    assert resultado["historial"][0]["pregunta"] == "Primera"
    assert resultado["historial"][1]["pregunta"] == "Segunda"


def test_sin_herramientas_devuelve_resultado_vacio():
    resultado = ejecutor_service.ejecutar_herramientas(
        herramientas=[],
        usuario="alejandro",
        pregunta="¿Qué es FastAPI?",
        conversacion_id="conv-1",
    )

    assert resultado == {
        "contextos": [],
        "historial": [],
        "fragmentos_utilizados": 0,
        "fuentes": [],
    }


def test_rechaza_herramienta_desconocida():
    with pytest.raises(ejecutor_service.ErrorEjecutor):
        ejecutor_service.ejecutar_herramientas(
            herramientas=["correo"],
            usuario="alejandro",
            pregunta="Revisá mi correo",
            conversacion_id="conv-1",
        )


def test_construye_contexto_combinado():
    contexto = ejecutor_service.construir_contexto(
        [
            {
                "herramienta": "documentos",
                "contenido": ["fragmento A", "fragmento B"],
            },
            {
                "herramienta": "api_externa",
                "contenido": "Argentina: capital Buenos Aires.",
            },
        ]
    )

    assert "Información obtenida de documentos" in contexto
    assert "fragmento A" in contexto
    assert "Información obtenida de api_externa" in contexto
    assert "capital Buenos Aires" in contexto
