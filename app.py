import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date
import re

# --- 1. BASE DE DATOS (REPARACIÓN TOTAL) ---
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
    # Si la tabla no tiene la columna 'casa', la borramos para crearla bien
    try:
        c.execute("SELECT casa FROM obras LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("DROP TABLE IF EXISTS obras")
        c.execute('''CREATE TABLE obras 
                     (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, 
                      imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Archivo de Arte Pro", layout="wide")
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
        foto_cuadro = st.file_uploader("1. Foto del Cuadro", type=['jpg', 'jpeg', 'png'])
        foto_ficha = st.file_uploader("2. Foto de la Ficha (Datos)", type=['jpg', 'jpeg', 'png'])
    with col2:
        casa_subasta = st.text_input("Casa de Subastas", value="Ansorena")
        fecha_subasta = st.date_input("Fecha de Subasta", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6)

    if st.button("🚀 Analizar y Guardar"):
        if not api_key:
            st.error("Pon la API Key en la izquierda.")
        elif not foto_cuadro or not foto_ficha:
            st.warning("Faltan fotos.")
        else:
            with st.spinner("Gemini analizando..."):
                try:
                    genai.configure(api_key=api_key)
                    
                    # --- SOLUCIÓN AL ERROR 404: Probamos varios nombres de modelo ---
                    model_found = False
                    for model_name in ['gemini-1.5-flash', 'gemini-1.5-flash-latest']:
                        try:
                            model = genai.GenerativeModel(model_name)
                            img_ficha = Image.open(foto_ficha)
                            prompt = "Analiza esta ficha. Responde estrictamente: Autor|PrecioMartillo|Alto|Ancho"
                            response = model.generate_content([prompt, img_ficha])
                            if response:
                                model_found = True
                                break
                        except:
                            continue
                    
                    if not model_found:
                        st.error("No se pudo conectar con los modelos de Gemini. Revisa tu API Key.")
                    else:
                        datos = response.text.strip().split("|")
                        autor_raw = datos[0].strip().upper()
                        p_martillo = limpiar_numero(datos[1])
                        alto = limpiar_numero(datos[2])
                        ancho = limpiar_numero(datos[3])
                        
                        precio_r = p_martillo * (1 + comision_pct / 100)
                        ratio = precio_r / (alto * ancho) if (alto * ancho) > 0 else 0
                        
                        # Crear carpetas por autor
                        autor_folder = f"fotos/{autor_raw.replace(' ', '_')}"
                        if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                        
                        path_c = f"{autor_folder}/C_{foto_cuadro.name}"
                        path_f = f"{autor_folder}/F_{foto_ficha.name}"
                        
                        with open(path_c, "wb") as f: f.write(foto_cuadro.getbuffer())
                        with open(path_f, "wb") as f: f.write(foto_ficha.getbuffer())
                        
                        c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                  (autor_raw, precio_r, ratio, path_c, path_f, casa_subasta, str(fecha_subasta)))
                        conn.commit()
                        st.success(f"✅ ¡Guardado! Autor: {autor_raw}")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- 4. COLECCIÓN AGRUPADA POR AUTOR ---
elif menu == "📚 Ver Mi Colección":
    st.subheader("Tu Archivo Clasificado por Autores")
    
    autores = c.execute("SELECT DISTINCT autor FROM obras ORDER BY autor ASC").fetchall()
    
    if not autores:
        st.info("Tu colección está vacía. Sube algo primero.")
    else:
        for (nombre_autor,) in autores:
            # Aquí está la "carpeta" por autor que querías
            with st.expander(f"📁 AUTOR: {nombre_autor}"):
                obras_autor = c.execute("SELECT * FROM obras WHERE autor=? ORDER BY fecha DESC", (nombre_autor,)).fetchall()
                
                for obra in obras_autor:
                    col_info, col_img_c, col_img_f = st.columns([2, 2, 1])
                    with col_info:
                        st.write(f"🏛️ **Casa:** {obra[5]}")
                        st.write(f"💰 **Precio Real:** {obra[1]:,.2f} €")
                        st.write(f"📏 **Ratio:** {obra[2]:.4f} €/cm²")
                        st.write(f"📅 **Fecha:** {obra[6]}")
                    with col_img_c:
                        if os.path.exists(obra[3]):
                            st.image(obra[3], caption="Cuadro")
                    with col_img_f:
                        if os.path.exists(obra[4]):
                            st.image(obra[4], caption="Ficha", width=150)
                    st.divider()
