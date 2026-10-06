from pathlib import Path
import pandas as pd
import requests


ARCHIVO_SALIDA = Path(__file__).resolve().parent / "medicamentos_artritis_reumatoide.xlsx"


def obtener_todos_los_nregistros(enfermedad: str) -> list:
    """
    Realiza la llamada POST a la API de CIMA de forma paginada para obtener
    todos los nregistros asociados a una enfermedad.
    """
    url_base = "https://cima.aemps.es/cima/rest/buscarEnFichaTecnica"
    payload = [{"seccion": "4.1",
                "texto": enfermedad,
                "contiene": 1
                }]
    nregistros = []
    pagina = 1
    total_filas = 0

    while True:
        url = f"{url_base}?pagina={pagina}"
        response = requests.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        resultados = data.get("resultados", [])

        if not resultados:
            break

        for item in resultados:
            if item.get("nregistro") is not None:
                nregistros.append(item["nregistro"])

        total_filas = data.get("totalFilas", 0)
        tamanio_pagina = data.get("tamanioPagina", len(resultados))

        if len(set(nregistros)) >= total_filas or len(resultados) < tamanio_pagina:
            break

        pagina += 1

    nregistros_unicos = list(dict.fromkeys(nregistros))
    if len(nregistros_unicos) < total_filas:
        raise RuntimeError(
            f"La API anunció {total_filas} registros y solo se recibieron "
            f"{len(nregistros_unicos)} tras paginar."
        )
    return nregistros_unicos


def obtener_detalle_medicamento(nregistro: str) -> dict:
    """
    Realiza una llamada GET por cada nregistro para extraer los atributos especificados.
    """
    url = f"https://cima.aemps.es/cima/rest/medicamento?nregistro={nregistro}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    med = response.json()

    # Crear todas las variables para almacenarlas despues
    # Presentaciones
    presentaciones = med.get("presentaciones", [])

    # Codigo nacional
    cn = next(
        (presentacion.get("cn") for presentacion in presentaciones if presentacion.get("cn")),
        None,
    )

    # Principios activos
    pactivos_list = [
        pa.get("nombre")
        for pa in med.get("principiosActivos", [])
        if pa.get("nombre")
    ]
    pactivos = ", ".join(pactivos_list)

    # URL Ficha tecnica
    docs = med.get("docs", [])
    url_html = None
    for doc in docs:
        if doc.get("tipo") == 1 and doc.get("urlHtml"):
            url_html = doc.get("urlHtml")
            break

    # URL Foto
    fotos = med.get("fotos", [])
    url_foto = None
    for foto in fotos:
        url = foto.get("url", "")
        if "material" in str(foto.get("tipo", "")).lower() and url.lower().endswith(".jpg"):
            url_foto = url
            break

    # Vías de administración
    vias = ", ".join(
        [
            via.get("nombre")
            for via in med.get("viasAdministracion", [])
            if via.get("nombre")
        ]
    )

    # Crear un diccionario con las variables que se quieren almacenar
    return {
        "nregistro": med.get("nregistro"),
        "nombre": med.get("nombre"),
        "pactivos": pactivos,
        "labtitular": med.get("labtitular"),
        "labcomercializador": med.get("labcomercializador"),
        "cn": cn,
        "dosis": med.get("dosis"),
        "forma_farmaceutica_simplificada": (
            med.get("formaFarmaceuticaSimplificada") or {}
        ).get("nombre"),
        "estado_aut": med.get("estado", {}).get("aut"),
        "estado_rev": med.get("estado", {}).get("rev"),
        "comercializado": 1 if med.get("comerc") else 0,
        "requiere_receta": 1 if med.get("receta") else 0,
        "generico": 1 if med.get("generico") else 0,
        "afecta_conduccion": 1 if med.get("conduc") else 0,
        "triangulo_negro": 1 if med.get("triangulo") else 0,
        "medicamento_huerfano": 1 if med.get("huerfano") else 0,
        "biosimilar": 1 if med.get("biosimilar") else 0,
        "url_html_ficha_tecnica": url_html,
        "url_foto_materiales": url_foto,
        "num_registros_atc": len(med.get("atcs", [])),
        "num_principios_activos": len(med.get("principiosActivos", [])),
        "num_excipientes": len(med.get("excipientes", [])),
        "vias_administracion": vias,
    }


def main():
    enfermedad = "artritis reumatoide"
    print(f"Buscando medicamentos para: '{enfermedad}'...")

    nregistros = obtener_todos_los_nregistros(enfermedad)
    print(f"Total de registros encontrados: {len(nregistros)}")

    datos_medicamentos = []
    for idx, nreg in enumerate(nregistros, start=1):
        print(
            f"[{idx}/{len(nregistros)}] Extrayendo detalle para nregistro: {nreg}"
        )
        detalle = obtener_detalle_medicamento(nreg)
        if detalle:
            datos_medicamentos.append(detalle)

    df = pd.DataFrame(datos_medicamentos)
    df.to_excel(ARCHIVO_SALIDA, index=False)
    print(f"Archivo exportado '{ARCHIVO_SALIDA.name}'.")


if __name__ == "__main__":
    main()
