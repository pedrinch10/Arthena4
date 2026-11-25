"""HU-6: carga en MySQL, vista de KPIs y fichero final con fecha."""

import json
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd


DATOS = Path(__file__).resolve().parent.parent / "datos"
CONFIG = Path(__file__).resolve().parent.parent / "config.json"
ARCHIVO_ENTRADA = DATOS / "medicamentos_artritis_reumatoide_clusters.csv"
ARCHIVO_FINAL = DATOS / f"medicamentos_artritis_reumatoide_final_{datetime.now():%Y%m%d_%H%M}.csv"

COLUMNAS = ["nregistro", "cn", "nombre", "pactivos", "forma_farmaceutica_simplificada", "dosis_mg",
            "cluster", "nombre_cluster", "pvp_iva", "precio_referencia", "tiene_precio",
            "volumen_informativo_seguridad", "complejidad_desglose_clinico", "indicador_riesgo_severo",
            "num_principios_activos", "num_excipientes", "comercializado", "generico", "biosimilar",
            "antiguedad_anios","url_html_ficha_tecnica","url_foto_materiales","fecha_autorizacion",
            "fecha_revision"]

SQL_TABLA = """
CREATE TABLE IF NOT EXISTS medicamentos (
    nregistro                        VARCHAR(10)   NOT NULL,
    cn                               VARCHAR(10),
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
    url_html_ficha_tecnica           VARCHAR(300),
    url_foto_materiales              VARCHAR(300),
    labtitular                       VARCHAR(100),
    labcomercializador               VARCHAR(100),
    fecha_autorizacion               DATE,
    fecha_revision                   DATE,
    PRIMARY KEY (nregistro)
)"""

SQL_VISTA = """
CREATE OR REPLACE VIEW vista_kpi_medicamentos AS
SELECT
    m.*,
    (m.pvp_iva - m.precio_referencia) / NULLIF(m.precio_referencia, 0) * 100 AS desviacion_precio_pct,
    m.volumen_informativo_seguridad / NULLIF(m.complejidad_desglose_clinico, 0) AS densidad_ficha_tecnica,
    COALESCE(m.num_principios_activos, 0) + COALESCE(m.num_excipientes, 0) AS total_componentes,
    m.pvp_iva - m.precio_referencia AS margen_economico_absoluto,
    CASE WHEN m.pvp_iva IS NULL THEN NULL
         ELSE RANK() OVER (PARTITION BY m.forma_farmaceutica_simplificada ORDER BY m.pvp_iva DESC)
    END AS ranking_precio_forma,
    ROUND(m.pvp_iva / NULLIF(AVG(m.pvp_iva) OVER (PARTITION BY m.forma_farmaceutica_simplificada), 0), 2)
        AS indice_precio_relativo_forma
FROM medicamentos m
"""


def main():
    df = pd.read_csv(ARCHIVO_ENTRADA, dtype={"nregistro": str, "cn": str})

    # Los KPIs de negocio solo usan precios oficiales: se quitan los rellenados en la HU-4
    df.loc[df["precio_rellenado"] == 1, "pvp_iva"] = None
    df["tiene_precio"] = df["pvp_iva"].notna().astype(int)
    df_load = df[COLUMNAS]

    # Los datos de conexión se leen de config.json (en el .gitignore, no se sube a GitHub)
    with open(CONFIG, encoding="utf-8") as f:
        conn = mysql.connector.connect(**json.load(f))
    cursor = conn.cursor()
    cursor.execute(SQL_TABLA)

    # Se reescriben los datos dentro de una transacción: si los conteos no cuadran, se deshace todo
    filas = list(df_load.astype(object).where(df_load.notna(), None).itertuples(index=False, name=None))
    sql_insert = f"INSERT INTO medicamentos ({', '.join(COLUMNAS)}) VALUES ({', '.join(['%s'] * len(COLUMNAS))})"
    cursor.execute("DELETE FROM medicamentos")
    cursor.executemany(sql_insert, filas)
    cursor.execute("SELECT COUNT(*) FROM medicamentos")
    if cursor.fetchone()[0] != len(df_load):
        conn.rollback()
        raise ValueError("El número de filas en MySQL no coincide con el del dataset")
    conn.commit()

    cursor.execute(SQL_VISTA)
    cursor.close()
    conn.close()

    # Fichero final con fecha y hora: los anteriores no se borran
    df_load.to_csv(ARCHIVO_FINAL, index=False, encoding="utf-8-sig")
    return df_load


if __name__ == "__main__":
    main()
