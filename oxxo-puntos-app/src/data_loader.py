"""
Carga y normalización de las dos bases de datos:
- Book.xlsx (hoja JUN): tiendas ABIERTA / OBRA / FIRMADA con coordenadas.
- Operaciones_ult_semana.xlsm (hoja Visitas_Operaciones): puntos evaluados.
"""
import os
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sube de src/ a oxxo-puntos-app/
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

# Nombre de columna "estándar" que usa el resto de la app (el filtro por
# fecha en app.py). Se llena automáticamente detectando alguna columna del
# Excel cuyo nombre contenga "fecha" (ver _find_date_column). Si tu hoja
# usa un nombre muy distinto (que no contenga la palabra "fecha"), agrégalo
# a DATE_COLUMN_HINTS.
DATE_COLUMN_STD = "Fecha"
DATE_COLUMN_HINTS = ["fecha de visita", "fecha visita", "fecha de la visita", "fecha"]


def _file_signature(path: str):
    """mtime + size, se usa como parte de la cache key para invalidar el
    cache automáticamente cuando reemplaces el Excel en el repo."""
    stat = os.stat(path)
    return (path, stat.st_mtime, stat.st_size)


def _find_date_column(df: pd.DataFrame):
    """Busca la columna de fecha en 'Visitas_Operaciones'. Prueba primero
    los nombres exactos en DATE_COLUMN_HINTS (en orden) y, si no encuentra
    ninguno, cualquier columna cuyo nombre contenga la palabra 'fecha'."""
    cols_lower = {c.lower().strip(): c for c in df.columns if isinstance(c, str)}
    for hint in DATE_COLUMN_HINTS:
        if hint in cols_lower:
            return cols_lower[hint]
    for lower, original in cols_lower.items():
        if "fecha" in lower:
            return original
    return None


@st.cache_data(show_spinner="Cargando tiendas vigentes...")
def load_tiendas(_sig=None) -> pd.DataFrame:
    sig = _file_signature(BOOK_PATH)
    df = pd.read_excel(BOOK_PATH, sheet_name="JUN")
    df.columns = [str(c).strip() for c in df.columns]
    keep = [c for c in TIENDAS_COLS if c in df.columns]
    df = df[keep].copy()

    df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()
    df = df[df["ESTADO"].isin(ESTADOS_VIGENTES)].copy()

    df["NAME"] = df["NAME"].astype(str).str.strip()
    df = df[df["NAME"].ne("") & df["NAME"].ne("0")]

    # X = longitud, Y = latitud en esta base
    df["lat"] = pd.to_numeric(df["Y"], errors="coerce")
    df["lon"] = pd.to_numeric(df["X"], errors="coerce")

    df = df.reset_index(drop=True)
    return df


@st.cache_data(show_spinner="Cargando puntos evaluados (Operaciones)...")
def load_visitas(_sig=None) -> pd.DataFrame:
    sig = _file_signature(VISITAS_PATH)
    df = pd.read_excel(
        VISITAS_PATH, sheet_name="Visitas_Operaciones", engine="openpyxl"
    )
    df.columns = [str(c) for c in df.columns]
    df = df.rename(columns=VISITAS_RENAME)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    if "Nombre del Punto" in df.columns:
        df["Nombre del Punto"] = df["Nombre del Punto"].astype(str).str.strip()
        df = df[df["Nombre del Punto"].ne("") & df["Nombre del Punto"].ne("nan")]

    # --- Columna estándar de fecha, usada por el filtro de fecha en la UI.
    fecha_col = _find_date_column(df)
    if fecha_col is not None:
        df[DATE_COLUMN_STD] = pd.to_datetime(df[fecha_col], errors="coerce")
    else:
        # No se encontró ninguna columna de fecha: se deja vacía y app.py
        # ocultará el filtro automáticamente con un aviso.
        df[DATE_COLUMN_STD] = pd.NaT

    # --- Columna ID, usada para marcar puntos como "Subido". Si ya existe
    # en el Excel se normaliza a texto; si no existe, se usa el nombre del
    # punto como identificador de respaldo.
    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(str)
    elif "Nombre del Punto" in df.columns:
        df["ID"] = df["Nombre del Punto"]
    else:
        df["ID"] = df.index.astype(str)

    df = df.reset_index(drop=True)
    return df


def reload_all():
    """Fuerza recarga (botón 'Recargar datos' en la UI)."""
    load_tiendas.clear()
    load_visitas.clear()
