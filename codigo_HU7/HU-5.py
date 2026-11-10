"""HU-5: K-Means sobre los medicamentos y nombre de cada cluster (versión script del notebook del grupo).

Es la parte de codigo_HU4_HU5/HU5_KMeans.ipynb que entrena el modelo y asigna los nombres.
La elección de k (codo y silueta para k = 2..10) y las gráficas se hicieron en el notebook;
aquí k queda fijo en 6, que fue la decisión justificada allí.

Entradas: datos/medicamentos_artritis_reumatoide_modelo.xlsx   (HU-4)
          datos/medicamentos_artritis_reumatoide_hu4.xlsx      (HU-4, solo columnas descriptivas)
Salida  : datos/medicamentos_artritis_reumatoide_clusters.csv  (HU-4 modelo + cluster + nombre_cluster)
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
RUTA_MODELO = DATOS / "medicamentos_artritis_reumatoide_modelo.xlsx"
RUTA_COMPLETO = DATOS / "medicamentos_artritis_reumatoide_hu4.xlsx"
RUTA_SALIDA = DATOS / "medicamentos_artritis_reumatoide_clusters.csv"

K = 6
SEMILLA = 42
VARIABLES_MODELO = ["volumen_informativo_seguridad", "complejidad_desglose_clinico",
                    "indicador_riesgo_severo", "pvp_iva", "antiguedad_anios"]
VARIABLES_LOG = ["volumen_informativo_seguridad", "complejidad_desglose_clinico",
                 "indicador_riesgo_severo", "pvp_iva"]
COLS_DESCRIPTIVAS = ["pactivos", "forma_agrupada", "labtitular"]

log = logging.getLogger("HU-5")


def cargar_datos() -> pd.DataFrame:
    for ruta in (RUTA_MODELO, RUTA_COMPLETO):
        if not ruta.exists():
            raise FileNotFoundError(f"No existe la entrada de la HU-5 (la genera la HU-4): {ruta}")

    # nregistro como texto para no perder los ceros a la izquierda
    df = pd.read_excel(RUTA_MODELO, dtype={"nregistro": str})
    df_info = pd.read_excel(RUTA_COMPLETO, dtype={"nregistro": str},
                            usecols=["nregistro"] + COLS_DESCRIPTIVAS)
    df = df.merge(df_info, on="nregistro", how="left", validate="1:1")
    log.info("Datos del modelo: %d filas x %d columnas", *df.shape)
    return df


def preparar_X(df: pd.DataFrame) -> np.ndarray:
    """Precio nulo = 0, log1p a las variables con cola larga y estandarización."""
    X = df[VARIABLES_MODELO].copy()
    log.info("Precios nulos puestos a 0 para el modelo: %d", X["pvp_iva"].isna().sum())
    X["pvp_iva"] = X["pvp_iva"].fillna(0)
    X[VARIABLES_LOG] = np.log1p(X[VARIABLES_LOG])
    return StandardScaler().fit_transform(X)


def nombrar_clusters(df: pd.DataFrame) -> dict[int, str]:
    """Nombres por reglas sobre el perfil medio, no por el número del cluster.

    K-Means numera los grupos de forma arbitraria: si cambian los datos, el "cluster 3"
    puede ser otro grupo. Con reglas (el que más medicamentos sin precio tiene, el más
    antiguo...) el nombre sigue al perfil aunque cambie el número.
    """
    perfil = df.groupby("cluster")[VARIABLES_MODELO].mean()
    perfil["sin_precio_%"] = df["pvp_iva"].isna().groupby(df["cluster"]).mean() * 100

    reglas = [  # (columna, idxmax o idxmin, nombre)
        ("sin_precio_%", "max", "Biológicos y terapias dirigidas"),
        ("antiguedad_anios", "max", "Clásicos de larga trayectoria"),
        ("volumen_informativo_seguridad", "min", "Fichas breves (corticoides y analgésicos)"),
        ("pvp_iva", "min", "AINE genéricos económicos"),
        ("volumen_informativo_seguridad", "max", "FAME e inmunosupresores"),
    ]
    pendientes = perfil.copy()
    nombres = {}
    for columna, criterio, nombre in reglas:
        c = pendientes[columna].idxmax() if criterio == "max" else pendientes[columna].idxmin()
        nombres[c] = nombre
        pendientes = pendientes.drop(c)
    nombres[pendientes.index[0]] = "Coxibs (antiinflamatorios selectivos)"
    return nombres


def main() -> None:
    df = cargar_datos()
    X_scaled = preparar_X(df)

    kmeans = KMeans(n_clusters=K, n_init=20, random_state=SEMILLA)
    df["cluster"] = kmeans.fit_predict(X_scaled)
    silueta = silhouette_score(X_scaled, df["cluster"])
    log.info("K-Means con k=%d | silueta media = %.3f", K, silueta)

    nombres = nombrar_clusters(df)
    df["nombre_cluster"] = df["cluster"].map(nombres)
    for nombre, n in df["nombre_cluster"].value_counts().items():
        log.info("  %-45s %4d medicamentos", nombre, n)

    if df["nombre_cluster"].isna().any():
        raise ValueError("Hay medicamentos sin nombre de cluster")

    df_salida = df.drop(columns=COLS_DESCRIPTIVAS)
    df_salida.to_csv(RUTA_SALIDA, index=False, encoding="utf-8-sig")
    log.info("Guardado %s: %d x %d", RUTA_SALIDA.name, *df_salida.shape)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
                        stream=sys.stdout)
    main()
