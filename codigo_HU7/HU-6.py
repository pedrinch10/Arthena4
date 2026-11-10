"""HU-6: carga en MySQL y vista de KPIs (versión script del notebook del grupo).

Es codigo_HU4_HU5/HU6_carga_mysql.ipynb sin las consultas de exploración. Cambios para que
pueda ejecutarse solo, sin nadie delante:
  - La configuración de MySQL se lee del config.json local. Si falta la contraseña,
    se usa la variable de entorno ARTHENA_MYSQL_PWD.
  - Las verificaciones del notebook se convierten en controles: si algo no cuadra se hace
    ROLLBACK y se lanza un error, para que el script maestro lo registre y pare.

Entradas: datos/medicamentos_artritis_reumatoide_clusters.csv  (HU-5)
          datos/medicamentos_artritis_reumatoide_hu4.xlsx      (HU-4, columnas que faltan)
Salidas : tabla arthena.medicamentos y vista arthena.vista_kpi_medicamentos
          datos/medicamentos_artritis_reumatoide_kpis.csv      (copia de la vista para Power BI)
"""

import json
import logging
import os
import sys
import warnings
from pathlib import Path

import mysql.connector
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CONFIG_MYSQL = RAIZ / "config.json"
DATOS = RAIZ / "datos"
RUTA_CLUSTERS = DATOS / "medicamentos_artritis_reumatoide_clusters.csv"
RUTA_HU4 = DATOS / "medicamentos_artritis_reumatoide_hu4.xlsx"
RUTA_KPIS = DATOS / "medicamentos_artritis_reumatoide_kpis.csv"

COLS_EXTRA = ["cn", "pactivos", "precio_referencia", "num_excipientes",
              "forma_farmaceutica_simplificada", "precio_rellenado"]
COLUMNAS = ["nregistro", "cn", "nombre", "pactivos", "forma_farmaceutica_simplificada", "dosis_mg",
            "cluster", "nombre_cluster", "pvp_iva", "precio_referencia", "tiene_precio",
            "volumen_informativo_seguridad", "complejidad_desglose_clinico", "indicador_riesgo_severo",
            "num_principios_activos", "num_excipientes", "comercializado", "generico", "biosimilar",
            "antiguedad_anios"]

SQL_TABLA = """
CREATE TABLE medicamentos (
    nregistro                        VARCHAR(10)   NOT NULL,
    cn                               VARCHAR(10)   NOT NULL,
    nombre                           VARCHAR(300)  NOT NULL,
    pactivos                         VARCHAR(500),
    forma_farmaceutica_simplificada  VARCHAR(100),
    dosis_mg                         DECIMAL(10,2),
    cluster                          TINYINT       NOT NULL,
    nombre_cluster                   VARCHAR(100)  NOT NULL,
    pvp_iva                          DECIMAL(10,2),
    precio_referencia                DECIMAL(10,2),
    tiene_precio                     TINYINT(1)    NOT NULL,
    volumen_informativo_seguridad    INT,
    complejidad_desglose_clinico     INT,
    indicador_riesgo_severo          INT,
    num_principios_activos           TINYINT,
    num_excipientes                  TINYINT,
    comercializado                   TINYINT(1),
    generico                         TINYINT(1),
    biosimilar                       TINYINT(1),
    antiguedad_anios                 DECIMAL(5,1),
    PRIMARY KEY (nregistro)
)"""

SQL_VISTA = """
CREATE OR REPLACE VIEW vista_kpi_medicamentos AS
SELECT
    m.*,
    -- Desviación de Precio (%): (PVP-IVA - PR) / PR * 100
    (m.pvp_iva - m.precio_referencia) / NULLIF(m.precio_referencia, 0) * 100 AS desviacion_precio_pct,
    -- Densidad de la Ficha Técnica: palabras de la sección 4.4 / número de tablas
    m.volumen_informativo_seguridad / NULLIF(m.complejidad_desglose_clinico, 0) AS densidad_ficha_tecnica,
    -- Total de Componentes: principios activos + excipientes
    COALESCE(m.num_principios_activos, 0) + COALESCE(m.num_excipientes, 0) AS total_componentes,
    -- Margen Económico Absoluto: PVP-IVA - PR
    m.pvp_iva - m.precio_referencia AS margen_economico_absoluto,
    -- (PLUS) Ranking de precios dentro de cada forma farmacéutica (1 = el más caro; NULL si no hay precio)
    CASE WHEN m.pvp_iva IS NULL THEN NULL
         ELSE RANK() OVER (PARTITION BY m.forma_farmaceutica_simplificada ORDER BY m.pvp_iva DESC)
    END AS ranking_precio_forma,
    -- Índice de precio relativo: PVP / precio medio de su forma farmacéutica
    ROUND(m.pvp_iva / NULLIF(AVG(m.pvp_iva) OVER (PARTITION BY m.forma_farmaceutica_simplificada), 0), 2)
        AS indice_precio_relativo_forma
FROM medicamentos m
"""

log = logging.getLogger("HU-6")
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")


def preparar_datos() -> pd.DataFrame:
    """CSV de la HU-5 + columnas que faltan del Excel de la HU-4, sin precios rellenados."""
    for ruta in (RUTA_CLUSTERS, RUTA_HU4):
        if not ruta.exists():
            raise FileNotFoundError(f"No existe la entrada de la HU-6: {ruta}")

    df_clu = pd.read_csv(RUTA_CLUSTERS, dtype={"nregistro": str})
    df_hu4 = pd.read_excel(RUTA_HU4, dtype={"nregistro": str, "cn": str})
    cols_faltan = [c for c in COLS_EXTRA if c not in df_clu.columns]
    df = df_clu.merge(df_hu4[["nregistro"] + cols_faltan], on="nregistro", how="left", validate="1:1")
    log.info("CSV HU-5 %s + columnas de la HU-4 %s -> %s", df_clu.shape, cols_faltan, df.shape)

    # Un KPI de negocio no se calcula con precios estimados: se quitan los rellenados en la HU-4
    log.info("Precios rellenados que se quitan: %d", (df["precio_rellenado"] == 1).sum())
    df.loc[df["precio_rellenado"] == 1, "pvp_iva"] = None
    df["tiene_precio"] = df["pvp_iva"].notna().astype(int)

    df_load = df[COLUMNAS].copy()
    if not df_load["nregistro"].is_unique:
        raise ValueError("nregistro no es único: no puede ser la clave primaria")
    return df_load


def conectar():
    with RUTA_CONFIG_MYSQL.open(encoding="utf-8") as archivo:
        config = json.load(archivo)

    clave = config.get("password") or os.getenv("ARTHENA_MYSQL_PWD")
    if not clave:
        raise RuntimeError("Falta la clave de MySQL en config.json o en ARTHENA_MYSQL_PWD")

    conexion = {
        "host": config.get("host", "localhost"),
        "port": int(config.get("port", 3306)),
        "user": config.get("user", "arthena_app"),
        "database": config.get("database", "arthena"),
    }
    conn = mysql.connector.connect(password=clave, **conexion)
    log.info("Conectado a MySQL %s@%s/%s", conexion["user"], conexion["host"], conexion["database"])
    return conn


def cargar_tabla(conn, df_load: pd.DataFrame) -> None:
    """DROP + CREATE + INSERT. Se puede ejecutar tantas veces como se quiera (idempotente)."""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS medicamentos")
    cursor.execute(SQL_TABLA)

    # NaN de pandas -> None, que mysql.connector convierte en NULL
    df_sql = df_load.astype(object).where(df_load.notna(), None)
    filas = list(df_sql.itertuples(index=False, name=None))
    marcadores = ", ".join(["%s"] * len(COLUMNAS))
    cursor.executemany(f"INSERT INTO medicamentos ({', '.join(COLUMNAS)}) VALUES ({marcadores})", filas)

    cursor.execute("SELECT COUNT(*) FROM medicamentos")
    n_mysql = cursor.fetchone()[0]
    if n_mysql != len(df_load):
        conn.rollback()
        raise ValueError(f"Filas en pandas {len(df_load)} != filas en MySQL {n_mysql}: ROLLBACK")
    conn.commit()
    log.info("Tabla medicamentos cargada: %d filas (COMMIT)", n_mysql)

    # Mismos nulos en MySQL que en pandas (comprobación 7 del notebook)
    for col in ["dosis_mg", "pvp_iva", "precio_referencia"]:
        cursor.execute(f"SELECT SUM({col} IS NULL) FROM medicamentos")
        nulos_sql = int(cursor.fetchone()[0] or 0)
        nulos_pd = int(df_load[col].isna().sum())
        if nulos_sql != nulos_pd:
            raise ValueError(f"Nulos de {col}: MySQL {nulos_sql} != pandas {nulos_pd}")
    cursor.close()


def crear_vista_y_exportar(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(SQL_VISTA)
    cursor.close()
    log.info("Vista vista_kpi_medicamentos creada")

    df_kpis = pd.read_sql("SELECT * FROM vista_kpi_medicamentos", conn)
    df_kpis.to_csv(RUTA_KPIS, index=False, encoding="utf-8-sig")
    log.info("Exportado %s: %d x %d", RUTA_KPIS.name, *df_kpis.shape)


def main() -> None:
    df_load = preparar_datos()
    conn = conectar()
    try:
        cargar_tabla(conn, df_load)
        crear_vista_y_exportar(conn)
    finally:
        conn.close()   # se cierra la conexión aunque haya habido un error
        log.info("Conexión cerrada")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
                        stream=sys.stdout)
    main()
