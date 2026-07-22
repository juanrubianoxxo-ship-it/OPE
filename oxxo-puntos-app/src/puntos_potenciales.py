"""
Carga de la base 'Puntos_Potenciales.xlsx' (hoja MS26 de microsaturación) y
búsqueda de puntos potenciales cercanos a una coordenada dada.

Coloca el archivo en: data/Puntos_Potenciales.xlsx
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.geo_utils import buscar_cercanos

# Mismo patrón que data_loader.py: sube de src/ a la raíz del proyecto.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUNTOS_POTENCIALES_PATH = os.path.join(BASE_DIR, "data", "Puntos_Potenciales.xlsx")
HOJA_MS26 = "MS26"

# Columnas que nos interesan de la hoja MS26 (ajusta aquí si tu archivo
# tiene encabezados distintos). Se limpian espacios extra al cargar.
COLUMNAS_UTILES = [
    "# Microsaturación",
    "Fecha recepción",
    "Practicante",
    "Region",
    "UPZ",
    "Nombre PP",
    "Estado",
    "Especialista",
    "Longitud",
    "Latitud",
    "Tiendas evaluadas",
]


@st.cache_data(show_spinner=False)
def load_puntos_potenciales(path: str | Path = PUNTOS_POTENCIALES_PATH) -> pd.DataFrame:
    """
    Lee la hoja MS26 del archivo de Puntos Potenciales y devuelve un
    DataFrame limpio con columnas 'lat' y 'lon' listas para usar con
    geo_utils.buscar_cercanos.
    """
    path = Path(path)
    if not path.exists():
        # No truena la app si aún no han subido el archivo: devuelve vacío.
        return pd.DataFrame(columns=COLUMNAS_UTILES + ["lat", "lon"])

    df = pd.read_excel(path, sheet_name=HOJA_MS26)
    df.columns = [str(c).strip() for c in df.columns]

    # Nos quedamos solo con las columnas que existen realmente en el archivo
    columnas_presentes = [c for c in COLUMNAS_UTILES if c in df.columns]
    df = df[columnas_presentes].copy()

    df["lat"] = pd.to_numeric(df.get("Latitud"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("Longitud"), errors="coerce")

    if "Nombre PP" in df.columns:
        df["Nombre PP"] = df["Nombre PP"].astype(str).str.strip()

    df = df.dropna(subset=["lat", "lon"])
    return df.reset_index(drop=True)


def buscar_puntos_potenciales_cercanos(
    lat: float,
    lon: float,
    radio_m: float = 300,
    df_pp: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Busca en la base de Puntos Potenciales (microsaturación) los puntos
    dentro de `radio_m` metros de (lat, lon). Útil para saber si un punto
    evaluado en Operaciones ya se había presentado antes como microsaturación.
    """
    if df_pp is None:
        df_pp = load_puntos_potenciales()
    if df_pp.empty:
        return df_pp
    return buscar_cercanos(lat, lon, df_pp, lat_col="lat", lon_col="lon", radio_m=radio_m)
