"""HU-1 a HU-3: extracción CIMA, métricas de las fichas técnicas y cruce con el Nomenclátor.

No repite código: importa los tres scripts que ya existen en codigo_HU1_HU2_HU3/
y llama a su main() en orden. Cada uno lee el Excel que deja el anterior:

    HU-1  extraccion_medicamentos_inicial.py -> datos/medicamentos_artritis_reumatoide.xlsx
    HU-2  web_scraper_kpis.py                -> datos/medicamentos_artritis_reumatoide_enriquecido.xlsx
    HU-3  join_datos_csv.py                  -> datos/medicamentos_artritis_reumatoide_con_precios.xlsx
"""

import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # carpeta Arthena4
CARPETA_HU1_HU3 = RAIZ / "codigo_HU1_HU2_HU3"

# Para poder hacer "import" de scripts que están en otra carpeta,
# esa carpeta tiene que estar en la lista de sitios donde Python busca módulos.
sys.path.insert(0, str(CARPETA_HU1_HU3))

import extraccion_medicamentos_inicial as hu1   # noqa: E402  (el import va después de tocar sys.path)
import web_scraper_kpis as hu2                  # noqa: E402
import join_datos_csv as hu3                    # noqa: E402

log = logging.getLogger("HU1_HU3")


def main() -> None:
    log.info("HU-1: extracción de medicamentos desde la API de CIMA")
    hu1.main()

    log.info("HU-2: web scraping de las fichas técnicas")
    hu2.main()

    log.info("HU-3: cruce con el Nomenclátor por código nacional")
    hu3.main()

    log.info("HU-1 a HU-3 terminadas")


if __name__ == "__main__":
    # Formato sencillo: quien guarda la hora y el fichero de log es el script maestro.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
                        stream=sys.stdout)
    main()
