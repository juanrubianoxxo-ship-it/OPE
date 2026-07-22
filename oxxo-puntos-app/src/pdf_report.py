"""
Genera un informe PDF de un punto evaluado (base de Operaciones):
datos principales, nombre original vs. nombre nuevo propuesto, fotos del
local y (opcionalmente) las coincidencias de nombre/radio encontradas.

Uso típico desde app.py:

    from src.pdf_report import generar_informe_pdf

    pdf_bytes = generar_informe_pdf(
        datos=fila_visita.to_dict(),
        nombre_original=seleccion,
        nombre_nuevo=nuevo_nombre_input,
        fotos=fotos,
        coincidencias=fila_match["Todas las coincidencias"],
    )
    st.download_button("Descargar informe PDF", pdf_bytes,
                        file_name=f"informe_{id_punto}.pdf",
                        mime="application/pdf")
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import pandas as pd
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)

# Campos del punto evaluado que se incluyen en el informe, en este orden.
# El primer elemento es el nombre de columna en la fila de la visita, el
# segundo es la etiqueta que se imprime.
CAMPOS_INFORME = [
    ("Nombre del Punto", "Nombre del punto (original)"),
    ("Jefe de zona", "Jefe de zona"),
    ("Región", "Región"),
    ("Plaza", "Plaza"),
    ("Dirección", "Dirección"),
    ("Segmento de tienda aproximado", "Segmento aproximado"),
    ("Tienda de local", "Tipo de local"),
    ("Principal característica de la ubicación", "Característica principal"),
    ("Contacto del Propietario (Teléfono)", "Contacto (teléfono)"),
    ("Contacto del Propietario (Correo Electronico)", "Contacto (correo)"),
    ("Estado", "Estado visita"),
    ("Estado Growth", "Estado Growth"),
    ("Comentarios", "Comentarios"),
]


def _descargar_imagen(url: str, timeout: int = 10) -> Optional[io.BytesIO]:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return io.BytesIO(resp.content)
    except Exception:
        return None


def generar_informe_pdf(
    datos: dict,
    nombre_original: str,
    fotos: Optional[list[str]] = None,
    nombre_nuevo: Optional[str] = None,
    coincidencias: Optional[list[dict]] = None,
) -> bytes:
    """
    Construye el informe en memoria y devuelve los bytes del PDF, listos
    para pasar a st.download_button.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "TituloInforme", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6
    )
    normal = styles["Normal"]

    story = []

    # ---- Encabezado -------------------------------------------------
    story.append(Paragraph("Informe de punto evaluado", titulo_style))
    story.append(
        Paragraph(
            f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            normal,
        )
    )
    story.append(Spacer(1, 10))

    # ---- Nombre original vs. nombre nuevo propuesto ------------------
    if nombre_nuevo and nombre_nuevo.strip() and nombre_nuevo.strip() != nombre_original:
        tabla_nombres = Table(
            [
                ["Nombre original", nombre_original],
                ["Nombre nuevo propuesto", nombre_nuevo.strip()],
            ],
            colWidths=[5 * cm, 10.5 * cm],
        )
        tabla_nombres.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 1), (1, 1), colors.HexColor("#fff3cd")),
                ]
            )
        )
        story.append(tabla_nombres)
        story.append(Spacer(1, 10))
    else:
        story.append(Paragraph(f"<b>Nombre del punto:</b> {nombre_original}", normal))
        story.append(Spacer(1, 10))

    # ---- Datos principales -------------------------------------------
    story.append(Paragraph("Información principal", subtitulo_style))
    filas = []
    for campo, etiqueta in CAMPOS_INFORME:
        if campo == "Nombre del Punto":
            continue  # ya se mostró arriba
        valor = datos.get(campo, "")
        if pd.isna(valor) if not isinstance(valor, str) else False:
            valor = ""
        valor = str(valor).strip() if valor is not None else ""
        if valor and valor.lower() != "nan":
            filas.append([etiqueta, valor])

    if filas:
        tabla_datos = Table(filas, colWidths=[5 * cm, 10.5 * cm])
        tabla_datos.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(tabla_datos)
    story.append(Spacer(1, 10))

    # ---- Coincidencias (nombre y/o radio) ------------------------------
    if coincidencias:
        story.append(Paragraph("Coincidencias encontradas", subtitulo_style))
        encabezado = ["Tienda / Punto", "Estado", "Score / Distancia"]
        filas_coinc = [encabezado]
        for c in coincidencias:
            nombre_c = c.get("tienda_name") or c.get("NAME") or c.get("Nombre PP") or "-"
            estado_c = c.get("estado") or c.get("ESTADO") or c.get("Estado") or "-"
            if "distancia_m" in c:
                metrica = f"{c['distancia_m']:.0f} m"
            else:
                metrica = f"{c.get('score', '-')}%"
            filas_coinc.append([str(nombre_c), str(estado_c), metrica])

        tabla_coinc = Table(filas_coinc, colWidths=[7 * cm, 4.5 * cm, 4 * cm])
        tabla_coinc.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#343a40")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(tabla_coinc)
        story.append(Spacer(1, 10))

    # ---- Fotos ----------------------------------------------------------
    if fotos:
        story.append(Paragraph("Fotos del local", subtitulo_style))
        for url in fotos:
            img_bytes = _descargar_imagen(url)
            if img_bytes is None:
                story.append(Paragraph(f"(No se pudo descargar: {url})", normal))
                continue
            try:
                img = RLImage(img_bytes, width=12 * cm, height=8 * cm, kind="proportional")
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception:
                story.append(Paragraph(f"(No se pudo insertar la imagen: {url})", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
