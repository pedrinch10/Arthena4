"""Calcula las tres métricas de HU-2 a partir de las fichas técnicas de CIMA."""

import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


DIRECTORIO = Path(__file__).resolve().parent.parent
ARCHIVO_ENTRADA = DIRECTORIO / "datos/medicamentos_artritis_reumatoide.xlsx"
ARCHIVO_SALIDA = DIRECTORIO / "datos/medicamentos_artritis_reumatoide_enriquecido.xlsx"
PATRON_SECCION_44 = re.compile(r"^\s*4[.]4(?:\b|[.]|\s)", re.IGNORECASE)
PATRON_GRAVES = re.compile(r"\bgraves?\b", re.IGNORECASE)

METRICAS_VACIAS = {
    "volumen_informativo_seguridad": None,
    "complejidad_desglose_clinico": None,
    "indicador_riesgo_severo": None,
}


def extraer_texto_seccion_44(soup: BeautifulSoup) -> str | None:
    """
    Extrae el contenido de 4.4 hasta el siguiente encabezado HTML.
    """
    encabezados = soup.find_all(re.compile(r"^h[1-6]$"))
    encabezado = next(
        (
            tag
            for tag in encabezados
            if (tag.get("id", "") == "4.4" or PATRON_SECCION_44.match(tag.get_text(" ", strip=True)))
        ),
        None,
    )
    if encabezado is None:
        return None

    partes = []
    for elemento in encabezado.find_next_siblings():
        if elemento.name and re.fullmatch(r"h[1-6]", elemento.name, re.IGNORECASE):
            break
        texto = elemento.get_text(" ", strip=True)
        if texto:
            partes.append(texto)
    return " ".join(partes)


def analizar_html(html: bytes | str) -> tuple[dict, str]:
    """
    Calcula métricas del HTML; mantiene el indicador de riesgo sobre todo el documento.
    """
    soup = BeautifulSoup(html, "html.parser")
    texto_documento = soup.get_text(" ", strip=True)
    texto_seccion = extraer_texto_seccion_44(soup)

    metricas = {
        "volumen_informativo_seguridad": (
            len(texto_seccion.split()) if texto_seccion is not None else None
        ),
        "complejidad_desglose_clinico": len(soup.find_all("table")),
        "indicador_riesgo_severo": len(PATRON_GRAVES.findall(texto_documento)),
    }
    estado = "OK" if texto_seccion is not None else "ERROR"
    return metricas, estado


def analizar_ficha_tecnica(url: object, session: requests.Session | None = None) -> tuple[dict, str]:
    """
    Descarga una ficha y devuelve métricas y estado para distinguir errores de ceros.
    """
    if not isinstance(url, str) or not url.strip():
        return METRICAS_VACIAS.copy(), "URL ausente"

    cliente = session or requests
    try:
        response = cliente.get(
            url.strip()
        )
        response.raise_for_status()
        return analizar_html(response.content)
    except requests.RequestException as error:
        return METRICAS_VACIAS.copy(), f"Error HTTP/conexión: {error.__class__.__name__}"
    except Exception as error:  # conserva la fila y hace visible un fallo de parseo inesperado
        return METRICAS_VACIAS.copy(), f"Error de análisis: {error.__class__.__name__}"


def main() -> None:
    df = pd.read_excel(ARCHIVO_ENTRADA)
    if "url_html_ficha_tecnica" not in df.columns:
        raise ValueError("El Excel de HU-1 no contiene 'url_html_ficha_tecnica'.")

    columnas = list(METRICAS_VACIAS)
    resultados = {columna: [] for columna in columnas}
    estados = []

    with requests.Session() as session:
        total = len(df)
        for indice, fila in enumerate(df.itertuples(index=False), start=1):
            registro = getattr(fila, "nregistro", "sin nregistro")
            url = getattr(fila, "url_html_ficha_tecnica")
            metricas, estado = analizar_ficha_tecnica(url, session)
            for columna in columnas:
                resultados[columna].append(metricas[columna])
            estados.append(estado)
            print(f"[{indice}/{total}] nregistro {registro}: {estado}")

    for columna, valores in resultados.items():
        df[columna] = valores
    df.to_excel(ARCHIVO_SALIDA, index=False)

    print(f"Excel HU-2 guardado: {ARCHIVO_SALIDA.name}")
    print(f"Fichas procesadas: {estados.count('OK')} de {len(df)}")
    print(f"Fichas con aviso: {estados.count('ERROR')}")


if __name__ == "__main__":
    main()
