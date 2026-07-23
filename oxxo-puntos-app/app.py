import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from src.data_loader import load_tiendas, load_visitas, reload_all, DATE_COLUMN_STD
from src.matching import build_match_table
from src.maps_utils import get_coordinates
from src.photos_utils import parse_photo_urls
from src.estado_subido import obtener_subidos, marcar_subido, desmarcar_subido
from src.geo_utils import buscar_cercanos
from src.puntos_potenciales import load_puntos_potenciales, buscar_puntos_potenciales_cercanos
from src.pdf_report import generar_informe_pdf

st.set_page_config(
    page_title="Puntos evaluados vs. tiendas vigentes",
    page_icon="📍",
    layout="wide",
)

# ---------------------------------------------------------- Tema OXXO -----
OXXO_ROJO = "#E4032E"
OXXO_AMARILLO = "#FFD200"
OXXO_ROJO_OSCURO = "#B4022A"
OXXO_BLANCO = "#FFFFFF"
OXXO_GRIS = "#2B2B2B"

st.markdown(
    f"""
    <style>
    /* ---------- Fondo general ---------- */
    .stApp {{
        background: linear-gradient(180deg, #fffdf5 0%, #ffffff 35%);
    }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {OXXO_ROJO} 0%, {OXXO_ROJO_OSCURO} 100%);
    }}
    section[data-testid="stSidebar"] * {{
        color: {OXXO_BLANCO} !important;
    }}
    section[data-testid="stSidebar"] .stCaption, 
    section[data-testid="stSidebar"] small {{
        color: #ffe9ec !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.35) !important;
    }}

    /* Sliders y radios dentro del sidebar */
    section[data-testid="stSidebar"] [data-baseweb="slider"] div[role="slider"] {{
        background-color: {OXXO_AMARILLO} !important;
        border: 2px solid {OXXO_BLANCO} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stTickBar"] {{
        display: none;
    }}

    /* ---------- Títulos ---------- */
    h1 {{
        color: {OXXO_ROJO_OSCURO} !important;
        font-weight: 800 !important;
        border-bottom: 4px solid {OXXO_AMARILLO};
        padding-bottom: 8px;
        display: inline-block;
    }}
    h2, h3 {{
        color: {OXXO_ROJO} !important;
        font-weight: 700 !important;
    }}

    /* ---------- Botones ---------- */
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {{
        background: linear-gradient(135deg, {OXXO_AMARILLO} 0%, #ffc400 100%) !important;
        color: {OXXO_GRIS} !important;
        font-weight: 700 !important;
        border: 2px solid {OXXO_ROJO} !important;
        border-radius: 10px !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        box-shadow: 0 2px 6px rgba(228,3,46,0.25) !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {{
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 14px rgba(228,3,46,0.35) !important;
        background: linear-gradient(135deg, {OXXO_ROJO} 0%, {OXXO_ROJO_OSCURO} 100%) !important;
        color: {OXXO_BLANCO} !important;
        border: 2px solid {OXXO_AMARILLO} !important;
    }}

    /* ---------- Métricas (tarjetas) ---------- */
    div[data-testid="stMetric"] {{
        background: {OXXO_BLANCO};
        border: 2px solid {OXXO_AMARILLO};
        border-left: 8px solid {OXXO_ROJO};
        border-radius: 12px;
        padding: 14px 16px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        transition: transform 0.15s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 18px rgba(228,3,46,0.18);
    }}
    div[data-testid="stMetricLabel"] {{
        color: {OXXO_ROJO_OSCURO} !important;
        font-weight: 700 !important;
    }}

    /* ---------- Radios (Vista) ---------- */
    section[data-testid="stSidebar"] div[role="radiogroup"] label {{
        background: rgba(255,255,255,0.12);
        border-radius: 8px;
        padding: 6px 10px;
        margin-bottom: 4px;
        transition: background 0.15s ease;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background: rgba(255,210,0,0.3);
    }}

    /* ---------- Tablas / DataFrames ---------- */
    div[data-testid="stDataFrame"] {{
        border: 2px solid {OXXO_AMARILLO};
        border-radius: 10px;
        overflow: hidden;
    }}

    /* ---------- Alertas ---------- */
    div[data-testid="stAlert"] {{
        border-radius: 10px;
        border-left-width: 6px !important;
    }}

    /* ---------- Checkbox / inputs de texto ---------- */
    .stTextInput > div > div > input {{
        border: 2px solid {OXXO_AMARILLO} !important;
        border-radius: 8px !important;
    }}
    .stTextInput > div > div > input:focus {{
        border: 2px solid {OXXO_ROJO} !important;
        box-shadow: 0 0 0 2px rgba(228,3,46,0.15) !important;
    }}

    /* ---------- Selectbox ---------- */
    div[data-baseweb="select"] > div {{
        border: 2px solid {OXXO_AMARILLO} !important;
        border-radius: 8px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- Sidebar --
with st.sidebar:
    st.title("📍 Panel de control")

    if st.button("🔄 Recargar datos (Excel del repo)", use_container_width=True):
        reload_all()
        load_puntos_potenciales.clear()
        st.rerun()

    st.caption(
        "Los datos se leen de `data/Book.xlsx`, "
        "`data/Operaciones_ult_semana.xlsm` y `data/Puntos_Potenciales.xlsx`. "
        "Para actualizarlos, reemplaza esos archivos en el repositorio de "
        "GitHub y presiona Recargar."
    )

    st.divider()
    threshold = st.slider(
        "Umbral de similitud para marcar posible duplicado",
        min_value=50, max_value=100, value=80, step=1,
    )
    top_n = st.slider("Coincidencias a mostrar por punto", 1, 5, 3)

    st.divider()
    radio_cercania_m = st.slider(
        "Radio de cercanía (metros) para tiendas abiertas",
        min_value=50, max_value=1000, value=300, step=25,
    )
    st.caption(
        "Este radio solo aplica a la tabla de cercanía de **tiendas "
        "abiertas**. En el mapa se muestran **todos** los puntos "
        "potenciales, sin importar la distancia."
    )

    st.divider()
    page = st.radio(
        "Vista",
        ["🔍 Comparación de nombres", "🗂️ Detalle por punto"],
        label_visibility="collapsed",
    )

# ------------------------------------------------------------------ Data --
try:
    tiendas = load_tiendas()
    visitas_full = load_visitas()
except FileNotFoundError as e:
    st.error(
        "No encuentro los archivos de datos. Verifica que "
        "`data/Book.xlsx` y `data/Operaciones_ult_semana.xlsm` "
        f"estén en el repo.\n\nDetalle: {e}"
    )
    st.stop()

puntos_potenciales = load_puntos_potenciales()

if visitas_full.empty:
    st.warning("La hoja 'Visitas_Operaciones' no tiene puntos para analizar.")
    st.stop()

subidos_ids = obtener_subidos()

# --------------------------------------------- Filtros nuevos (sidebar) ---
with st.sidebar:
    st.divider()
    st.subheader("📅 Filtro por fecha")

    tiene_fechas = visitas_full[DATE_COLUMN_STD].notna().any()
    rango_fecha = None
    if tiene_fechas:
        fecha_min = visitas_full[DATE_COLUMN_STD].min().date()
        fecha_max = visitas_full[DATE_COLUMN_STD].max().date()
        rango_fecha = st.date_input(
            "Ver puntos evaluados entre estas fechas",
            value=(fecha_min, fecha_max),
            min_value=fecha_min,
            max_value=fecha_max,
        )
    else:
        st.caption(
            "No se detectó una columna de fecha en 'Visitas_Operaciones' "
            "(busco alguna columna cuyo nombre contenga 'fecha')."
        )

    st.divider()
    mostrar_subidos = st.checkbox(
        "Mostrar también los puntos ya marcados como 'Subido'",
        value=False,
    )

    if puntos_potenciales.empty:
        st.caption(
            "⚠️ No encontré `data/Puntos_Potenciales.xlsx` (o la hoja "
            "'MS26' vino vacía). Súbelo al repo para activar los puntos "
            "potenciales en el mapa."
        )

# ---------------------------------------------------- Aplicar filtros -----
visitas = visitas_full.copy()

n_sin_fecha_excluidos = 0
if rango_fecha and isinstance(rango_fecha, tuple) and len(rango_fecha) == 2:
    inicio, fin = rango_fecha
    con_fecha = visitas[DATE_COLUMN_STD].notna()
    en_rango = (visitas[DATE_COLUMN_STD].dt.date >= inicio) & (visitas[DATE_COLUMN_STD].dt.date <= fin)
    n_sin_fecha_excluidos = int((~con_fecha).sum())
    visitas = visitas[con_fecha & en_rango]

n_subidos_ocultos = 0
if not mostrar_subidos:
    n_subidos_ocultos = int(visitas["ID"].isin(subidos_ids).sum())
    visitas = visitas[~visitas["ID"].isin(subidos_ids)]

if visitas.empty:
    st.warning("No hay puntos evaluados que cumplan con los filtros seleccionados.")
    st.stop()

match_table = build_match_table(visitas, tiendas, threshold=threshold, top_n=top_n)
match_table["ID"] = match_table["ID"].astype(str)
match_table["Subido"] = match_table["ID"].isin(subidos_ids)

# ============================================================== PAGE 1 ====
if page == "🔍 Comparación de nombres":
    st.title("Comparación: puntos evaluados vs. tiendas vigentes")
    st.caption(
        f"{len(visitas)} puntos evaluados · {len(tiendas)} tiendas "
        "ABIERTA / OBRA / FIRMADA en la base."
    )
    if n_sin_fecha_excluidos:
        st.caption(
            f"⚠️ {n_sin_fecha_excluidos} punto(s) sin fecha registrada se "
            "excluyeron por el filtro de fecha."
        )
    if n_subidos_ocultos:
        st.caption(
            f"👁️ {n_subidos_ocultos} punto(s) ya marcados como 'Subido' "
            "están ocultos (activa la casilla en la barra lateral para verlos)."
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Puntos evaluados", len(match_table))
    c2.metric(
        "Posibles duplicados",
        int(match_table["Posible duplicado"].sum()),
    )
    c3.metric(
        "Sin coincidencia relevante",
        int((match_table["Score"] < threshold).sum()),
    )

    solo_alertas = st.checkbox("Mostrar solo posibles duplicados", value=False)
    tabla = match_table[match_table["Posible duplicado"]] if solo_alertas else match_table

    def resaltar(row):
        color = "background-color: #ffe1e1" if row["Posible duplicado"] else ""
        return [color] * len(row)

    cols_mostrar = [
        "ID", "Nombre del Punto", "Jefe de zona", "Región", "Plaza",
        "Estado visita", "Mejor coincidencia", "Estado tienda", "Score",
        "Posible duplicado", "Subido",
    ]
    st.dataframe(
        tabla[cols_mostrar].style.apply(resaltar, axis=1),
        use_container_width=True,
        hide_index=True,
        height=550,
    )

    st.caption(
        "El **Score** va de 0 a 100 (similitud de texto entre nombres, "
        "algoritmo WRatio). Ajusta el umbral en la barra lateral. Para ver "
        "el detalle completo de un punto (fotos, contacto, mapa, cercanía "
        "y descargar el informe en PDF) ve a la pestaña **Detalle por punto**."
    )

# ============================================================== PAGE 2 ====
else:
    st.title("Detalle del punto evaluado")

    nombres = match_table["Nombre del Punto"].tolist()
    if not nombres:
        st.info("No hay puntos que cumplan con los filtros seleccionados.")
        st.stop()

    seleccion = st.selectbox("Selecciona un punto evaluado", nombres)

    fila_match = match_table[match_table["Nombre del Punto"] == seleccion].iloc[0]
    fila_visita = visitas[visitas["Nombre del Punto"] == seleccion].iloc[0]
    id_punto = str(fila_visita.get("ID", ""))
    ya_subido = id_punto in subidos_ids

    col_estado, col_boton = st.columns([3, 1])
    with col_estado:
        if ya_subido:
            st.success("✅ Este punto ya está marcado como **Subido**.")
        else:
            st.info("Este punto todavía no se ha marcado como Subido.")
    with col_boton:
        if ya_subido:
            if st.button("↩️ Desmarcar", use_container_width=True):
                desmarcar_subido(id_punto)
                st.rerun()
        else:
            if st.button("📤 Marcar como Subido", use_container_width=True):
                marcar_subido(id_punto)
                st.rerun()

    if fila_match["Posible duplicado"]:
        st.error(
            f"⚠️ Posible duplicado — coincide en un {fila_match['Score']}% "
            f"con **{fila_match['Mejor coincidencia']}** "
            f"({fila_match['Estado tienda']})."
        )

    # -------------------------------------------- Nombre nuevo propuesto --
    st.subheader("✏️ Renombrar (opcional)")
    nuevo_nombre = st.text_input(
        "Si vas a subir este punto con otro nombre, escríbelo aquí. "
        "El informe en PDF imprimirá el nombre original y este nombre nuevo.",
        value="",
        placeholder=f"Nombre actual: {seleccion}",
        key=f"nuevo_nombre_{id_punto}",
    )

    col_info, col_foto = st.columns([1.1, 1])

    with col_info:
        st.subheader("Información principal")
        st.markdown(f"**Nombre del punto:** {fila_visita.get('Nombre del Punto', '')}")
        st.markdown(f"**Jefe de zona:** {fila_visita.get('Jefe de zona', '')}")
        st.markdown(f"**Región / Plaza:** {fila_visita.get('Región', '')} / {fila_visita.get('Plaza', '')}")
        st.markdown(f"**Dirección:** {fila_visita.get('Dirección', '')}")
        st.markdown(f"**Segmento aproximado:** {fila_visita.get('Segmento de tienda aproximado', '')}")
        st.markdown(f"**Tipo de local:** {fila_visita.get('Tienda de local', '')}")
        st.markdown(f"**Característica principal:** {fila_visita.get('Principal característica de la ubicación', '')}")
        st.markdown(f"**Contacto propietario (tel):** {fila_visita.get('Contacto del Propietario (Teléfono)', '')}")
        st.markdown(f"**Contacto propietario (correo):** {fila_visita.get('Contacto del Propietario (Correo Electronico)', '')}")
        st.markdown(f"**Estado visita:** {fila_visita.get('Estado', '')}")
        st.markdown(f"**Estado Growth:** {fila_visita.get('Estado Growth', '')}")
        fecha_val = fila_visita.get(DATE_COLUMN_STD)
        if pd.notna(fecha_val):
            st.markdown(f"**Fecha:** {fecha_val.strftime('%Y-%m-%d')}")
        if pd.notna(fila_visita.get("Comentarios")):
            st.markdown(f"**Comentarios:** {fila_visita.get('Comentarios', '')}")

        maps_link = fila_visita.get("Enlace de la ubicación en Google Maps", "")
        if isinstance(maps_link, str) and maps_link.strip():
            st.link_button("🗺️ Abrir en Google/Bing Maps", maps_link.strip())

    with col_foto:
        st.subheader("Fotos del local")
        fotos = parse_photo_urls(fila_visita.get("Fotos del Local Revisado", ""))
        if fotos:
            for url in fotos:
                st.image(url, use_container_width=True)
        else:
            st.info("Este punto no tiene fotos cargadas.")

    st.divider()
    st.subheader("Ubicación en el mapa")
    st.caption("Haz clic en cualquier punto del mapa para ver su información.")

    direccion = fila_visita.get("Dirección", "")
    lat, lon, fuente = get_coordinates(maps_link, direccion)

    tiendas_cercanas = pd.DataFrame()
    puntos_potenciales_cercanos = pd.DataFrame()

    if lat is not None:
        st.caption(f"Coordenadas obtenidas — {fuente} · lat: {lat:.6f}, lon: {lon:.6f}")

        m = folium.Map(location=[lat, lon], zoom_start=15)

        # ---- Punto evaluado (el que estás revisando) --------------------
        popup_evaluado = folium.Popup(
            f"<b>📍 {seleccion}</b><br>"
            f"Jefe de zona: {fila_visita.get('Jefe de zona', '')}<br>"
            f"Estado visita: {fila_visita.get('Estado', '')}<br>"
            f"Dirección: {fila_visita.get('Dirección', '')}",
            max_width=300,
        )
        folium.Marker(
            [lat, lon],
            popup=popup_evaluado,
            icon=folium.Icon(color="blue", icon="star"),
        ).add_to(m)

        # -------------------------------------- Tiendas cercanas (radio) --
        # `tiendas` (load_tiendas) ya viene filtrada a ABIERTA/OBRA/FIRMADA;
        # aquí nos quedamos solo con ABIERTA, que es lo que pediste.
        tiendas_abiertas = tiendas[tiendas["ESTADO"] == "ABIERTA"]
        tiendas_cercanas = buscar_cercanos(
            lat, lon, tiendas_abiertas, lat_col="lat", lon_col="lon", radio_m=radio_cercania_m
        )
        for _, t in tiendas_cercanas.iterrows():
            popup_tienda = folium.Popup(
                f"<b>🟠 {t.get('NAME', '')}</b><br>"
                f"Estado: {t.get('ESTADO', '')}<br>"
                f"Plaza 2026: {t.get('PLAZA 2026', '')}<br>"
                f"Municipio: {t.get('MUNICIPIO', '')}<br>"
                f"Distancia: {round(t.get('distancia_m', 0))} m",
                max_width=300,
            )
            folium.Marker(
                [t["lat"], t["lon"]],
                popup=popup_tienda,
                icon=folium.Icon(color="orange", icon="shopping-cart"),
            ).add_to(m)

        # ------------------------- TODOS los puntos potenciales (sin radio) --
        if not puntos_potenciales.empty:
            for _, p in puntos_potenciales.iterrows():
                if pd.isna(p.get("lat")) or pd.isna(p.get("lon")):
                    continue
                popup_pp = folium.Popup(
                    f"<b>🟣 {p.get('Nombre PP', '')}</b><br>"
                    f"Estado: {p.get('Estado', '')}<br>"
                    f"Región: {p.get('Region', '')}<br>"
                    f"UPZ: {p.get('UPZ', '')}<br>"
                    f"Riesgo: {p.get('Riesgo', '')}",
                    max_width=300,
                )
                folium.Marker(
                    [p["lat"], p["lon"]],
                    popup=popup_pp,
                    icon=folium.Icon(color="purple", icon="flag"),
                ).add_to(m)

            # Para la tabla de cercanía (texto) sí seguimos usando el radio
            puntos_potenciales_cercanos = buscar_puntos_potenciales_cercanos(
                lat, lon, radio_m=radio_cercania_m, df_pp=puntos_potenciales
            )

        st.caption(
            "🔵 Punto evaluado · 🟠 Tiendas abiertas cercanas "
            f"(radio {radio_cercania_m} m) · 🟣 Todos los puntos "
            "potenciales — haz clic en cualquiera para ver el detalle."
        )
        st_folium(m, use_container_width=True, height=480, returned_objects=[])
    else:
        st.warning(f"No se pudo ubicar el punto en el mapa. Motivo: {fuente}")

    # ------------------------------------- Resultados de cercanía (texto) --
    st.divider()
    st.subheader(f"📡 Cercanía en un radio de {radio_cercania_m} m")
    st.caption(
        "Esto es solo por distancia (no por parecido de nombre): tiendas ya "
        "ABIERTAS y puntos que ya se habían presentado antes como "
        "microsaturación (Puntos Potenciales), sin importar cómo se llamen."
    )

    filas_cercania = []
    for _, t in tiendas_cercanas.iterrows():
        filas_cercania.append({
            "Distancia (m)": round(t["distancia_m"]),
            "Tipo": "🟠 Tienda abierta",
            "Nombre": t.get("NAME", ""),
            "Detalle": f"{t.get('PLAZA 2026', '')} · {t.get('MUNICIPIO', '')}",
        })
    for _, p in puntos_potenciales_cercanos.iterrows():
        filas_cercania.append({
            "Distancia (m)": round(p["distancia_m"]),
            "Tipo": "🟣 Punto potencial",
            "Nombre": p.get("Nombre PP", ""),
            "Detalle": f"{p.get('Estado', '')} · {p.get('Region', '')} / {p.get('UPZ', '')}",
        })

    if filas_cercania:
        tabla_cercania = pd.DataFrame(filas_cercania).sort_values("Distancia (m)").reset_index(drop=True)
        st.dataframe(tabla_cercania, hide_index=True, use_container_width=True)
    else:
        st.caption("No hay tiendas abiertas ni puntos potenciales dentro del radio.")

    st.divider()
    st.subheader("Coincidencias de nombre encontradas")
    st.caption("Esta comparación es solo por similitud de texto contra tiendas vigentes (no aplica a Puntos Potenciales).")
    if fila_match["Todas las coincidencias"]:
        st.dataframe(
            pd.DataFrame(fila_match["Todas las coincidencias"])[
                ["tienda_name", "estado", "plaza", "municipio", "score"]
            ].rename(columns={
                "tienda_name": "Tienda", "estado": "Estado",
                "plaza": "Plaza 2026", "municipio": "Municipio", "score": "Score",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No se encontraron tiendas con nombre parecido.")

    # -------------------------------------------------- Descargar informe --
    st.divider()
    st.subheader("📄 Informe del punto")

    pdf_bytes = generar_informe_pdf(
        datos=fila_visita.to_dict(),
        nombre_original=seleccion,
        nombre_nuevo=nuevo_nombre,
        fotos=fotos,
        lat=lat,
        lon=lon,
        cercania=filas_cercania,
    )
    st.download_button(
        "⬇️ Descargar informe en PDF",
        data=pdf_bytes,
        file_name=f"informe_punto_{id_punto or seleccion}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
