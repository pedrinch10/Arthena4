"""HU-1, HU-2 y HU-3: extracción de CIMA, métricas de las fichas técnicas y precios del Nomenclátor."""

import io
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


DATOS = Path(__file__).resolve().parent.parent / "datos"
ARCHIVO_HU1 = DATOS / "medicamentos_artritis_reumatoide.xlsx"
ARCHIVO_HU2 = DATOS / "medicamentos_artritis_reumatoide_enriquecido.xlsx"
ARCHIVO_HU3 = DATOS / "medicamentos_artritis_reumatoide_con_precios.xlsx"

ENFERMEDAD = "artritis reumatoide"
URL_NOMENCLATOR = "https://www.sanidad.gob.es/profesionales/nomenclator.do?metodo=nomenclatorExcel"
COLUMNAS_NOMENCLATOR = ["Código Nacional", "Estado", "Precio de venta al público con IVA",
                        "Precio de referencia", "Tratamiento de larga duración", "Especial control médico"]

# Los identificadores se leen como texto para no perder los ceros a la izquierda
TIPOS = {"nregistro": str, "cn": str}


# HU-1
def obtener_nregistros(enfermedad):
    """Llamadas POST paginadas a CIMA para obtener los nregistro de la enfermedad."""
    url_base = "https://cima.aemps.es/cima/rest/buscarEnFichaTecnica"
    payload = [{"seccion": "4.1", "texto": enfermedad, "contiene": 1}]
    nregistros = []
    pagina = 1

    while True:
        response = requests.post(f"{url_base}?pagina={pagina}", json=payload)
        response.raise_for_status()
        data = response.json()
        resultados = data.get("resultados", [])
        nregistros += [item["nregistro"] for item in resultados if item.get("nregistro")]

        if not resultados or len(nregistros) >= data.get("totalFilas", 0):
            break
        pagina += 1

    return list(dict.fromkeys(nregistros))   # sin duplicados y en el mismo orden


def obtener_detalle(nregistro):
    """Llamada GET a CIMA con las características de un medicamento."""
    response = requests.get(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={nregistro}", timeout=30)
    response.raise_for_status()
    med = response.json()

    cn = next((p["cn"] for p in med.get("presentaciones", []) if p.get("cn")), None)
    url_html = next((d["urlHtml"] for d in med.get("docs", []) if d.get("tipo") == 1 and d.get("urlHtml")), None)
    url_foto = next((f["url"] for f in med.get("fotos", [])
                     if "material" in str(f.get("tipo", "")).lower() and f.get("url", "").lower().endswith(".jpg")), None)

    return {
        "nregistro": med.get("nregistro"),
        "nombre": med.get("nombre"),
        "pactivos": ", ".join(pa["nombre"] for pa in med.get("principiosActivos", []) if pa.get("nombre")),
        "labtitular": med.get("labtitular"),
        "labcomercializador": med.get("labcomercializador"),
        "cn": cn,
        "dosis": med.get("dosis"),
        "forma_farmaceutica_simplificada": (med.get("formaFarmaceuticaSimplificada") or {}).get("nombre"),
        "estado_aut": med.get("estado", {}).get("aut"),
        "estado_rev": med.get("estado", {}).get("rev"),
        "comercializado": int(bool(med.get("comerc"))),
        "requiere_receta": int(bool(med.get("receta"))),
        "generico": int(bool(med.get("generico"))),
        "afecta_conduccion": int(bool(med.get("conduc"))),
        "triangulo_negro": int(bool(med.get("triangulo"))),
        "medicamento_huerfano": int(bool(med.get("huerfano"))),
        "biosimilar": int(bool(med.get("biosimilar"))),
        "url_html_ficha_tecnica": url_html,
        "url_foto_materiales": url_foto,
        "num_registros_atc": len(med.get("atcs", [])),
        "num_principios_activos": len(med.get("principiosActivos", [])),
        "num_excipientes": len(med.get("excipientes", [])),
        "vias_administracion": ", ".join(v["nombre"] for v in med.get("viasAdministracion", []) if v.get("nombre")),
    }


def hu1():
    nregistros = obtener_nregistros(ENFERMEDAD)
    df = pd.DataFrame([obtener_detalle(n) for n in nregistros])
    df.to_excel(ARCHIVO_HU1, index=False)
    return df


# HU-2
PATRON_SECCION_44 = re.compile(r"^\s*4[.]4(?:\b|[.]|\s)")
PATRON_GRAVES = re.compile(r"\bgraves?\b", re.IGNORECASE)


def analizar_ficha(url):
    """Descarga una ficha técnica y calcula sus tres métricas."""
    if not isinstance(url, str):
        return {}
    response = requests.get(url, timeout=30)
    # si una ficha no responde, sus métricas quedan vacías
    if not response.ok:          
        return {}
    soup = BeautifulSoup(response.content, "html.parser")

    # Texto de la sección 4.4: desde su encabezado hasta el siguiente encabezado
    encabezado = next((h for h in soup.find_all(re.compile(r"^h[1-6]$"))
                       if h.get("id") == "4.4" or PATRON_SECCION_44.match(h.get_text(" ", strip=True))), None)
    palabras_44 = None
    if encabezado is not None:
        partes = []
        for elemento in encabezado.find_next_siblings():
            if re.fullmatch(r"h[1-6]", elemento.name or ""):
                break
            partes.append(elemento.get_text(" ", strip=True))
        palabras_44 = len(" ".join(partes).split())

    return {
        "volumen_informativo_seguridad": palabras_44,
        "complejidad_desglose_clinico": len(soup.find_all("table")),
        "indicador_riesgo_severo": len(PATRON_GRAVES.findall(soup.get_text(" ", strip=True))),
    }


def hu2():
    df = pd.read_excel(ARCHIVO_HU1, dtype=TIPOS)
    metricas = pd.DataFrame([analizar_ficha(url) for url in df["url_html_ficha_tecnica"]], index=df.index)
    df = pd.concat([df, metricas], axis=1)
    df.to_excel(ARCHIVO_HU2, index=False)
    return df


# HU-3
def hu3():
    df = pd.read_excel(ARCHIVO_HU2, dtype=TIPOS)

    # Descarga del listado completo del Nomenclátor (sustituye al fichero descargado a mano)
    response = requests.get(URL_NOMENCLATOR, timeout=120)
    response.raise_for_status()
    nomenclator = pd.read_excel(io.BytesIO(response.content))[COLUMNAS_NOMENCLATOR]

    # Cruce por Código Nacional en formato numérico para que coincidan los tipos de ambas tablas
    df["cn_cruce"] = pd.to_numeric(df["cn"], errors="coerce")
    nomenclator["cn_cruce"] = pd.to_numeric(nomenclator["Código Nacional"], errors="coerce")
    df = (df.merge(nomenclator.drop(columns="Código Nacional"), on="cn_cruce", how="left")
            .drop(columns="cn_cruce"))

    df.to_excel(ARCHIVO_HU3, index=False)
    return df


if __name__ == "__main__":
    hu1()
    hu2()
    hu3()
