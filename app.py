import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date
import re

# --- 1. BASE DE DATOS (REPARACIÓN FORZOSA) ---
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
    # Comprobamos si la tabla tiene todas las columnas necesarias
    try:
        c.execute("SELECT imagen_ficha, casa FROM obras LIMIT 1")
    except sqlite3.OperationalError:
        # Si falla, borramos y recreamos para limpiar errores de versiones previas
        c.execute("DROP TABLE IF EXISTS obras")
        c.execute('''CREATE TABLE obras 
                     (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, 
                      imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Archivo de Arte", layout="wide")
st.title("🎨 Mi Clasificador de Subastas")

st.sidebar.header("⚙️ Configuración")
api_key = st.sidebar.text_input("Introduce tu Google API Key", type="password")
menu = st.sidebar.selectbox("Ir a:", ["➕ Subir Nueva Obra", "📚 Ver Mi Colección"])

def limpiar_numero(texto):
    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto.replace(',', '.'))
    return float(numeros[0]) if numeros else 0.0

# --- 3. SUBIDA DE DATOS ---
if menu == "➕ Subir Nueva Obra":
    st.subheader("Registrar nueva obra")
    col1, col2 = st.columns(2)
    with col1:
        foto_cuadro = st.file_uploader("1. Foto del Cuadro", type=['jpg', 'jpeg', 'png'], key="cuadro")
        foto_ficha = st.file_uploader("2. Foto de la Ficha (Datos)", type=['jpg', 'jpeg', 'png'], key="ficha")
    with col2:
        casa_subasta = st.text_input("Casa de Subastas", value="Desconocida")
        fecha_subasta = st.date_input("Fecha de Subasta", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6)

    if st.button("🚀 Analizar y Guardar"):
        if not api_key:
            st.error("Introduce la API Key en la barra lateral")
        elif not foto_cuadro or not foto_ficha:
            st.warning("Faltan fotos por subir")
        else:
            with st.spinner("Gemini analizando y clasificando..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash-latest')
                    img_ficha = Image.open(foto_ficha)
                    
                    prompt = "Analiza esta ficha. Extrae: Autor, PrecioMartillo, Alto, Ancho. Responde solo: Autor|Precio|Alto|Ancho"
                    response = model.generate_content([prompt, img_ficha])
                    
                    datos = response.text.strip().split("|")
                    autor_raw = datos[0].strip().upper()
                    p_martillo = limpiar_numero(datos[1])
                    alto = limpiar_numero(datos[2])
                    ancho = limpiar_numero(datos[3])
                    
                    precio_r = p_martillo * (1 + comision_pct / 100)
                    ratio = precio_r / (alto * ancho) if (alto * ancho) > 0 else 0
                    
                    # Guardar Archivos en carpetas por Autor
                    autor_folder = f"fotos/{autor_raw.replace(' ', '_')}"
                    if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                    
                    path_c = f"{autor_folder}/C_{foto_cuadro.name}"
                    path_f = f"{autor_folder}/F_{foto_ficha.name}"
                    
                    with open(path_c, "wb") as f: f.write(foto_cuadro.getbuffer())
                    with open(path_f, "wb") as f: f.write(foto_ficha.getbuffer())
                    
                    # Guardar en Base de Datos
                    c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                              (autor_raw, precio_r, ratio, path_c, path_f, casa_subasta, str(fecha_subasta)))
                    conn.commit()
                    st.success(f"✅ ¡Guardado! Autor: {autor_raw}")
                except Exception as e:
                    st.error(f"Error procesando la imagen: {e}")

# --- 4. COLECCIÓN AGRUPADA POR AUTOR ---
elif menu == "📚 Ver Mi Colección":
    st.subheader("Tu Archivo Clasificado")
    
    # Consultamos autores únicos que tengan obras
    autores = c.execute("SELECT DISTINCT autor FROM obras ORDER BY autor ASC").fetchall()
    
    if not autores:
        st.info("Tu colección está vacía. Sube tu primera obra en el menú de la izquierda.")
    else:
        st.write(f"Tienes obras de **{len(autores)}** autores diferentes.")
        
        # Iteramos por cada autor
        for (nombre_autor,) in autores:
            # Creamos una "carpeta" desplegable para cada autor
            with st.expander(f"📁 AUTOR: {nombre_autor}"):
                # Buscamos todas las obras de este autor específico
                obras_autor = c.execute("SELECT * FROM obras WHERE autor=? ORDER BY fecha DESC", (nombre_autor,)).fetchall()
                
                for obra in obras_autor:
                    col_txt, col_img_c, col_img_f = st.columns([2, 2, 1])
                    with col_txt:
                        st.markdown(f"#### Detalle")
                        st.write(f"🏛️ **Casa:** {obra[5]}")
                        st.write(f"💰 **Precio Real:** {obra[1]:,.2f} €")
                        st.write(f"📏 **Ratio:** {obra[2]:.4f} €/cm²")
                        st.write(f"📅 **Fecha:** {obra[6]}")
                    with col_img_c:
                        if os.path.exists(obra[3]):
                            st.image(obra[3], caption="Cuadro", use_container_width=True)
                    with col_img_f:
                        if os.path.exists(obra[4]):
                            st.image(obra[4], caption="Ficha", use_container_width=True)
                    st.divider()
