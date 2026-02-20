import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date
import re

# --- CONFIGURACIÓN DE BASE DE DATOS CON REPARACIÓN ---
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
    # Intentamos crear la tabla con la estructura completa
    c.execute('''CREATE TABLE IF NOT EXISTS obras 
                 (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, 
                  imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
    
    # TRUCO: Si la tabla ya existía pero es vieja, añadimos las columnas que falten
    try:
        c.execute("ALTER TABLE obras ADD COLUMN imagen_ficha TEXT")
        c.execute("ALTER TABLE obras ADD COLUMN casa TEXT")
        c.execute("ALTER TABLE obras ADD COLUMN fecha TEXT")
    except sqlite3.OperationalError:
        # Si da error es porque las columnas ya existen, así que no hacemos nada
        pass
        
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# --- INTERFAZ ---
st.set_page_config(page_title="Tasador Arte Gemini Pro", layout="wide", page_icon="🎨")
st.title("🎨 Art Auction Intelligence")

# Barra lateral
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("Introduce tu Google API Key", type="password")
menu = st.sidebar.selectbox("Menú", ["Nueva Subasta", "Mi Colección"])

# --- FUNCIÓN PARA LIMPIAR NÚMEROS ---
def limpiar_numero(texto):
    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto.replace(',', '.'))
    return float(numeros[0]) if numeros else 0.0

# --- LÓGICA PRINCIPAL ---
if menu == "Nueva Subasta":
    st.subheader("📸 Registro de Nueva Obra")
    
    col1, col2 = st.columns(2)
    with col1:
        foto_cuadro = st.file_uploader("1. Foto del CUADRO", type=['jpg', 'jpeg', 'png'])
        foto_ficha = st.file_uploader("2. Foto de la FICHA (datos)", type=['jpg', 'jpeg', 'png'])
    
    with col2:
        casa_subasta = st.text_input("Casa de Subastas", placeholder="Ej: Ansorena, Templum...")
        fecha_subasta = st.date_input("Fecha de la subasta", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6, step=0.1)

    if st.button("🚀 Analizar y Guardar"):
        if not api_key:
            st.error("⚠️ Falta la API Key en la barra lateral.")
        elif not foto_cuadro or not foto_ficha:
            st.warning("⚠️ Sube ambas fotos para continuar.")
        else:
            with st.spinner("Gemini analizando ficha técnica..."):
                try:
                    genai.configure(api_key=api_key)
                    modelos_probar = ['gemini-1.5-flash', 'gemini-1.5-pro']
                    response = None
                    
                    img_ficha = Image.open(foto_ficha)
                    prompt = "Analiza esta ficha de subasta. Responde estrictamente en este formato: Autor|Precio de martillo|Alto cm|Ancho cm. No digas nada más."

                    for nombre_modelo in modelos_probar:
                        try:
                            model = genai.GenerativeModel(nombre_modelo)
                            response = model.generate_content([prompt, img_ficha])
                            if response: break
                        except: continue

                    if response and response.text:
                        datos = response.text.strip().split("|")
                        if len(datos) >= 4:
                            autor = datos[0].strip()
                            p_martillo = limpiar_numero(datos[1])
                            alto = limpiar_numero(datos[2])
                            ancho = limpiar_numero(datos[3])
                            
                            precio_real = p_martillo * (1 + comision_pct / 100)
                            superficie = alto * ancho
                            ratio = precio_real / superficie if superficie > 0 else 0
                            
                            # Guardar Fotos
                            autor_folder = f"fotos/{autor.replace(' ', '_')}"
                            if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                            
                            path_cuadro = f"{autor_folder}/C_{foto_cuadro.name}"
                            path_ficha = f"{autor_folder}/F_{foto_ficha.name}"
                            
                            with open(path_cuadro, "wb") as f: f.write(foto_cuadro.getbuffer())
                            with open(path_ficha, "wb") as f: f.write(foto_ficha.getbuffer())
                            
                            # Guardar en BD
                            c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                      (autor, precio_real, ratio, path_cuadro, path_ficha, casa_subasta, str(fecha_subasta)))
                            conn.commit()
                            
                            st.success(f"✅ ¡{autor} guardado!")
                            st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {e}")

elif menu == "Mi Colección":
    st.subheader("📚 Tu Historial")
    try:
        obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
        
        if not obras:
            st.info("Catálogo vacío.")
        else:
            for o in obras:
                # El bloque expander ahora usa los índices correctos de la tabla actualizada
                with st.expander(f"📅 {o[6]} | {o[0]} - {o[5]}"):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    with c1: 
                        if os.path.exists(o[3]): st.image(o[3], caption="Obra")
                    with c2: 
                        if os.path.exists(o[4]): st.image(o[4], caption="Ficha")
                    with c3:
                        st.write(f"**Casa:** {o[5]}")
                        st.write(f"**Precio Total:** {o[1]:,.2f} €")
                        st.write(f"**Ratio:** {o[2]:.4f} €/cm²")
    except Exception as e:
        st.error("Hubo un problema con la base de datos. Por favor, reinicia la app en Streamlit Cloud.")
