"""HU-7: archivo maestro. Ejecuta en orden las HU-1 a HU-6 y registra el resultado en el log."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import HU1_HU3
import HU_4
import HU_5
import HU_6


CARPETA_LOGS = Path(__file__).resolve().parent.parent / "logs"
CARPETA_LOGS.mkdir(exist_ok=True)
LOG_FILE = CARPETA_LOGS / f"Arthena_artritis_reumatoide_{datetime.now():%Y%m%d_%H%M}.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8")

# (HU, función que la ejecuta, columnas que debe traer con datos al terminar)
PASOS = [
    #("HU-1", HU1_HU3.hu1, ["nregistro", "cn", "url_html_ficha_tecnica"]),
    #("HU-2", HU1_HU3.hu2, ["volumen_informativo_seguridad", "complejidad_desglose_clinico", "indicador_riesgo_severo"]),
    #("HU-3", HU1_HU3.hu3, ["Estado", "Precio de venta al público con IVA", "Precio de referencia"]),
    #("HU-4", HU_4.main, ["dosis_mg", "antiguedad_anios", "pvp_iva", "forma_agrupada"]),
    #("HU-5", HU_5.main, ["cluster", "nombre_cluster"]),
    ("HU-6", HU_6.main, ["nregistro", "cluster"]),
]


def ejecutar_paso(hu, funcion, columnas):
    """Ejecuta una HU y comprueba que el dataset generado no está vacío y trae las columnas nuevas"""
    logging.info(f"Iniciando {hu}")
    df = funcion()
    if df is None or df.empty:
        raise ValueError("Dataset vacío.")
    for col in columnas:
        if col not in df.columns or df[col].isna().all():
            raise ValueError(f"Falta la columna {col} o está vacía.")
    logging.info(f"ÉXITO en {hu}: {len(df)} filas.")


if __name__ == "__main__":
    logging.info("Inicio del flujo de orquestación.")
    for hu, funcion, columnas in PASOS:
        try:
            ejecutar_paso(hu, funcion, columnas)
        except Exception:
            logging.error(f"Error en {hu}: el flujo se detiene en este paso.")
            logging.critical("Flujo interrumpido.")
            sys.exit(1)
    logging.info("Flujo completado correctamente.")
