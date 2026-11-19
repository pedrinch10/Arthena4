# HU-7 · Orquestación, programación y logging

## Qué hay en esta carpeta

| Fichero | Qué hace | Lee | Escribe |
|---|---|---|---|
| `Arthena_artritis_reumatoide.py` | **Maestro**: ejecuta los 4 pasos en orden, registra todo en el log y para si algo falla | (nada) | `logs/Arthena_artritis_reumatoide_AAAAMMDD.log` |
| `HU1_HU3.py` | Llama a los `main()` de los 3 scripts de `codigo_HU1_HU2_HU3/` | API CIMA, fichas, Nomenclátor | `..._.xlsx`, `..._enriquecido.xlsx`, `..._con_precios.xlsx` |
| `HU-4.py` | Limpieza del notebook `HU4_EDA_medicamentos.ipynb`, sin gráficas | `..._con_precios.xlsx` | `..._hu4.xlsx`, `..._modelo.xlsx` |
| `HU-5.py` | K-Means (k = 6) y nombres de cluster de `HU5_KMeans.ipynb` | `..._modelo.xlsx`, `..._hu4.xlsx` | `..._clusters.csv` |
| `HU-6.py` | Carga en MySQL y vista de KPIs de `HU6_carga_mysql.ipynb` | `..._clusters.csv`, `..._hu4.xlsx` | tabla `medicamentos`, vista `vista_kpi_medicamentos`, `..._kpis.csv` |

Los notebooks contienen el análisis (gráficas, elección de k, comprobaciones).
Los `.py` son la parte que transforma datos y puede ejecutarse sola.

## Antes de la primera ejecución (una sola vez)

1. Instalar en el `.venv` las librerías que faltan en `requirements.txt`:
   ```
   .venv\Scripts\pip install scikit-learn mysql-connector-python
   ```
   (y añadir `scikit-learn>=1.3` y `mysql-connector-python>=8.0` a `requirements.txt`).
2. Usar el `config.json` local en la raíz de `Arthena4` para el script y el notebook de HU-6.
   El archivo está excluido de Git. Los campos `host`, `port`, `user` y `database` tienen como valores
   por defecto `localhost`, `3306`, `arthena_app` y `arthena`. Indica tu usuario de MySQL en `user`
   y su contraseña en `password`. Si omites `password` o lo dejas vacío, se usa `ARTHENA_MYSQL_PWD`.

## Ejecutarlo a mano

Desde la carpeta `Arthena4`:
```
.venv\Scripts\python codigo_HU7\Arthena_artritis_reumatoide.py --desde HU-4
.venv\Scripts\python codigo_HU7\Arthena_artritis_reumatoide.py
```
La primera orden no vuelve a llamar a la API ni al scraping (tarda segundos). La segunda ejecuta el flujo completo:
la HU-1 y la HU-2 hacen unas 1.300 peticiones web, así que puede tardar bastante.

Resultado: `logs\Arthena_artritis_reumatoide_AAAAMMDD.log`. Los `.log` están en `.gitignore` y no se suben.

## Programarlo con el Programador de Tareas de Windows

**Con la ventana** (`Win + R` → `taskschd.msc`) → *Crear tarea básica*:
- Nombre: `Arthena_artritis_reumatoide`
- Desencadenador: *Semanalmente*, lunes, 03:00 (o lo que queráis justificar)
- Acción: *Iniciar un programa*
  - Programa: `C:\Users\alvar\Master_Comillas\Ingenieria_Datos\Proyecto_FINAL\Arthena4\.venv\Scripts\python.exe`
  - Argumentos: `codigo_HU7\Arthena_artritis_reumatoide.py`
  - Iniciar en: `C:\Users\alvar\Master_Comillas\Ingenieria_Datos\Proyecto_FINAL\Arthena4`

**Con una orden** (equivalente):
```
schtasks /Create /TN "Arthena_artritis_reumatoide" /SC WEEKLY /D MON /ST 03:00 /TR "C:\Users\alvar\Master_Comillas\Ingenieria_Datos\Proyecto_FINAL\Arthena4\.venv\Scripts\python.exe C:\Users\alvar\Master_Comillas\Ingenieria_Datos\Proyecto_FINAL\Arthena4\codigo_HU7\Arthena_artritis_reumatoide.py"
schtasks /Run /TN "Arthena_artritis_reumatoide"
```
Para probarla: clic derecho en la tarea → *Ejecutar*. Después mira el `.log` y la columna
*Resultado de la última ejecución* (0x0 = bien, 0x1 = el maestro ha devuelto error).

Es importante usar el `python.exe` **del `.venv`**: el Python general de Windows no tiene pandas ni sklearn.

**Equivalente en Linux (crontab -e)**, por si lo preguntan:
```
0 3 * * 1  cd /ruta/Arthena4 && .venv/bin/python codigo_HU7/Arthena_artritis_reumatoide.py
```

## Cómo se ve un error (para enseñarlo en la defensa)

Renombra un momento `datos/medicamentos_artritis_reumatoide_con_precios.xlsx` y ejecuta con `--desde HU-4`. En el log sale:
```
ERROR | [HU-4] FileNotFoundError: No existe la entrada de la HU-4 (la genera la HU-3): ...
ERROR | HU-4: HU-4.py terminó con código 1 (el error está justo encima)
ERROR | Flujo DETENIDO en HU-4 (cada paso necesita la salida del anterior)
INFO  | FIN con ERRORES tras 0.3 s
```
Vuelve a ponerle el nombre original.

## Decisiones que hay que saber defender

1. **subprocess y no import.** `HU-4.py` no se puede importar (Python lee el guion como una resta).
   Además, si un paso se rompe, el maestro sigue vivo para registrar el error. `sys.executable` hace que
   cada paso use el mismo Python que el maestro, es decir, el del `.venv`.
2. **Si un paso falla, se para.** Cada paso usa el fichero del anterior. Seguir daría errores en cadena o,
   peor, resultados calculados con datos viejos.
3. **Se comprueban los ficheros de salida.** Que un script termine sin error no basta: el maestro mira que
   cada salida exista y tenga fecha de esta ejecución.
4. **Rutas con `Path(__file__)`.** El Programador de Tareas no arranca en vuestra carpeta: `"../datos"` fallaría.
5. **Nada interactivo.** Sin `plt.show()` (bloquea) ni `getpass()` (nadie puede escribir la clave a las 3:00).
   MySQL usa la clave de `config.json` o de `ARTHENA_MYSQL_PWD`. El archivo local guarda la clave en texto plano.
6. **Se puede repetir.** La HU-6 hace `DROP TABLE IF EXISTS` + `CREATE`, y la vista usa `CREATE OR REPLACE VIEW`:
   ejecutar el flujo dos veces no duplica filas.
7. **Un log por día.** Los handlers de `logging` escriben a la vez en el fichero y en la consola, con hora, nivel y paso.
   Si se ejecuta dos veces el mismo día, se añade al final del mismo fichero.

## Avisos

- **Los números de cluster pueden cambiar** entre ordenadores o versiones de scikit-learn. Los **nombres** no,
  porque se asignan por reglas (el cluster con más medicamentos sin precio, el más antiguo...). Comprobado: con
  los mismos datos, los 645 medicamentos tienen el mismo `nombre_cluster`, pero el número es otro.
  En Power BI filtrad por `nombre_cluster`, no por `cluster`.
- `antiguedad_anios` se calcula con la fecha del día: cambia un poco en cada ejecución. Es lo esperado.
- Volver a ejecutar la HU-1 descarga los datos actuales de CIMA: el número de medicamentos puede no ser 645.
