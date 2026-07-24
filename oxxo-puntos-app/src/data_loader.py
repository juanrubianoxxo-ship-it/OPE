"""
Carga y normalización de las bases de datos de la aplicación.

- ``Book.xlsx`` (hoja ``JUN``): tiendas vigentes con coordenadas X/Y.
- ``Operaciones_ult_semana.xlsm`` (hoja ``Visitas_Operaciones``): puntos
  evaluados. Para el mapa se usan exclusivamente columnas explícitas de
  latitud y longitud de esta hoja; el enlace de Maps se conserva como
  referencia, pero no se utiliza para obtener la ubicación.
"""
from __future__ import annotations

import os
from typing import Iterable

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_PATH = os.path.join(BASE_DIR, "data", "Book.xlsx")
VISITAS_PATH = os.path.join(BASE_DIR, "data", "Operaciones_ult_semana.xlsm")

ESTADOS_VIGENTES = ["ABIERTA", "OBRA", "FIRMADA"]

TIENDAS_COLS = [
    "NAME", "ESTADO", "PLAZA 2026", "DEPARTAMENTO", "MUNICIPIO",
    "UPZ/COMUNA", "ESTRATO", "TIPO DE LOCAL", "AREA", "X", "Y",
    "FECHA APE", "ARRENDADOR",
]

VISITAS_RENAME = {
    "Nombre del Punto ": "Nombre del Punto",
    " TICKET U6M": "TICKET U6M",
    " VENTAS OUM": "VENTAS OUM",
    " CONTRIBUCION UM": "CONTRIBUCION UM",
    " CONTRIBUCION U6M": "CONTRIBUCION U6M",
    " RENTA UM": "RENTA UM",
}

# Nombre de columna estándar para el filtro de fecha de la interfaz.
DATE_COLUMN_STD = "Fecha"
DATE_COLUMN_HINTS = ["fecha de visita", "fecha visita", "fecha de la visita", "fecha"]

# Se aceptan encabezados frecuentes, pero solo pares explícitos de coordenadas.
# No se consulta ni se resuelve el enlace de Google Maps para ubicar el punto.
LATITUDE_COLUMN_HINTS = (
    "latitud", "latitude", "lat", "y",
    "coordenada latitud", "coordenadas latitud", "coordenada y", "coordenadas y",
    "latitud gps", "latitud ubicacion", "latitud de la ubicacion",
)
LONGITUDE_COLUMN_HINTS = (
    "longitud", "longitude", "lon", "lng", "x",
    "coordenada longitud", "coordenadas longitud", "coordenada x", "coordenadas x",
    "longitud gps", "longitud ubicacion", "longitud de la ubicacion",
)


def _file_signature(path: str):
    """mtime + size para invalidar el caché cuando se reemplaza un Excel."""
    stat = os.stat(path)
    return (path, stat.st_mtime, stat.st_size)


def _find_date_column(df: pd.DataFrame):
    """Encuentra una columna de fecha en ``Visitas_Operaciones``."""
    cols_lower = {c.lower().strip(): c for c in df.columns if isinstance(c, str)}
    for hint in DATE_COLUMN_HINTS:
        if hint in cols_lower:
            return cols_lower[hint]
    for lower, original in cols_lower.items():
        if "fecha" in lower:
            return original
    return None


def _normalizar_encabezado(value: object) -> str:
    """Normaliza un encabezado para comparar variantes de escritura."""
    return "".join(str(value).casefold().strip().replace("_", " ").split())


def _find_coordinate_column(df: pd.DataFrame, hints: Iterable[str]):
    """Devuelve el encabezado real que coincide con alguna variante válida."""
    by_normalized = {
        _normalizar_encabezado(column): column
        for column in df.columns
        if isinstance(column, str)
    }
    for hint in hints:
        result = by_normalized.get(_normalizar_encabezado(hint))
        if result is not None:
            return result
    return None


def _to_coordinate(series: pd.Series) -> pd.Series:
    """Convierte coordenadas a número y admite coma decimal cuando aplique."""
    cleaned = series.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _add_visit_coordinates(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """
    Agrega las columnas normalizadas ``lat`` y ``lon``.
    Prioridad:
    1. Columnas explícitas de coordenadas en la base.
    2. Extracción desde el enlace de Google Maps.
    """
    import re
    def _extract_from_maps(url):
        if not isinstance(url, str) or not url.strip():
            return None, None
        match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        match = re.search(r'/@(-?\d+\.\d+),(-?\d+\.\d+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        match = re.search(r'!1d(-?\d+\.\d+)!2d(-?\d+\.\d+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        match = re.search(r'!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None

    lat_source = _find_coordinate_column(df, LATITUDE_COLUMN_HINTS)
    lon_source = _find_coordinate_column(df, LONGITUDE_COLUMN_HINTS)

    df["lat"] = pd.Series(float("nan"), index=df.index, dtype="float64")
    df["lon"] = pd.Series(float("nan"), index=df.index, dtype="float64")

    if lat_source is not None and lon_source is not None:
        df["lat"] = _to_coordinate(df[lat_source])
        df["lon"] = _to_coordinate(df[lon_source])
    else:
        # Buscar columna de Maps
        maps_col = None
        for col in df.columns:
            if isinstance(col, str) and ("maps" in col.lower() or "ubicación" in col.lower()):
                maps_col = col
                break
        
        if maps_col:
            for idx, row in df.iterrows():
                lat, lon = _extract_from_maps(row[maps_col])
                if lat is not None and lon is not None:
                    df.at[idx, "lat"] = lat
                    df.at[idx, "lon"] = lon

    valid = df["lat"].between(-90, 90) & df["lon"].between(-180, 180)
    df.loc[~valid, ["lat", "lon"]] = float("nan")
    return lat_source, lon_source


@st.cache_data(show_spinner="Cargando tiendas vigentes...")
def load_tiendas(_sig=None) -> pd.DataFrame:
    _file_signature(BOOK_PATH)
    df = pd.read_excel(BOOK_PATH, sheet_name="JUN")
    df.columns = [str(c).strip() for c in df.columns]
    keep = [c for c in TIENDAS_COLS if c in df.columns]
    df = df[keep].copy()

    df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()
    df = df[df["ESTADO"].isin(ESTADOS_VIGENTES)].copy()

    df["NAME"] = df["NAME"].astype(str).str.strip()
    df = df[df["NAME"].ne("") & df["NAME"].ne("0")]

    # X = longitud, Y = latitud en la base de tiendas.
    df["lat"] = pd.to_numeric(df["Y"], errors="coerce")
    df["lon"] = pd.to_numeric(df["X"], errors="coerce")
    return df.reset_index(drop=True)


@st.cache_data(show_spinner="Cargando puntos evaluados (Operaciones)...")
def load_visitas(_sig=None) -> pd.DataFrame:
    """Carga Operaciones y deja ``lat``/``lon`` listos si la base los trae."""
    _file_signature(VISITAS_PATH)
    df = pd.read_excel(
        VISITAS_PATH, sheet_name="Visitas_Operaciones", engine="openpyxl"
    )
    df.columns = [str(c) for c in df.columns]
    df = df.rename(columns=VISITAS_RENAME)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    if "Nombre del Punto" in df.columns:
        df["Nombre del Punto"] = df["Nombre del Punto"].astype(str).str.strip()
        df = df[df["Nombre del Punto"].ne("") & df["Nombre del Punto"].ne("nan")]

    fecha_col = _find_date_column(df)
    if fecha_col is not None:
        df[DATE_COLUMN_STD] = pd.to_datetime(
            df[fecha_col], errors="coerce", dayfirst=True
        )
    else:
        df[DATE_COLUMN_STD] = pd.NaT

    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(str)
    elif "Nombre del Punto" in df.columns:
        df["ID"] = df["Nombre del Punto"]
    else:
        df["ID"] = df.index.astype(str)

    lat_source, lon_source = _add_visit_coordinates(df)
    df.attrs["coordinate_sources"] = {"latitud": lat_source, "longitud": lon_source}
    return df.reset_index(drop=True)


def reload_all():
    """Fuerza la recarga de los Excel desde la interfaz."""
    load_tiendas.clear()
    load_visitas.clear()
