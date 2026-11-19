"""HU-5: asignación del cluster K-Means a cada medicamento."""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


DATOS = Path(__file__).resolve().parent.parent / "datos"
ARCHIVO_ENTRADA = DATOS / "medicamentos_artritis_reumatoide_hu4.csv"
ARCHIVO_SALIDA = DATOS / "medicamentos_artritis_reumatoide_clusters.csv"
ARCHIVO_MODELO = DATOS / "modelo_kmeans.joblib"
PATRON_FINALES = "medicamentos_artritis_reumatoide_final_*.csv"   # ficheros finales con fecha de la HU-6

VARIABLES = ["volumen_informativo_seguridad", "complejidad_desglose_clinico",
             "indicador_riesgo_severo", "pvp_iva", "antiguedad_anios"]
VARIABLES_LOG = ["volumen_informativo_seguridad", "complejidad_desglose_clinico",
                 "indicador_riesgo_severo", "pvp_iva"]
K = 6


def preparar(df):
    """Mismas transformaciones que en el Sprint 2: precio nulo = 0 y logaritmo en las variables asimétricas."""
    X = df[VARIABLES].fillna({"pvp_iva": 0})
    X[VARIABLES_LOG] = np.log1p(X[VARIABLES_LOG])
    return X


def entrenar(df, X):
    """Solo se usa la primera vez: entrena el modelo del Sprint 2 y pone nombre a los clusters."""
    scaler = StandardScaler().fit(X)
    kmeans = KMeans(n_clusters=K, n_init=20, random_state=42).fit(scaler.transform(X))

    perfil = df[VARIABLES].assign(cluster=kmeans.labels_).groupby("cluster").mean()
    perfil["sin_precio"] = df["pvp_iva"].isna().groupby(kmeans.labels_).mean()

    # Reglas de nombres del Sprint 2
    nombres = {}
    reglas = [("sin_precio", "max", "Biológicos y terapias dirigidas"),
              ("antiguedad_anios", "max", "Clásicos de larga trayectoria"),
              ("volumen_informativo_seguridad", "min", "Fichas breves (corticoides y analgésicos)"),
              ("pvp_iva", "min", "AINE genéricos económicos"),
              ("volumen_informativo_seguridad", "max", "FAME e inmunosupresores")]
    for columna, criterio, nombre in reglas:
        c = perfil[columna].idxmax() if criterio == "max" else perfil[columna].idxmin()
        nombres[c] = nombre
        perfil = perfil.drop(c)
    nombres[perfil.index[0]] = "Coxibs (antiinflamatorios selectivos)"

    joblib.dump({"scaler": scaler, "kmeans": kmeans, "nombres": nombres}, ARCHIVO_MODELO)


def main():
    df = pd.read_csv(ARCHIVO_ENTRADA, dtype={"nregistro": str, "cn": str})
    X = preparar(df)

    if not ARCHIVO_MODELO.exists():
        entrenar(df, X)
    modelo = joblib.load(ARCHIVO_MODELO)

    df["cluster"] = modelo["kmeans"].predict(modelo["scaler"].transform(X))
    df["nombre_cluster"] = df["cluster"].map(modelo["nombres"])

    # Cambios de cluster respecto al último fichero final guardado
    finales = sorted(DATOS.glob(PATRON_FINALES))
    if finales:
        anterior = pd.read_csv(finales[-1], dtype={"nregistro": str}, usecols=["nregistro", "cluster"])
        comparacion = df[["nregistro", "cluster"]].merge(anterior, on="nregistro", suffixes=("", "_anterior"))
        cambios = (comparacion["cluster"] != comparacion["cluster_anterior"]).sum()
        logging.info(f"HU-5: {cambios} de {len(comparacion)} medicamentos "
                     f"({cambios / len(comparacion):.1%}) han cambiado de cluster respecto a {finales[-1].name}")
    else:
        logging.info("HU-5: no hay una versión anterior con la que comparar los clusters")

    df.to_csv(ARCHIVO_SALIDA, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    main()
