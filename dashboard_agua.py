# ====================================================
# STREAMLIT: Redistribución de agua en emergencias
# Doctorado en Ciencias Ambientales - UNMSM
# Autor: Mg. Ing. Joel Cruz Machacuay
# ====================================================

import streamlit as st

# --- LOGIN SIMPLE ---
USERS = {"jurado1": "clave123", "jurado2": "clave456"}

if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔐 Acceso restringido")
    user = st.text_input("Usuario")
    pw = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user in USERS and USERS[user] == pw:
            st.session_state["auth"] = True
            st.success("Acceso permitido")
        else:
            st.error("Credenciales inválidas")
    st.stop()

# --- DESCARGA AUTOMÁTICA DE DATOS ---
import os
import gdown
import zipfile

# Ruta de datos
data_dir = "Datos_qgis"
os.makedirs(data_dir, exist_ok=True)

# URL de Google Drive (archivo ZIP de tus datos GIS)
url = "https://drive.google.com/uc?id=1N6mHSt-dKX8csuCcIlB2J6xTGaA_P1ax"
output = os.path.join(data_dir, "Datos_qgis.zip")

# Descargar y descomprimir solo si no existe ya
if not os.path.exists(output):
    st.info("📥 Descargando datos desde Google Drive, espera un momento...")
    gdown.download(url, output, quiet=False)

    with zipfile.ZipFile(output, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    st.success("✅ Datos descargados y listos.")

# --- LIBRERÍAS ---
import pandas as pd
import geopandas as gpd
import folium
from shapely.ops import unary_union
from streamlit_folium import st_folium
import plotly.express as px

# --- CONFIG CISERNAS ---
cisternas = {
    "19 m³": {"capacidad": 19, "costo_fijo": 350, "costo_km": 6, "consumo_km": 0.5},  
    "34 m³": {"capacidad": 34, "costo_fijo": 500, "costo_km": 8, "consumo_km": 0.8}   
}

# ========= FUNCIONES =========
def normalizar(x):
    return str(x).strip().upper().replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")

def calcular_costos(aporte, dist_km, tipo_cisterna):
    cfg = cisternas[tipo_cisterna]
    cap = cfg["capacidad"]
    viajes = int(aporte // cap + (aporte % cap > 0))
    costo = viajes * (cfg["costo_fijo"] + cfg["costo_km"] * dist_km)
    consumo = viajes * cfg["consumo_km"] * dist_km  
    return viajes, costo, consumo

def asignar_pozos(geom_obj, demanda, escenario, tipo_cisterna, pozos_gdf):
    resultados = []
    restante = demanda
    total_viajes, total_costo, total_consumo = 0, 0, 0

    pozos_tmp = []
    for _, pozo in pozos_gdf.iterrows():
        try:
            q_m3_dia = float(pozo["Q_m3_dia"])
        except:
            q_m3_dia = 0
        if q_m3_dia > 0:
            dist_km = pozo.geometry.distance(geom_obj) * 111
            aporte_disp = q_m3_dia * (escenario / 100)
            pozos_tmp.append((dist_km, pozo["ID"], aporte_disp, pozo.geometry))

    pozos_tmp.sort(key=lambda x: x[0])

    for dist_km, pozo_id, aporte_disp, geom in pozos_tmp:
        if restante <= 0:
            break
        aporte_asignado = min(aporte_disp, restante)
        viajes, costo, consumo = calcular_costos(aporte_asignado, dist_km, tipo_cisterna)
        resultados.append([pozo_id, aporte_asignado, viajes, costo, consumo, round(dist_km, 3), geom])
        restante -= aporte_asignado
        total_viajes += viajes
        total_costo += costo
        total_consumo += consumo

    return resultados, restante, total_viajes, total_costo, total_consumo

# ========= CARGA DE DATOS =========
sectores_gdf = gpd.read_file(os.path.join(data_dir, "Sectores_F1_ENFEN.shp")).to_crs(epsg=4326)
distritos_gdf = gpd.read_file(os.path.join(data_dir, "DISTRITOS_Final.shp")).to_crs(epsg=4326)
pozos_gdf = gpd.read_file(os.path.join(data_dir, "Pozos.shp")).to_crs(epsg=4326)
distritos_combinado_gdf = gpd.read_file(os.path.join(data_dir, "Distrito_combinado.shp")).to_crs(epsg=4326)
centroides_gdf = gpd.read_file(os.path.join(data_dir, "Centroide.gpkg")).to_crs(epsg=4326)

# CSV de demandas
demandas_sectores = pd.read_csv(os.path.join(data_dir, "Demandas_Sectores_30lhd.csv"))
demandas_distritos = pd.read_csv(os.path.join(data_dir, "Demandas_Distritos_30lhd.csv"))

# Normalizar
sectores_gdf["ZONENAME"] = sectores_gdf["ZONENAME"].apply(normalizar)
demandas_sectores["ZONENAME"] = demandas_sectores["ZONENAME"].apply(normalizar)
distritos_gdf["NOMBDIST"] = distritos_gdf["NOMBDIST"].apply(normalizar)
demandas_distritos["Distrito"] = demandas_distritos["Distrito"].apply(normalizar)
distritos_combinado_gdf["NOMBDIST"] = distritos_combinado_gdf["NOMBDIST"].apply(normalizar)

# Merge con demandas
sectores_gdf = sectores_gdf.merge(
    demandas_sectores[["ZONENAME","Demanda_m3_dia"]],
    on="ZONENAME", how="left"
)
distritos_gdf = distritos_gdf.merge(
    demandas_distritos[["Distrito","Demanda_Distrito_m3_30_lhd"]],
    left_on="NOMBDIST", right_on="Distrito", how="left"
)

# ========= INTERFAZ =========
st.sidebar.header("⚙️ Configuración del análisis")
modo = st.sidebar.radio("Nivel de análisis", ["Sector", "Distrito", "Combinación Distritos", "Resumen general"])
escenario_sel = st.sidebar.selectbox("Escenario (%)", [10, 20, 30])
cisterna_sel = st.sidebar.radio("Tipo de cisterna", list(cisternas.keys()))

# ========= SECTOR =========
if modo == "Sector":
    sectores_ids = sectores_gdf["ZONENAME"].dropna().unique().tolist()
    sector_sel = st.sidebar.selectbox("Selecciona un sector", sectores_ids)

    row = sectores_gdf[sectores_gdf["ZONENAME"] == sector_sel].iloc[0]
    demanda = float(row["Demanda_m3_dia"]) if "Demanda_m3_dia" in row else 0
    geom_sector = row.geometry

    st.subheader(f"📍 Sector {sector_sel}")
    st.write(f"Demanda oficial: {demanda:.2f} m³/día")

    resultados, restante, total_viajes, total_costo, total_consumo = asignar_pozos(
        geom_sector.centroid, demanda, escenario_sel, cisterna_sel, pozos_gdf
    )

    m = folium.Map(location=[geom_sector.centroid.y, geom_sector.centroid.x], zoom_start=14, tiles="cartodbpositron")
    folium.GeoJson(geom_sector, style_function=lambda x: {"color":"red","fillOpacity":0.3}).add_to(m)

    for pozo_id, aporte, viajes, costo, consumo, dist_km, geom in resultados:
        popup = f"Pozo {pozo_id}<br>Aporte: {aporte:.2f} m³/d<br>Viajes: {viajes}<br>Costo: S/ {costo:.2f}<br>Consumo: {consumo:.2f} gal<br>Dist: {dist_km:.3f} km"
        folium.CircleMarker([geom.y, geom.x], radius=6, color="blue", fill=True, popup=popup).add_to(m)

    st_folium(m, width=900, height=500, key="map_sector")
    df_res = pd.DataFrame(resultados, columns=["Pozo_ID","Aporte_m3_d","Viajes","Costo_total_S","Consumo_gal","Distancia_km","geom"]).drop(columns="geom")
    st.dataframe(df_res)

    if restante > 0:
        st.error(f"❌ El sector {sector_sel} requiere {demanda:.2f} m³/día. No satisfecha, faltan {restante:.2f} m³/día.")
    else:
        st.success(f"✅ El sector {sector_sel} requiere {demanda:.2f} m³/día. Satisfecha con {len(df_res)} pozos, {total_viajes} viajes, costo total S/ {total_costo:.2f}, consumo {total_consumo:.2f} gal.")

# ========= DISTRITO =========
if modo == "Distrito":
    distritos_ids = distritos_gdf["NOMBDIST"].dropna().unique().tolist()
    distrito_sel = st.sidebar.selectbox("Selecciona un distrito", distritos_ids)

    row = distritos_gdf[distritos_gdf["NOMBDIST"] == distrito_sel].iloc[0]
    demanda = float(row["Demanda_Distrito_m3_30_lhd"]) if "Demanda_Distrito_m3_30_lhd" in row else 0
    geom_dist = row.geometry

    st.subheader(f"📍 Distrito {distrito_sel}")
    st.write(f"Demanda oficial: {demanda:.2f} m³/día")

    resultados, restante, total_viajes, total_costo, total_consumo = asignar_pozos(
        geom_dist.centroid, demanda, escenario_sel, cisterna_sel, pozos_gdf
    )

    m = folium.Map(location=[geom_dist.centroid.y, geom_dist.centroid.x], zoom_start=12, tiles="cartodbpositron")
    folium.GeoJson(geom_dist, style_function=lambda x: {"color":"orange","fillOpacity":0.3}).add_to(m)

    for pozo_id, aporte, viajes, costo, consumo, dist_km, geom in resultados:
        popup = f"Pozo {pozo_id}<br>Aporte: {aporte:.2f} m³/d<br>Viajes: {viajes}<br>Costo: S/ {costo:.2f}<br>Consumo: {consumo:.2f} gal<br>Dist: {dist_km:.3f} km"
        folium.CircleMarker([geom.y, geom.x], radius=6, color="blue", fill=True, popup=popup).add_to(m)

    st_folium(m, width=900, height=500, key="map_dist")
    df_res = pd.DataFrame(resultados, columns=["Pozo_ID","Aporte_m3_d","Viajes","Costo_total_S","Consumo_gal","Distancia_km","geom"]).drop(columns="geom")
    st.dataframe(df_res)

    if restante > 0:
        st.error(f"❌ El distrito {distrito_sel} requiere {demanda:.2f} m³/día. No satisfecha, faltan {restante:.2f} m³/día.")
    else:
        st.success(f"✅ El distrito {distrito_sel} requiere {demanda:.2f} m³/día. Satisfecha con {len(df_res)} pozos, {total_viajes} viajes, costo total S/ {total_costo:.2f}, consumo {total_consumo:.2f} gal.")

# ========= COMBINACIÓN DE DISTRITOS =========
if modo == "Combinación Distritos":
    distritos_ids = distritos_combinado_gdf["NOMBDIST"].dropna().unique().tolist()
    seleccion = st.sidebar.multiselect("Selecciona distritos críticos", distritos_ids)

    if seleccion:
        subset = distritos_combinado_gdf[distritos_combinado_gdf["NOMBDIST"].isin(seleccion)]
        demanda_total = subset["Demanda_m3"].fillna(0).sum()

        st.subheader(f"📍 Combinación: {', '.join(seleccion)}")
        st.dataframe(subset[["NOMBDIST","Demanda_m3"]])
        st.write(f"🔢 Demanda total combinada: {demanda_total:.2f} m³/día")

        geom_union = unary_union(subset.geometry)
        geom_ref = geom_union.centroid

        m = folium.Map(location=[geom_ref.centroid.y, geom_ref.centroid.x], zoom_start=11, tiles="cartodbpositron")
        folium.GeoJson(geom_union, style_function=lambda x: {"color":"purple","fillOpacity":0.3}).add_to(m)

        resultados, restante, total_viajes, total_costo, total_consumo = asignar_pozos(
            geom_ref.centroid, demanda_total, escenario_sel, cisterna_sel, pozos_gdf
        )

        for pozo_id, aporte, viajes, costo, consumo, dist_km, geom in resultados:
            popup = f"Pozo {pozo_id}<br>Aporte: {aporte:.2f} m³/d<br>Viajes: {viajes}<br>Costo: S/ {costo:.2f}<br>Consumo: {consumo:.2f} gal<br>Dist: {dist_km:.3f} km"
            folium.CircleMarker([geom.y, geom.x], radius=6, color="blue", fill=True, popup=popup).add_to(m)

        st_folium(m, width=900, height=500, key="map_comb")
        df_res = pd.DataFrame(resultados, columns=["Pozo_ID","Aporte_m3_d","Viajes","Costo_total_S","Consumo_gal","Distancia_km","geom"]).drop(columns="geom")
        st.dataframe(df_res)

        if restante > 0:
            st.error(f"❌ La combinación de {', '.join(seleccion)} requiere {demanda_total:.2f} m³/día. No satisfecha, faltan {restante:.2f} m³/día.")
        else:
            st.success(f"✅ La combinación de {', '.join(seleccion)} requiere {demanda_total:.2f} m³/día. Satisfecha con {len(df_res)} pozos, {total_viajes} viajes, costo total S/ {total_costo:.2f}, consumo {total_consumo:.2f} gal.")

# ========= RESUMEN GENERAL =========
if modo == "Resumen general":
    st.subheader("📊 Resumen general de costos")

    # --- Sectores ---
    sectores_costos = []
    for _, row in sectores_gdf.iterrows():
        try:
            demanda = float(row["Demanda_m3_dia"])
        except:
            demanda = 0
        if demanda > 0:
            _, restante, total_viajes, total_costo, _ = asignar_pozos(
                row.geometry.centroid, demanda, escenario_sel, cisterna_sel, pozos_gdf
            )
            sectores_costos.append([row["ZONENAME"], demanda, total_costo])

    df_sect = pd.DataFrame(sectores_costos, columns=["Sector","Demanda_m3_d","Costo_S"])
    if not df_sect.empty:
        st.markdown("### 🔹 Sectores")
        st.dataframe(df_sect.sort_values("Costo_S", ascending=False))

        fig1 = px.bar(df_sect.sort_values("Costo_S", ascending=False).head(10),
                      x="Sector", y="Costo_S", title="Sectores más costosos", text="Costo_S")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(df_sect.sort_values("Costo_S", ascending=True).head(10),
                      x="Sector", y="Costo_S", title="Sectores menos costosos", text="Costo_S")
        st.plotly_chart(fig2, use_container_width=True)

        max_sector = df_sect.loc[df_sect["Costo_S"].idxmax()]
        min_sector = df_sect.loc[df_sect["Costo_S"].idxmin()]
        st.success(f"✅ El sector más costoso es **{max_sector['Sector']}** con un costo de S/ {max_sector['Costo_S']:.2f}.")
        st.info(f"ℹ️ El sector menos costoso es **{min_sector['Sector']}** con un costo de S/ {min_sector['Costo_S']:.2f}.")

    # --- Distritos ---
    distritos_costos = []
    for _, row in distritos_gdf.iterrows():
        try:
            demanda = float(row["Demanda_Distrito_m3_30_lhd"])
        except:
            demanda = 0
        if demanda > 0:
            _, restante, total_viajes, total_costo, _ = asignar_pozos(
                row.geometry.centroid, demanda, escenario_sel, cisterna_sel, pozos_gdf
            )
            distritos_costos.append([row["NOMBDIST"], demanda, total_costo])

    df_dist = pd.DataFrame(distritos_costos, columns=["Distrito","Demanda_m3_d","Costo_S"])
    if not df_dist.empty:
        st.markdown("### 🔹 Distritos")
        st.dataframe(df_dist.sort_values("Costo_S", ascending=False))

        fig3 = px.bar(df_dist.sort_values("Costo_S", ascending=False).head(10),
                      x="Distrito", y="Costo_S", title="Distritos más costosos", text="Costo_S")
        st.plotly_chart(fig3, use_container_width=True)

        fig4 = px.bar(df_dist.sort_values("Costo_S", ascending=True).head(10),
                      x="Distrito", y="Costo_S", title="Distritos menos costosos", text="Costo_S")
        st.plotly_chart(fig4, use_container_width=True)

        max_dist = df_dist.loc[df_dist["Costo_S"].idxmax()]
        min_dist = df_dist.loc[df_dist["Costo_S"].idxmin()]
        st.success(f"✅ El distrito más costoso es **{max_dist['Distrito']}** con un costo de S/ {max_dist['Costo_S']:.2f}.")
        st.info(f"ℹ️ El distrito menos costoso es **{min_dist['Distrito']}** con un costo de S/ {min_dist['Costo_S']:.2f}.")
