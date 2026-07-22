import unicodedata
from urllib.parse import quote

import httpx


COUNTRIES_DEV_URL = "https://countries.dev/name"


class ErrorAPIExterna(Exception):
    pass


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caracter for caracter in texto if unicodedata.category(caracter) != "Mn"
    )


def _extraer_pais(pregunta: str) -> str:
    pregunta_normalizada = _normalizar(pregunta)
    conectores = (" de ", " del ", " en ")

    for conector in conectores:
        if conector in pregunta_normalizada:
            posicion = pregunta_normalizada.rfind(conector)
            pais = pregunta[posicion + len(conector):].strip(" ¿?¡!.,")
            if pais:
                return pais

    palabras = pregunta.strip(" ¿?¡!.,").split()
    if palabras:
        return palabras[-1]

    raise ErrorAPIExterna("No pude identificar el país en la pregunta")


def consultar_pais(pregunta: str) -> dict:
    pais = _extraer_pais(pregunta)
    url = f"{COUNTRIES_DEV_URL}/{quote(pais)}"

    try:
        respuesta = httpx.get(url, timeout=20, follow_redirects=True)
        if respuesta.status_code == 404:
            raise ErrorAPIExterna(f'No encontré información para el país "{pais}"')
        respuesta.raise_for_status()
        datos = respuesta.json()
    except ErrorAPIExterna:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise ErrorAPIExterna("No se pudo consultar la API externa de países") from error

    if not datos:
        raise ErrorAPIExterna(f'No encontré información para el país "{pais}"')

    pais_datos = datos[0]
    nombre = pais_datos.get("name") or pais
    capital = pais_datos.get("capital") or "Sin datos"
    monedas_datos = pais_datos.get("currencies") or []
    idiomas_datos = pais_datos.get("languages") or []

    monedas = [
        f'{moneda.get("name", moneda.get("code", "Sin datos"))} '
        f'({moneda.get("symbol") or moneda.get("code", "Sin datos")})'
        for moneda in monedas_datos
    ]

    return {
        "pais": nombre,
        "capital": capital,
        "monedas": monedas or ["Sin datos"],
        "idiomas": [idioma.get("name", "Sin datos") for idioma in idiomas_datos]
        or ["Sin datos"],
        "poblacion": pais_datos.get("population"),
        "region": pais_datos.get("region") or "Sin datos",
        "subregion": pais_datos.get("subregion") or "Sin datos",
        "fuente": "countries.dev",
    }


def formatear_respuesta_pais(datos: dict) -> str:
    monedas = ", ".join(datos["monedas"])
    idiomas = ", ".join(datos["idiomas"])
    poblacion = datos["poblacion"]
    poblacion_texto = f"{poblacion:,}".replace(",", ".") if poblacion else "Sin datos"

    return (
        f'{datos["pais"]}: capital {datos["capital"]}; moneda(s): {monedas}; '
        f'idioma(s): {idiomas}; población: {poblacion_texto}; '
        f'región: {datos["region"]}. Fuente: {datos["fuente"]}.'
    )
