from unittest.mock import Mock

from app.services import decisor_service


def _respuesta_ollama(herramientas: list[str], motivo: str = "") -> Mock:
    respuesta = Mock()
    respuesta.raise_for_status.return_value = None
    respuesta.json.return_value = {
        "message": {
            "content": (
                '{"herramientas":'
                f'{str(herramientas).replace(chr(39), chr(34))},'
                f'"motivo":"{motivo}"'
                "}"
            )
        }
    }
    return respuesta


def test_decide_sin_herramientas_para_conocimiento_general(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama([]),
    )

    decision = decisor_service.decidir_herramientas(
        "¿Qué es la inyección de dependencias?"
    )

    assert decision["herramientas"] == []


def test_decide_documentos_cuando_recibe_documento_id(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama([]),
    )

    decision = decisor_service.decidir_herramientas(
        "¿Qué establece sobre licencias?",
        documento_id="documento-123",
    )

    assert decision["herramientas"] == ["documentos"]


def test_decide_mongodb_para_recordar_la_conversacion(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama([]),
    )

    decision = decisor_service.decidir_herramientas(
        "¿Qué hablamos sobre Redis?"
    )

    assert decision["herramientas"] == ["mongodb"]


def test_decide_api_externa_para_datos_de_paises(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama([]),
    )

    decision = decisor_service.decidir_herramientas(
        "¿Cuál es la capital y la moneda de Brasil?"
    )

    assert decision["herramientas"] == ["api_externa"]


def test_decide_varias_herramientas_sin_duplicarlas(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama(
            ["documentos", "api_externa"],
            "Se necesita comparar ambas fuentes.",
        ),
    )

    decision = decisor_service.decidir_herramientas(
        "Según el documento, ¿cuál es la población del país?",
        documento_id="documento-123",
    )

    assert decision["herramientas"] == [
        "documentos",
        "api_externa",
    ]


def test_descarta_herramientas_no_permitidas(monkeypatch):
    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        lambda *args, **kwargs: _respuesta_ollama(
            ["internet", "mongodb"]
        ),
    )

    decision = decisor_service.decidir_herramientas(
        "Necesito recordar algo que dije"
    )

    assert decision["herramientas"] == ["mongodb"]


def test_falla_de_ollama_conserva_las_reglas_locales(monkeypatch):
    def simular_error(*args, **kwargs):
        raise decisor_service.httpx.ConnectError(
            "Ollama no disponible"
        )

    monkeypatch.setattr(
        decisor_service.httpx,
        "post",
        simular_error,
    )

    decision = decisor_service.decidir_herramientas(
        "¿Cuál es la población de Argentina?"
    )

    assert decision["herramientas"] == ["api_externa"]
