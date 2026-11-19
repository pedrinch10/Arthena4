"""HU-4: limpieza y transformación de los datos (reglas definidas en el EDA del Sprint 2)."""

from pathlib import Path

import numpy as np
import pandas as pd


DATOS = Path(__file__).resolve().parent.parent / "datos"
ARCHIVO_ENTRADA = DATOS / "medicamentos_artritis_reumatoide_con_precios.xlsx"
ARCHIVO_SALIDA = DATOS / "medicamentos_artritis_reumatoide_hu4.csv"

PVP = "Precio de venta al público con IVA"
MIN_CASOS_VIA = 5


def quitar_tildes(serie):
    return serie.str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("ascii")


def main():
    df = pd.read_excel(ARCHIVO_ENTRADA, dtype={"nregistro": str, "cn": str})

    # Identificador: nregistro con los ceros a la izquierda, tomado de la URL de la ficha técnica
    df["nregistro"] = df["url_html_ficha_tecnica"].str.extract(r"/ft/(\d+)/")[0].fillna(df["nregistro"])

    # Dosis en miligramos (los gramos se multiplican por 1000)
    dosis_txt = df["dosis"].str.lower()
    dosis_mg = (dosis_txt.str.extract(r"(\d+(?:[.,]\d+)?)\s*mg\b")[0]
                .str.replace(r"^(\d{1,3})\.(\d{3})$", r"\1\2", regex=True)   # separador de miles
                .str.replace(",", ".", regex=False).astype(float))
    dosis_g = dosis_txt.str.extract(r"(\d+(?:[.,]\d+)?)\s*g\b")[0].str.replace(",", ".", regex=False).astype(float) * 1000
    df["dosis_mg"] = dosis_mg.fillna(dosis_g)

    # Fechas: de milisegundos a fecha (hora de Madrid)
    for col in ["estado_aut", "estado_rev"]:
        df[col] = (pd.to_datetime(df[col].astype("Int64"), unit="ms", utc=True)
                   .dt.tz_convert("Europe/Madrid").dt.tz_localize(None).dt.normalize())
    df["antiguedad_anios"] = ((pd.Timestamp.today() - df["estado_aut"]).dt.days / 365.25).round(1)
    df["tiene_revision"] = df["estado_rev"].notna().astype(int)

    # SI/NO a 1/0
    for col in ["Especial control médico", "Tratamiento de larga duración"]:
        df[col] = df[col].map({"SI": 1, "NO": 0})

    # Estado del Nomenclátor: ALTA / BAJA / SIN DATO
    df["Estado"] = np.select([df["Estado"] == "ALTA", df["Estado"].notna()], ["ALTA", "BAJA"], default="SIN DATO")

    # Precio: mediana de medicamentos equivalentes (mismo principio activo, dosis y forma)
    mediana_grupo = df.groupby(["pactivos", "dosis_mg", "forma_farmaceutica_simplificada"])[PVP].transform("median")
    df["precio_rellenado"] = (df[PVP].isna() & mediana_grupo.notna()).astype(int)
    df[PVP] = df[PVP].fillna(mediana_grupo)
    df["tiene_precio"] = df[PVP].notna().astype(int)

    # Forma farmacéutica sin tildes y agrupada (el orden de las condiciones importa)
    df["forma_farmaceutica_simplificada"] = quitar_tildes(df["forma_farmaceutica_simplificada"])
    forma = df["forma_farmaceutica_simplificada"]
    df["forma_agrupada"] = np.select(
        [forma.str.contains("PERFUSION"), forma.str.contains("INYECTABLE"),
         forma.str.contains("SUPOSITORIO"), forma.str.contains("SOLUCION|SUSPENSION|GOTAS")],
        ["PERFUSION", "INYECTABLE", "RECTAL", "ORAL LIQUIDO"], default="ORAL SOLIDO")
    df["inyectable"] = forma.str.contains("INYECTABLE").astype(int)

    # Vías de administración: una columna 0/1 por vía; las poco frecuentes se agrupan en via_otras
    vias = df["vias_administracion"].str.get_dummies(sep=", ")
    vias.columns = "via_" + quitar_tildes(vias.columns.str.replace("VÍA ", "").to_series()).str.lower().str.replace(" ", "_").values
    vias["via_otras"] = vias.loc[:, vias.sum() < MIN_CASOS_VIA].max(axis=1)
    df = pd.concat([df, vias], axis=1)

    # Nombres de columnas en snake_case
    df = df.rename(columns={
        "estado_aut": "fecha_autorizacion",
        "estado_rev": "fecha_revision",
        "Estado": "estado_nomenclator",
        PVP: "pvp_iva",
        "Precio de referencia": "precio_referencia",
        "Tratamiento de larga duración": "tratamiento_larga_duracion",
        "Especial control médico": "especial_control_medico",
    })

    df.to_csv(ARCHIVO_SALIDA, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    main()
