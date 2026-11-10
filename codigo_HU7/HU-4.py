"""HU-4: limpieza y transformación del dataset consolidado (versión script del notebook del grupo).

Es la parte de codigo_HU4_HU5/HU4_EDA_medicamentos.ipynb que TRANSFORMA los datos.
Las gráficas y tablas de exploración se quedan en el notebook: un proceso programado
no tiene a nadie delante para mirarlas, y plt.show() lo dejaría bloqueado.

Entrada : datos/medicamentos_artritis_reumatoide_con_precios.xlsx   (HU-3)
Salidas : datos/medicamentos_artritis_reumatoide_hu4.xlsx           (dataset completo)
          datos/medicamentos_artritis_reumatoide_modelo.xlsx        (columnas para el K-Means)
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
RUTA_ENTRADA = DATOS / "medicamentos_artritis_reumatoide_con_precios.xlsx"
RUTA_COMPLETO = DATOS / "medicamentos_artritis_reumatoide_hu4.xlsx"
RUTA_MODELO = DATOS / "medicamentos_artritis_reumatoide_modelo.xlsx"

PVP = "Precio de venta al público con IVA"
MIN_CASOS_VIA = 5          # vías con menos casos se agrupan en via_otras

log = logging.getLogger("HU-4")


def quitar_tildes(serie: pd.Series) -> pd.Series:
    return serie.str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("ascii")


def corregir_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """nregistro desde la URL (recupera ceros a la izquierda), dosis en mg y fechas."""
    # nregistro: el Excel lo guarda como número y se pierden los ceros a la izquierda.
    # El número correcto está en la URL de la ficha técnica: .../ft/<nregistro>/...
    id_url = df["url_html_ficha_tecnica"].str.extract(r"/ft/(\d+)/")[0]
    log.info("nregistro corregidos desde la URL: %d", (id_url != df["nregistro"].astype(str)).sum())
    df["nregistro"] = id_url.astype(str)

    # dosis (texto libre) -> número en mg. Primero "mg"; si no hay, "g" * 1000.
    dosis_txt = df["dosis"].str.lower()
    dosis_mg = dosis_txt.str.extract(r"(\d+(?:[.,]\d+)?)\s*mg\b")[0]
    dosis_mg = dosis_mg.str.replace(r"^(\d{1,3})\.(\d{3})$", r"\1\2", regex=True)   # 1.000 -> 1000
    dosis_mg = dosis_mg.str.replace(",", ".", regex=False).astype(float)
    dosis_g = dosis_txt.str.extract(r"(\d+(?:[.,]\d+)?)\s*g\b")[0]
    dosis_g = dosis_g.str.replace(",", ".", regex=False).astype(float) * 1000
    dosis_unificada = dosis_mg.fillna(dosis_g)
    df["dosis_mg"] = dosis_unificada.astype(float).where(dosis_unificada.notna())
    log.info("dosis_mg con valor: %d de %d", df["dosis_mg"].notna().sum(), len(df))

    # Fechas: vienen en milisegundos desde 1970 (UTC)
    for col in ["estado_aut", "estado_rev"]:
        df[col] = (pd.to_datetime(df[col], unit="ms", utc=True)
                   .dt.tz_convert("Europe/Madrid").dt.tz_localize(None).dt.normalize())
    return df


def transformar_categoricas(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """SI/NO -> 1/0, vías en columnas 0/1, Estado, antigüedad y tipo de administración."""
    mapeo_sino = {"SI": 1, "NO": 0}
    df["Especial control médico"] = df["Especial control médico"].map(mapeo_sino)
    df["Tratamiento de larga duración"] = df["Tratamiento de larga duración"].map(mapeo_sino)

    # Un medicamento puede tener varias vías separadas por comas -> una columna por vía
    vias_distintas = df["vias_administracion"].str.get_dummies(sep=", ")
    df = pd.concat([df, vias_distintas], axis=1)

    mapeo_estado = {"BAJA GENERAL": 0, "BAJA POR NO COMERCIALIZAR": 0,
                    "SUSPENSION TEMPORAL GENERAL": 0, "ALTA": 1}
    df["Estado"] = df["Estado"].map(mapeo_estado).astype("boolean")

    df["antiguedad_anios"] = (pd.Timestamp.today() - df["estado_aut"]).dt.days / 365.25
    df["tipo_admin"] = np.where(
        df["forma_farmaceutica_simplificada"].str.contains("INYECTABLE", case=False, na=False),
        "Inyectable", "No inyectable")
    return df, vias_distintas.columns.tolist()


def preparar_final(df: pd.DataFrame, cols_vias: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Tratamientos pendientes del apartado 11 del notebook."""
    df_final = df.copy()
    df_final["cn"] = df_final["cn"].astype(str)

    # Precio: se rellena con la mediana de medicamentos equivalentes (mismo principio activo,
    # dosis y forma) y se marca con precio_rellenado para poder quitarlo en la HU-6.
    mediana_grupo = df_final.groupby(
        ["pactivos", "dosis_mg", "forma_farmaceutica_simplificada"])[PVP].transform("median")
    df_final["precio_rellenado"] = (df_final[PVP].isna() & mediana_grupo.notna()).astype(int)
    df_final[PVP] = df_final[PVP].fillna(mediana_grupo)
    df_final["tiene_precio"] = df_final[PVP].notna().astype(int)
    log.info("Precios rellenados: %d | con precio: %d | sin precio: %d",
             df_final["precio_rellenado"].sum(), df_final["tiene_precio"].sum(),
             (df_final["tiene_precio"] == 0).sum())

    df_final["Estado"] = df_final["Estado"].map({True: "ALTA", False: "BAJA"}).fillna("SIN DATO")

    df_final["tiene_revision"] = df_final["estado_rev"].notna().astype(int)
    df_final["antiguedad_anios"] = df_final["antiguedad_anios"].round(1)

    # Forma farmacéutica sin tildes y agrupada (el orden de las condiciones importa)
    df_final["forma_farmaceutica_simplificada"] = quitar_tildes(df_final["forma_farmaceutica_simplificada"])
    forma = df_final["forma_farmaceutica_simplificada"]
    condiciones = [forma.str.contains("PERFUSION"), forma.str.contains("INYECTABLE"),
                   forma.str.contains("SUPOSITORIO"), forma.str.contains("SOLUCION|SUSPENSION|GOTAS")]
    grupos = ["PERFUSION", "INYECTABLE", "RECTAL", "ORAL LIQUIDO"]
    df_final["forma_agrupada"] = np.select(condiciones, grupos, default="ORAL SOLIDO")

    df_final["inyectable"] = (df_final["tipo_admin"] == "Inyectable").astype(int)
    df_final = df_final.drop(columns=["tipo_admin"])

    # Columnas de vías: "VÍA ORAL" -> via_oral; las poco frecuentes se juntan en via_otras
    nombres_vias = ("via_" + quitar_tildes(pd.Series(cols_vias).str.replace("VÍA ", "", regex=False))
                    .str.lower().str.replace(" ", "_"))
    df_final = df_final.rename(columns=dict(zip(cols_vias, nombres_vias)))
    conteo_vias = df_final[nombres_vias].sum()
    vias_poco_frecuentes = conteo_vias[conteo_vias < MIN_CASOS_VIA].index.tolist()
    vias_principales = conteo_vias[conteo_vias >= MIN_CASOS_VIA].index.tolist()
    df_final["via_otras"] = df_final[vias_poco_frecuentes].max(axis=1)
    log.info("Vías principales: %s | agrupadas en via_otras: %d", vias_principales, len(vias_poco_frecuentes))

    df_final = df_final.rename(columns={
        "estado_aut": "fecha_autorizacion",
        "estado_rev": "fecha_revision",
        "Estado": "estado_nomenclator",
        PVP: "pvp_iva",
        "Tratamiento de larga duración": "tratamiento_larga_duracion",
        "Precio de referencia": "precio_referencia",
        "Especial control médico": "especial_control_medico",
    })
    return df_final, vias_principales


def preparar_modelo(df_final: pd.DataFrame, vias_principales: list[str]) -> pd.DataFrame:
    """Dataset numérico para el K-Means de la HU-5."""
    df_modelo = df_final.copy()
    df_modelo["estado_alta"] = (df_modelo["estado_nomenclator"] == "ALTA").astype(int)
    df_modelo["estado_baja"] = (df_modelo["estado_nomenclator"] == "BAJA").astype(int)

    dummies_forma = pd.get_dummies(df_modelo["forma_agrupada"], dtype=int)
    dummies_forma.columns = "forma_" + dummies_forma.columns.str.lower().str.replace(" ", "_")
    df_modelo = pd.concat([df_modelo, dummies_forma], axis=1)

    columnas_modelo = (
        ["nregistro", "nombre", "volumen_informativo_seguridad", "complejidad_desglose_clinico",
         "indicador_riesgo_severo", "pvp_iva", "dosis_mg", "antiguedad_anios",
         "num_principios_activos", "comercializado", "generico", "biosimilar", "afecta_conduccion",
         "triangulo_negro", "tratamiento_larga_duracion", "tiene_precio",
         "tiene_revision", "inyectable", "estado_alta", "estado_baja"]
        + vias_principales + ["via_otras"]
        + dummies_forma.columns.tolist()
    )
    return df_modelo[columnas_modelo]


def main() -> None:
    if not RUTA_ENTRADA.exists():
        raise FileNotFoundError(f"No existe la entrada de la HU-4 (la genera la HU-3): {RUTA_ENTRADA}")

    df = pd.read_excel(RUTA_ENTRADA)
    log.info("Leído %s: %d filas x %d columnas", RUTA_ENTRADA.name, *df.shape)

    df = corregir_tipos(df)
    df, cols_vias = transformar_categoricas(df)
    df_final, vias_principales = preparar_final(df, cols_vias)
    df_modelo = preparar_modelo(df_final, vias_principales)

    # Controles mínimos antes de escribir: si fallan, mejor parar que pasar datos malos a la HU-5
    if not df_final["nregistro"].is_unique:
        raise ValueError("Hay nregistro duplicados después de la limpieza")
    if len(df_final) != len(df) or len(df_modelo) != len(df):
        raise ValueError("La limpieza ha cambiado el número de filas")

    df_final.to_excel(RUTA_COMPLETO, index=False)
    df_modelo.to_excel(RUTA_MODELO, index=False)
    log.info("Guardado %s: %d x %d", RUTA_COMPLETO.name, *df_final.shape)
    log.info("Guardado %s: %d x %d", RUTA_MODELO.name, *df_modelo.shape)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
                        stream=sys.stdout)
    main()
