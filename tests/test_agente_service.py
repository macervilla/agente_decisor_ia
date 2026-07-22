import pytest

from app.services import agente_service


class ColeccionSimulada:
    def __init__(self, historial=None):
        self.historial = historial or []
        self.guardados = []

    def find(self, filtro, proyeccion):
        return CursorSimulado(self.historial)

    def insert_one(self, documento):
        self.guardados.append(documento)
        return None


class CursorSimulado(list):
    def sort(self, *args):
        return self

    def limit(self, cantidad):
        return CursorSimulado(self[:cantidad])


@pytest.fixture
def coleccion(monkeypatch):
    coleccion = ColeccionSimulada()
    monkeypatch.setattr(
        agente_service,
        "coleccion_conversaciones",
        coleccion,
    )
    return coleccion


def test_consulta_documento_usa_chromadb(monkeypatch, coleccion):
    def rag_simulado(**datos):
        assert datos["documento_id"] == "doc-123"
        return {
            "respuesta": "El saldo es $15.901.318,35.",
            "fragmentos_utilizados": 4,
        }

    monkeypatch.setattr(agente_service, "preguntar_documentos", rag_simulado)

    resultado = agente_service.consultar_agente(
        usuario="alejandro",
        pregunta="¿Cuál es el saldo de la cuenta?",
        documento_id="doc-123",
    )

    assert resultado["herramienta_utilizada"] == "documentos"
    assert resultado["fragmentos_utilizados"] == 4
    assert resultado["respuesta"] == "El saldo es $15.901.318,35."


def test_consulta_historial_usa_mongodb(monkeypatch):
    historial = [
        {
            "pregunta": "¿Cuál es el saldo?",
            "respuesta": "El saldo es positivo.",
        }
    ]
    coleccion = ColeccionSimulada(historial)
    monkeypatch.setattr(
        agente_service,
        "coleccion_conversaciones",
        coleccion,
    )

    resultado = agente_service.consultar_agente(
        usuario="alejandro",
        pregunta="¿Cuál fue mi pregunta anterior?",
        conversacion_id="conv-123",
    )

    assert resultado["herramienta_utilizada"] == "mongodb"
    assert resultado["respuesta"] == 'Tu pregunta anterior fue: "¿Cuál es el saldo?".'
    assert resultado["fragmentos_utilizados"] == 0


def test_consulta_pais_usa_api_externa(monkeypatch, coleccion):
    datos_pais = {
        "pais": "Brazil",
        "capital": "Brasilia",
        "monedas": ["Brazilian real (R$)"],
        "idiomas": ["Portuguese"],
        "poblacion": 212559409,
        "region": "Americas",
        "subregion": "South America",
        "fuente": "countries.dev",
    }
    monkeypatch.setattr(
        agente_service,
        "consultar_pais",
        lambda pregunta: datos_pais,
    )
    monkeypatch.setattr(
        agente_service,
        "formatear_respuesta_pais",
        lambda datos: "Brazil: capital Brasilia; moneda Brazilian real (R$).",
    )

    resultado = agente_service.consultar_agente(
        usuario="alejandro",
        pregunta="¿Cuál es la capital y la moneda de Brasil?",
    )

    assert resultado["herramienta_utilizada"] == "api_externa"
    assert resultado["fuente"] == "countries.dev"
    assert resultado["fragmentos_utilizados"] == 0


def test_consulta_general_simula_ollama(monkeypatch, coleccion):
    def ollama_simulado(pregunta, historial):
        assert historial == []
        return {
            "texto": "Una base vectorial almacena embeddings.",
            "modelo": "modelo-simulado",
        }

    monkeypatch.setattr(agente_service, "generar_respuesta", ollama_simulado)
    monkeypatch.setattr(
        agente_service,
        "_elegir_herramienta",
        lambda pregunta, documento_id: "directa",
    )

    resultado = agente_service.consultar_agente(
        usuario="alejandro",
        pregunta="¿Qué es una base de datos vectorial?",
    )

    assert resultado["herramienta_utilizada"] == "directa"
    assert resultado["respuesta"] == "Una base vectorial almacena embeddings."
    assert resultado["fragmentos_utilizados"] == 0


@pytest.mark.parametrize(
    "usuario,pregunta,mensaje",
    [
        ("   ", "Una pregunta", "El usuario no puede estar vacío"),
        ("alejandro", "   ", "La pregunta no puede estar vacía"),
    ],
)
def test_valida_datos_obligatorios(usuario, pregunta, mensaje, coleccion):
    with pytest.raises(agente_service.ErrorAgente, match=mensaje):
        agente_service.consultar_agente(usuario=usuario, pregunta=pregunta)
