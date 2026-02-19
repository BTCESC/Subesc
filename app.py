import streamlit as st
import os
import pandas as pd
from openai import OpenAI
from PIL import Image

st.set_page_config(page_title="Gestor de Subastas Pro", layout="wide")
st.title("🎨 Art Auction Intelligence (Multi-Foto)")

api_key = st.sidebar.text_input("Introduce tu OpenAI API Key", type="password")
client = OpenAI(api_key=api_key) if api_key else None

# --- CARGA DE ARCHIVOS ---
# Ahora permitimos subir más de una foto
uploaded_files = st.file_uploader("Sube la foto del cuadro Y la de los datos", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files and client:
    cols = st.columns(len(uploaded_files))
    for i, file in enumerate(uploaded_files):
        with cols[i]:
            st.image(file, caption=f"Imagen {i+1}", use_container_width=True)
    
    if st.button("Procesar Obra"):
        with st.spinner("La IA está analizando ambas imágenes..."):
            # Aquí la IA leería las dos imágenes simultáneamente
            # Una para identificar el cuadro y otra para el texto del catálogo
            
            datos_ia = {
                "autor": "Charles James", 
                "precio_martillo": 1000.0,
                "comision_casa": 26.6,
                "ancho": 50,
                "alto": 70
            }
            
            # Cálculos automáticos
            precio_real = datos_ia["precio_martillo"] * (1 + datos_ia["comision_casa"]/100)
            superficie = datos_ia["ancho"] * datos_ia["alto"]
            ratio = precio_real / superficie

            st.success(f"### Análisis Completado: {datos_ia['autor']}")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Precio Real (con comisión)", f"{precio_real:,.2f} €")
            m2.metric("Superficie", f"{superficie} cm²")
            m3.metric("Ratio €/cm²", f"{ratio:.4f}")

            # Organizar en carpetas
            nombre_autor = datos_ia["autor"].replace(" ", "_")
            if not os.path.exists(nombre_autor):
                os.makedirs(nombre_autor)
            
            # Guardamos todas las fotos subidas en la carpeta del autor
            for file in uploaded_files:
                ruta = os.path.join(nombre_autor, file.name)
                with open(ruta, "wb") as f:
                    f.write(file.getbuffer())
            
            st.info(f"📁 Todas las fotos han sido guardadas en la carpeta de autor: **{nombre_autor}**")
