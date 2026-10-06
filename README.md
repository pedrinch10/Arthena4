# BIODATAPHARMA · Arthena

Automatización de la extracción y análisis de medicamentos para artritis reumatoide mediante CIMA, las fichas técnicas y el nomenclátor del Ministerio de Sanidad.

## Estado

- **HU-1 — Completada:** extracción CIMA y Excel con los 23 campos solicitados.
- **HU-2 — Completada:** las tres métricas de fichas técnicas están calculadas para 645/645 registros.
- **HU-3 — Implementada:** el Excel final incorpora las seis columnas requeridas del nomenclátor.

**Cobertura económica:** con el nomenclátor de septiembre de 2026 hay 339 coincidencias de 645 códigos nacionales; 306 no aparecen en ese fichero y quedan sin datos económicos. En las coincidencias hay 339 valores de Estado, PVP con IVA, tratamiento de larga duración y especial control médico; 316 tienen precio de referencia informado. No se imputan valores ausentes. [Fuente oficial del nomenclátor](https://www.sanidad.gob.es/profesionales/nomenclator.do).

## Wiki por fechas

`->` Objetivo o tarea · `~>` desarrollo o ajuste · `>` paso técnico · `>>` evidencia · `=>` resultado.

### 22/09/2026 -> Inicio y HU-1

`->` Se configuró el repositorio y se implementó la extracción de medicamentos para artritis reumatoide desde CIMA.

`>` Se consultó la sección 4.1 con paginación y se obtuvo el detalle de cada `nregistro`.

`>>` `medicamentos_artritis_reumatoide.xlsx`: 645 filas, 23 columnas y 0 `nregistro` duplicados.

`=>` HU-1 completada, incluida la generación del Excel (punto 1.3).

### 24/09/2026 -> HU-2 y cruce inicial HU-3

`->` Se incorporó el análisis de fichas técnicas y se inició el cruce con el nomenclátor.

`>` HU-2 calcula palabras de la sección 4.4, etiquetas `<table>` y apariciones de «grave/graves».

`>>` Se añadió el fichero `20260924_Nomenclator_de_Facturacion.xls` como fuente económica.

### 30/09/2026 -> Revisión final frente al PDF

`~>` Se corrigió `comercializado`: el script leía la clave `comercializado`, pero la API de CIMA devuelve `comerc`, por lo que la columna valía 0 en los 645 registros. `url_foto_materiales` exige ahora tipo con «material» y extensión `.jpg`, como indica el PDF.

`>` Se volvió a ejecutar el flujo completo en orden: `extraccion_medicamentos_inicial.py` → `web_scraper_kpis.py` → `join_datos_csv.py`.

`>>` Los tres Excel conservan 645 filas, 645 `nregistro` únicos y 0 duplicados. HU-1: 23 columnas y 437 medicamentos comercializados. HU-2: 27 columnas y 645/645 fichas procesadas sin avisos. HU-3: 33 columnas y las seis variables económicas solicitadas. Las 9 pruebas automáticas pasan.

`>>` El nomenclátor contiene coincidencia para 339/645 códigos; 306 no aparecen en el fichero. De las coincidencias, 316 incluyen precio de referencia. No se estiman ni imputan valores ausentes.

`=>` El código y los ficheros generados cubren las transformaciones y salidas pedidas hasta HU-3.3. La disponibilidad de datos económicos sigue limitada a la cobertura de la fuente oficial. El informe detallado, elaborado sobre la plantilla, está en `docx/Informe_Sprint_1_Arthena.docx`; la copia `_v2` contiene el mismo informe.

## Ejecución

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python extraccion_medicamentos_inicial.py
.venv/bin/python web_scraper_kpis.py
.venv/bin/python join_datos_csv.py
```

Las rutas de entrada y salida se resuelven desde la ubicación de cada script. HU-3 utiliza el nomenclátor local `20260924_Nomenclator_de_Facturacion.xls`.

## Verificación

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Nueve pruebas comprueban la paginación y campos de HU-1, los indicadores binarios y la foto de materiales según los nombres reales de los campos de CIMA, las métricas HU-2, el tratamiento explícito de secciones ausentes, la normalización del Código Nacional, la detección de duplicados en el nomenclátor, los campos requeridos y la conservación de filas en el cruce.
