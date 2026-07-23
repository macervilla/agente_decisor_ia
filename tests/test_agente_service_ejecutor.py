from app.services import agente_service


def test_agente_combina_herramientas_y_guarda_una_sola_vez(monkeypatch):
    monkeypatch.setattr(
        agente_service,
        "decidir_herramientas",
        lambda pregunta, documento_id: {
            "herramientas": ["documentos", "api_externa"],
            "motivo": "Necesita ambas fuentes.",
        },
    )
    monkeypatch.setattr(
        agente_service,
        "ejecutar_herramientas",
        lambda **kwargs: {
            "contextos": [
                {
                    "herramienta": "documentos",
                    "contenido": ["Contenido del PDF"],
                },
                {
                    "herramienta": "api_externa",
                    "contenido": "Capital: Buenos Aires",
                },
            ],
            "historial": [],
            "fragmentos_utilizados": 1,
            "fuentes": ["countries.dev"],
        },
    )

    pregunta_enviada = {}

    def generar_respuesta_falsa(pregunta, historial):
        pregunta_enviada["texto"] = pregunta
        return {"texto": "Respuesta combinada", "modelo": "modelo-prueba"}

    monkeypatch.setattr(
        agente_service,
        "generar_respuesta",
        generar_respuesta_falsa,
    )

    guardados = []
    monkeypatch.setattr(
        agente_service,
        "_guardar_intercambio",
        lambda *args: guardados.append(args),
    )

    resultado = agente_service.consultar_agente(
        usuario="alejandro",
        pregunta="Compará el PDF con los datos del país",
        documento_id="doc-1",
        conversacion_id="conv-1",
    )

    assert "Contenido del PDF" in pregunta_enviada["texto"]
    assert "Capital: Buenos Aires" in pregunta_enviada["texto"]
    assert resultado["herramienta_utilizada"] == (
        "documentos + api_externa"
    )
    assert resultado["respuesta"] == "Respuesta combinada"
    assert len(guardados) == 1
