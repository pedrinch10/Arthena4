"""Enriquece el Excel de HU-2 con las variables del nomenclátor oficial."""

from pathlib import Path

import pandas as pd


DIRECTORIO = Path(__file__).resolve().parent.parent
ARCHIVO_ENTRADA = DIRECTORIO / "datos/medicamentos_artritis_reumatoide_enriquecido.xlsx"
ARCHIVO_NOMENCLATOR = DIRECTORIO / "datos/20260924_Nomenclator_de_Facturacion.xls"
ARCHIVO_SALIDA = DIRECTORIO / "datos/medicamentos_artritis_reumatoide_con_precios.xlsx"

COLUMNAS_NOMENCLATOR = [
    "Código Nacional",
    "Estado",
    "Precio de venta al público con IVA",
    "Precio de referencia",
    "Tratamiento de larga duración",
    "Especial control médico"
]


def enriquecer_medicamentos(df_hu2: pd.DataFrame, df_nomenclator: pd.DataFrame) -> pd.DataFrame:
    """
    Join de ambas tablas para incluir la columna de Precio de referencia a df_hu2
    """
    if "cn" not in df_hu2.columns:
        raise ValueError("El Excel de HU-2 debe contener la columna 'cn'.")

    faltantes = [col for col in COLUMNAS_NOMENCLATOR if col not in df_nomenclator.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en el nomenclátor: {faltantes}")    

    resultado = df_hu2.merge(
        df_nomenclator[COLUMNAS_NOMENCLATOR],
        left_on="cn",
        right_on="Código Nacional",
        how="left",
    ).drop(columns="Código Nacional")

    return resultado


def main() -> None:
    df_hu2 = pd.read_excel(ARCHIVO_ENTRADA)
    df_nomenclator = pd.read_excel(ARCHIVO_NOMENCLATOR)
    df_final = enriquecer_medicamentos(df_hu2, df_nomenclator)
    df_final.to_excel(ARCHIVO_SALIDA, index=False)

    coincidencias = df_final["Precio de referencia"].notna().sum()
    print(f"Excel final guardado: {ARCHIVO_SALIDA.name}")
    print(f"Precios de referencia obtenidos: {coincidencias} valores disponibles")
    print(f"El dataframe origina enriquecido tiene :(filas,columnas) {df_hu2.shape}")
    print(f"El dataframe con mas informacion oficial tiene: (filas, columnas) {df_final.shape}")

if __name__ == "__main__":
    main()
