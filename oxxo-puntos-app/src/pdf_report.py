"""Generación del informe PDF de un punto evaluado.

El informe conserva el enlace de Maps como referencia, imprime las coordenadas
explícitas recibidas desde Operaciones y limita el apartado de cercanía a las
cinco tiendas abiertas más cercanas. Las fotografías se acomodan en una
cuadrícula de dos columnas para que el documento sea más legible.
"""
from __future__ import annotations

import html
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
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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

COLOR_ROJO = colors.HexColor("#E4032E")
COLOR_AMARILLO = colors.HexColor("#FFD200")
COLOR_GRIS_CLARO = colors.HexColor("#F6F6F6")
COLOR_GRIS_TABLA = colors.HexColor("#333333")


def _texto(valor: object) -> str:
    """Convierte un valor de Excel en texto seguro y vacío si no existe."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    return "" if texto.casefold() == "nan" else texto


def _descargar_imagen(url: str, timeout: int = 10) -> Optional[io.BytesIO]:
    """Descarga una foto de manera tolerante a errores para el informe."""
    try:
        respuesta = requests.get(url, timeout=timeout)
        respuesta.raise_for_status()
        return io.BytesIO(respuesta.content)
    except requests.RequestException:
        return None


def _tabla_estandar(filas, anchos, header: bool = False) -> Table:
    """Aplica una apariencia consistente a las tablas del informe."""
    tabla = Table(filas, colWidths=anchos, repeatRows=1 if header else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8C8C8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        estilo.extend([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS_TABLA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_GRIS_CLARO]),
        ])
    else:
        estilo.extend([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ])
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _top_cinco_tiendas(tiendas_cercanas: Optional[list[dict]]) -> list[dict]:
    """Ordena por distancia y devuelve exclusivamente las cinco tiendas más cercanas."""
    if not tiendas_cercanas:
        return []

    filas = []
    for fila in tiendas_cercanas:
        tipo = _texto(fila.get("Tipo", ""))
        # Permite tanto el formato actual de app.py como llamadas directas.
        if tipo and "tienda" not in tipo.casefold():
            continue
        try:
            distancia = float(fila.get("Distancia (m)", float("inf")))
        except (TypeError, ValueError):
            distancia = float("inf")
        if distancia != float("inf"):
            filas.append({**fila, "_distancia": distancia})

    filas.sort(key=lambda fila: fila["_distancia"])
    return filas[:5]


def _cuadricula_fotos(fotos: list[str], normal: ParagraphStyle) -> tuple[list, int]:
    """Construye una cuadrícula de dos columnas y cuenta las fotos insertadas."""
    celdas = []
    insertadas = 0
    for indice, url in enumerate(fotos, start=1):
        imagen_bytes = _descargar_imagen(url)
        if imagen_bytes is None:
            celdas.append(Paragraph(f"Foto {indice}: no disponible.", normal))
            continue
        try:
            imagen = RLImage(imagen_bytes, width=7.2 * cm, height=5.1 * cm, kind="proportional")
            celdas.append(imagen)
            insertadas += 1
        except Exception:
            celdas.append(Paragraph(f"Foto {indice}: no se pudo insertar.", normal))

    if not celdas:
        return [], 0

    filas = [celdas[i:i + 2] for i in range(0, len(celdas), 2)]
    if len(filas[-1]) == 1:
        filas[-1].append("")

    tabla = Table(filas, colWidths=[8.1 * cm, 8.1 * cm], hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
    ]))
    return [tabla], insertadas


def generar_informe_pdf(
    datos: dict,
    nombre_original: str,
    fotos: Optional[list[str]] = None,
    nombre_nuevo: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    tiendas_cercanas: Optional[list[dict]] = None,
) -> bytes:
    """Construye el informe en memoria y devuelve los bytes del PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloInforme",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=COLOR_ROJO,
        spaceAfter=5,
    )
    subtitulo = ParagraphStyle(
        "SubtituloInforme",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=COLOR_ROJO,
        spaceBefore=10,
        spaceAfter=5,
    )
    normal = ParagraphStyle(
        "NormalInforme", parent=styles["Normal"], fontSize=8.5, leading=11
    )

    story = [
        Paragraph("Informe de punto evaluado", titulo),
        Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal),
        Spacer(1, 8),
    ]

    nombre_original = _texto(nombre_original)
    nombre_nuevo = _texto(nombre_nuevo)
    if nombre_nuevo and nombre_nuevo != nombre_original:
        story.append(_tabla_estandar(
            [
                ["Nombre original", nombre_original],
                ["Nombre nuevo propuesto", nombre_nuevo],
            ],
            [5 * cm, 10.5 * cm],
        ))
    else:
        story.append(Paragraph(f"<b>Nombre del punto:</b> {html.escape(nombre_original)}", normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Información principal", subtitulo))
    filas_datos = []
    for campo, etiqueta in CAMPOS_INFORME:
        if campo == "Nombre del Punto":
            continue
        valor = _texto(datos.get(campo, ""))
        if valor:
            filas_datos.append([etiqueta, valor])
    if filas_datos:
        story.append(_tabla_estandar(filas_datos, [5 * cm, 10.5 * cm]))
    story.append(Spacer(1, 8))

    maps_link = _texto(datos.get("Enlace de la ubicación en Google Maps", ""))
    tiene_coords = lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon)
    if maps_link or tiene_coords:
        story.append(Paragraph("Ubicación", subtitulo))
        filas_ubicacion = []
        if tiene_coords:
            filas_ubicacion.append(["Coordenadas", f"{float(lat):.6f}, {float(lon):.6f}"])
        if maps_link:
            enlace = html.escape(maps_link, quote=True)
            filas_ubicacion.append(["Link de Maps", Paragraph(f'<link href="{enlace}">Abrir ubicación en Maps</link>', normal)])
        story.append(_tabla_estandar(filas_ubicacion, [5 * cm, 10.5 * cm]))
        story.append(Spacer(1, 8))

    top_tiendas = _top_cinco_tiendas(tiendas_cercanas)
    story.append(Paragraph("Top 5 tiendas abiertas más cercanas", subtitulo))
    if top_tiendas:
        filas_tiendas = [["Distancia (m)", "Tienda", "Plaza / municipio"]]
        for tienda in top_tiendas:
            filas_tiendas.append([
                f"{round(tienda['_distancia'])}",
                _texto(tienda.get("Nombre", "")),
                _texto(tienda.get("Detalle", "")),
            ])
        story.append(_tabla_estandar(filas_tiendas, [2.7 * cm, 6.6 * cm, 6.2 * cm], header=True))
    else:
        story.append(Paragraph("No se encontraron tiendas abiertas dentro del radio seleccionado.", normal))
    story.append(Spacer(1, 8))

    fotos = fotos or []
    if fotos:
        story.append(Paragraph("Fotos del local", subtitulo))
        cuadricula, insertadas = _cuadricula_fotos(fotos, normal)
        story.extend(cuadricula)
        if insertadas == 0:
            story.append(Paragraph("No fue posible descargar las fotografías disponibles.", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
