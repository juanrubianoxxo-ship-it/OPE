"""
Carga y normalización de las dos bases de datos:
- Book.xlsx (hoja JUN): tiendas ABIERTA / OBRA / FIRMADA con coordenadas.
- Operaciones_ult_semana.xlsm (hoja Visitas_Operaciones): puntos evaluados.
"""
import os
import pandas as pd
import streamlit as st

BOOK_PATH = os.path.join("data", "Book.xlsx")
VISITAS_PATH = os.path.join("data", "Operaciones_ult_semana.xlsm")

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


def _file_signature(path: str):
    """mtime + size, se usa como parte de la cache key para invalidar el
    cache automáticamente cuando reemplaces el Excel en el repo."""
    stat = os.stat(path)
    return (path, stat.st_mtime, stat.st_size)


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

    df = df.reset_index(drop=True)
    return df


def reload_all():
    """Fuerza recarga (botón 'Recargar datos' en la UI)."""
    load_tiendas.clear()
    load_visitas.clear()
