import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date

# 1. BASE DE DATOS
conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS obras 
             (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
conn.commit()

# 2. CONFIGURACIÓN DE GEMINI
st.set_page_config(page_title="Gestor Subastas Gemini", layout="wide")
st.title("🚀 Tasador de Arte con Google Gemini")

api_key = st.sidebar.text_input("Introduce tu Google API Key (Gemini)", type="password")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # El más rápido y gratuito

# 3. INTERFAZ
menu = st.sidebar.selectbox("Menú", ["Nueva Subasta", "Mi Colección"])

if menu == "Nueva Subasta":
    st.subheader("📸 Captura de Datos")
    
    col1, col2 = st.columns(2)
    with col1:
        foto_cuadro = st.file_uploader("1. Foto del CUADRO", type=['jpg', 'png', 'jpeg'])
        foto_ficha = st.file_uploader("2. Foto de la FICHA (Datos)", type=['jpg', 'png', 'jpeg'])
    
    with col2:
        casa = st.text_input("Casa de Subastas")
        fecha_subasta = st.date_input("Fecha", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6)

    if st.button("🚀 Analizar con Gemini") and foto_cuadro and foto_ficha:
        if not api_key:
            st.error("Introduce la API Key en la barra lateral")
        else:
            with st.spinner("Gemini está leyendo la ficha técnica..."):
                try:
                    # Convertir imagen para Gemini
                    img_ficha = Image.open(foto_ficha)
                    
                    prompt = "Analiza esta ficha de subasta. Extrae: Autor, Precio de martillo (solo número), Alto (cm), Ancho (cm). Responde así: Autor|Precio|Alto|Ancho"
                    
                    response = model.generate_content([prompt, img_ficha])
                    datos = response.text.strip().split("|")
                    
                    autor, precio_m, alto, ancho = datos[0], float(datos[1]), float(datos[2]), float(datos[3])
                    
                    # Cálculos
                    precio_r = precio_m * (1 + comision_pct/100)
                    ratio = precio_r / (alto * ancho) if (alto * ancho) > 0 else 0
                    
                    # Guardar fotos localmente
                    autor_folder = f"fotos/{autor.replace(' ', '_')}"
                    if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                    
                    path_cuadro = f"{autor_folder}/C_{foto_cuadro.name}"
                    path_ficha = f"{autor_folder}/F_{foto_ficha.name}"
                    
                    with open(path_cuadro, "wb") as f: f.write(foto_cuadro.getbuffer())
                    with open(path_ficha, "wb") as f: f.write(foto_ficha.getbuffer())
                    
                    # Guardar en BD
                    c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                              (autor, precio_r, ratio, path_cuadro, path_ficha, casa, str(fecha_subasta)))
                    conn.commit()
                    
                    st.success(f"✅ ¡Éxito! Guardado {autor} en la colección.")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Error: {e}")

elif menu == "Mi Colección":
    st.subheader("📚 Historial de Subastas")
    obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
    
    for o in obras:
        with st.expander(f"{o[6]} | {o[0]} ({o[5]})"):
            c1, c2 = st.columns(2)
            with c1:
                st.image(o[3], caption="Obra")
            with c2:
                st.image(o[4], caption="Ficha", width=200)
                st.write(f"**Precio Real:** {o[1]:,.2f}€")
                st.write(f"**Ratio:** {o[2]:.4f} €/cm²")
                st.write(f"**Casa:** {o[5]}")
