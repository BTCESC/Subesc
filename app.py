import streamlit as st
import sqlite3
import os
import base64
from openai import OpenAI
from datetime import date

# 1. BASE DE DATOS
conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS obras 
             (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
conn.commit()

# 2. FUNCIÓN DE IA MEJORADA
def analizar_ficha(client, imagen_ficha):
    base64_ficha = base64.b64encode(imagen_ficha.read()).decode('utf-8')
    
    prompt = """Analiza esta ficha de subasta. 
    Extrae estrictamente en este formato: Autor|PrecioMartillo|Alto|Ancho
    Usa solo números para precio y medidas (en cm)."""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_ficha}"}}
        ]}]
    )
    return response.choices[0].message.content

# 3. INTERFAZ MEJORADA
st.set_page_config(page_title="Gestor Subastas Pro", layout="wide")
st.title("🎨 Clasificador de Arte Inteligente")

api_key = st.sidebar.text_input("Pega tu OpenAI API Key", type="password")
menu = st.sidebar.selectbox("Menú", ["Nueva Subasta", "Mi Colección"])

if menu == "Nueva Subasta":
    st.subheader("📸 Registro Separado de Obra")
    
    col1, col2 = st.columns(2)
    with col1:
        foto_cuadro = st.file_uploader("1. Sube solo la foto del CUADRO", type=['jpg', 'png', 'jpeg'])
        foto_ficha = st.file_uploader("2. Sube solo la foto de la FICHA/DATOS", type=['jpg', 'png', 'jpeg'])
    
    with col2:
        casa = st.text_input("Casa de Subastas")
        fecha_subasta = st.date_input("Fecha de la subasta", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6)

    if st.button("🚀 Procesar y Organizar") and foto_cuadro and foto_ficha:
        if not api_key:
            st.error("Falta la API Key en la barra lateral.")
        else:
            client = OpenAI(api_key=api_key)
            with st.spinner("Leyendo ficha técnica..."):
                try:
                    # IA analiza solo la ficha
                    datos = analizar_ficha(client, foto_ficha)
                    autor, precio_m, alto, ancho = datos.split("|")
                    
                    # Cálculos
                    precio_r = float(precio_m) * (1 + comision_pct/100)
                    ratio = precio_r / (float(alto) * float(ancho))
                    
                    # Organización de carpetas
                    autor_folder = f"fotos/{autor.replace(' ', '_')}"
                    if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                    
                    # Guardar ambas fotos
                    path_cuadro = f"{autor_folder}/CUADRO_{foto_cuadro.name}"
                    path_ficha = f"{autor_folder}/FICHA_{foto_ficha.name}"
                    
                    with open(path_cuadro, "wb") as f: f.write(foto_cuadro.getbuffer())
                    with open(path_ficha, "wb") as f: f.write(foto_ficha.getbuffer())
                    
                    # Guardar en BD
                    c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                              (autor, precio_r, ratio, path_cuadro, path_ficha, casa, str(fecha_subasta)))
                    conn.commit()
                    
                    st.success(f"✅ Guardado: {autor}. Precio: {precio_r:,.2f}€")
                except Exception as e:
                    st.error(f"Error: {e}")

elif menu == "Mi Colección":
    st.subheader("📚 Tu Galería de Autores")
    obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
    
    for o in obras:
        with st.expander(f"{o[6]} | {o[0]} ({o[5]})"):
            c1, c2 = st.columns(2)
            with c1:
                st.image(o[3], caption="Obra")
            with c2:
                st.image(o[4], caption="Ficha Técnica", width=200)
                st.write(f"**Precio Real:** {o[1]:,.2f}€ | **Ratio:** {o[2]:.4f}")
