import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from src.data_loader import load_tiendas, load_visitas, reload_all
from src.matching import build_match_table
from src.maps_utils import get_coordinates
from src.photos_utils import parse_photo_urls

st.set_page_config(
    page_title="Puntos evaluados vs. tiendas vigentes",
    page_icon="📍",
    layout="wide",
)

# ---------------------------------------------------------------- Sidebar --
with st.sidebar:
    st.title("📍 Panel de control")

    if st.button("🔄 Recargar datos (Excel del repo)", use_container_width=True):
        reload_all()
        st.rerun()

    st.caption(
        "Los datos se leen de `data/Book.xlsx` y "
        "`data/Operaciones_ult_semana.xlsm`. Para actualizarlos, reemplaza "
        "esos archivos en el repositorio de GitHub y presiona Recargar."
    )

    st.divider()
    threshold = st.slider(
        "Umbral de similitud para marcar posible duplicado",
        min_value=50, max_value=100, value=80, step=1,
    )
    top_n = st.slider("Coincidencias a mostrar por punto", 1, 5, 3)

    st.divider()
    page = st.radio(
        "Vista",
        ["🔍 Comparación de nombres", "🗂️ Detalle por punto"],
        label_visibility="collapsed",
    )

# ------------------------------------------------------------------ Data --
try:
    tiendas = load_tiendas()
    visitas = load_visitas()
except FileNotFoundError as e:
    st.error(
        "No encuentro los archivos de datos. Verifica que "
        "`data/Book.xlsx` y `data/Operaciones_ult_semana.xlsm` "
        f"estén en el repo.\n\nDetalle: {e}"
    )
    st.stop()

if visitas.empty:
    st.warning("La hoja 'Visitas_Operaciones' no tiene puntos para analizar.")
    st.stop()

match_table = build_match_table(visitas, tiendas, threshold=threshold, top_n=top_n)

# ============================================================== PAGE 1 ====
if page == "🔍 Comparación de nombres":
    st.title("Comparación: puntos evaluados vs. tiendas vigentes")
    st.caption(
        f"{len(visitas)} puntos evaluados · {len(tiendas)} tiendas "
        "ABIERTA / OBRA / FIRMADA en la base."
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
        "Posible duplicado",
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
        "el detalle completo de un punto (fotos, contacto, mapa), ve a la "
        "pestaña **Detalle por punto**."
    )

# ============================================================== PAGE 2 ====
else:
    st.title("Detalle del punto evaluado")

    nombres = match_table["Nombre del Punto"].tolist()
    seleccion = st.selectbox("Selecciona un punto evaluado", nombres)

    fila_match = match_table[match_table["Nombre del Punto"] == seleccion].iloc[0]
    fila_visita = visitas[visitas["Nombre del Punto"] == seleccion].iloc[0]

    if fila_match["Posible duplicado"]:
        st.error(
            f"⚠️ Posible duplicado — coincide en un {fila_match['Score']}% "
            f"con **{fila_match['Mejor coincidencia']}** "
            f"({fila_match['Estado tienda']})."
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

    direccion = fila_visita.get("Dirección", "")
    lat, lon, fuente = get_coordinates(maps_link, direccion)

    if lat is not None:
        st.caption(f"Coordenadas obtenidas — {fuente} · lat: {lat:.6f}, lon: {lon:.6f}")

        m = folium.Map(location=[lat, lon], zoom_start=15)
        folium.Marker(
            [lat, lon],
            tooltip=seleccion,
            popup=seleccion,
            icon=folium.Icon(color="blue", icon="star"),
        ).add_to(m)

        # Muestra también las tiendas vigentes coincidentes cerca, para
        # comparar visualmente si de verdad es el mismo punto.
        for coincidencia in fila_match["Todas las coincidencias"]:
            if pd.notna(coincidencia.get("lat")) and pd.notna(coincidencia.get("lon")):
                folium.Marker(
                    [coincidencia["lat"], coincidencia["lon"]],
                    tooltip=f"{coincidencia['tienda_name']} ({coincidencia['estado']}) · {coincidencia['score']}%",
                    icon=folium.Icon(
                        color="red" if coincidencia["score"] >= threshold else "gray",
                        icon="shopping-cart",
                    ),
                ).add_to(m)

        st_folium(m, use_container_width=True, height=450, returned_objects=[])
    else:
        st.warning(f"No se pudo ubicar el punto en el mapa. Motivo: {fuente}")

    st.divider()
    st.subheader("Coincidencias de nombre encontradas")
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
