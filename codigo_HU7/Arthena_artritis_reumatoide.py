"""Script maestro de la HU-7: orquesta el proyecto Arthena (artritis reumatoide) de principio a fin.

Ejecuta en orden HU1_HU3.py -> HU-4.py -> HU-5.py -> HU-6.py y registra todo con logging
en logs/Arthena_artritis_reumatoide_AAAAMMDD.log.

Decisiones de diseño (para poder defenderlas):
  * Cada paso se lanza con subprocess, como un proceso de Python aparte:
      - "HU-4.py" no se puede importar (el guion no es válido en un nombre de módulo);
      - si un paso se rompe, el maestro sigue vivo para registrar el error;
      - cada paso empieza "limpio", igual que si se ejecutara a mano.
  * Si un paso falla, se PARA: cada paso usa el fichero que genera el anterior, así que
    seguir solo produciría errores en cadena o, peor, resultados con datos viejos.
  * Después de cada paso se comprueba que sus ficheros de salida existen y se han
    actualizado en esta ejecución. Que un script termine sin error no basta.
  * Código de salida 0 si todo va bien y 1 si algo falla: el Programador de Tareas de
    Windows (o cron en Linux) lo muestra como "Resultado de la última ejecución".

Uso:
    python Arthena_artritis_reumatoide.py               # todo el flujo
    python Arthena_artritis_reumatoide.py --desde HU-4  # sin volver a llamar a la API ni al scraping
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent           # codigo_HU7
RAIZ = CARPETA.parent                               # Arthena4
DATOS = RAIZ / "datos"
CARPETA_LOGS = RAIZ / "logs"

NOMBRE = "Arthena_artritis_reumatoide"
TIMEOUT_PASO = 3 * 60 * 60     # 3 horas: la HU-1 y la HU-2 hacen cientos de peticiones web

# (nombre, script, ficheros que tiene que dejar actualizados)
PASOS = [
    ("HU1_HU3", "HU1_HU3.py", ["medicamentos_artritis_reumatoide.xlsx",
                               "medicamentos_artritis_reumatoide_enriquecido.xlsx",
                               "medicamentos_artritis_reumatoide_con_precios.xlsx"]),
    ("HU-4", "HU-4.py", ["medicamentos_artritis_reumatoide_hu4.xlsx",
                         "medicamentos_artritis_reumatoide_modelo.xlsx"]),
    ("HU-5", "HU-5.py", ["medicamentos_artritis_reumatoide_clusters.csv"]),
    ("HU-6", "HU-6.py", ["medicamentos_artritis_reumatoide_kpis.csv"]),
]

log = logging.getLogger(NOMBRE)


class PasoFallido(Exception):
    """Error esperado de un paso (código de salida != 0 o salida no generada)."""


def configurar_logging() -> Path:
    """Un fichero por día; si se ejecuta dos veces el mismo día, se añade al final (modo 'a')."""
    CARPETA_LOGS.mkdir(exist_ok=True)
    ruta_log = CARPETA_LOGS / f"{NOMBRE}_{datetime.now():%Y%m%d}.log"

    formato = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
    fichero = logging.FileHandler(ruta_log, mode="a", encoding="utf-8")
    fichero.setFormatter(formato)
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)

    log.setLevel(logging.INFO)
    log.addHandler(fichero)
    log.addHandler(consola)
    return ruta_log


def ejecutar_paso(nombre: str, script: str, salidas: list[str]) -> None:
    """Lanza un script, vuelca su salida en el log y comprueba sus ficheros. Lanza excepción si falla."""
    ruta_script = CARPETA / script
    if not ruta_script.exists():
        raise PasoFallido(f"No existe el script {ruta_script}")

    # Los hijos escriben en UTF-8 aunque Windows use otra codificación por defecto (tildes, €...)
    entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    inicio = time.time()

    resultado = subprocess.run(
        [sys.executable, str(ruta_script)],   # sys.executable = el mismo Python (el del .venv)
        cwd=RAIZ, env=entorno, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=TIMEOUT_PASO,
    )

    for linea in resultado.stdout.splitlines():
        if linea.strip():
            log.info("[%s] %s", nombre, linea)
    # stderr: si el paso ha ido bien solo son avisos de librerías; si ha fallado, es el error
    nivel = logging.WARNING if resultado.returncode == 0 else logging.ERROR
    for linea in resultado.stderr.splitlines():
        if linea.strip():
            log.log(nivel, "[%s] %s", nombre, linea)

    if resultado.returncode != 0:
        raise PasoFallido(f"{script} terminó con código {resultado.returncode} (el error está justo encima)")

    for fichero in salidas:
        ruta = DATOS / fichero
        if not ruta.exists():
            raise PasoFallido(f"{script} no ha generado {fichero}")
        if ruta.stat().st_mtime < inicio:
            raise PasoFallido(f"{script} no ha actualizado {fichero} (sigue siendo el de antes)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquestación del proyecto Arthena")
    parser.add_argument("--desde", choices=[p[0] for p in PASOS], default=PASOS[0][0],
                        help="paso desde el que empezar (por defecto, el primero)")
    args = parser.parse_args()

    ruta_log = configurar_logging()
    indice_inicio = [p[0] for p in PASOS].index(args.desde)
    pasos = PASOS[indice_inicio:]

    log.info("=" * 70)
    log.info("INICIO del flujo %s | pasos: %s", NOMBRE, ", ".join(p[0] for p in pasos))
    log.info("Python: %s | log: %s", sys.executable, ruta_log)
    inicio_total = time.time()

    for nombre, script, salidas in pasos:
        log.info("--- %s: empieza (%s)", nombre, script)
        inicio = time.time()
        try:
            ejecutar_paso(nombre, script, salidas)
        except PasoFallido as error:
            log.error("%s: %s", nombre, error)
        except subprocess.TimeoutExpired:
            log.error("%s: superado el tiempo máximo de %d s", nombre, TIMEOUT_PASO)
        except Exception:
            # Error inesperado del propio maestro: logger.exception guarda también el traceback
            log.exception("%s: error inesperado", nombre)
        else:
            log.info("--- %s: OK en %.1f s", nombre, time.time() - inicio)
            continue
        log.error("Flujo DETENIDO en %s (cada paso necesita la salida del anterior)", nombre)
        log.info("FIN con ERRORES tras %.1f s", time.time() - inicio_total)
        return 1

    log.info("FIN: flujo completado correctamente en %.1f s", time.time() - inicio_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
