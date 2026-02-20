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
             (autor TEXT, precio_real REAL, ratio REAL, imagen_ruta TEXT, casa TEXT, fecha TEXT)''')
conn.commit()

# 2. FUNCIÓN PARA QUE LA IA LEA LA IMAGEN
def analizar_con_ia(client, lista_imagenes):
    # Convertimos la primera imagen a formato que entienda la IA
    base64_image = base64.b64encode(lista_imagenes[0].read()).decode('utf-8')
    
    prompt = """Analiza estas fotos de una subasta de arte. 
    Extrae: 1. Nombre del autor, 2. Precio de martillo (solo el número), 3. Medidas (alto y ancho).
    Responde estrictamente en este formato: Autor|Precio|Alto|Ancho"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}]
    )
    return response.choices[0].message.content

# 3. INTERFAZ
st.title("🎨 Analizador de Arte Inteligente")

api_key = st.sidebar.text_input("Pega tu OpenAI API Key", type="password")
menu = st.sidebar.selectbox("Menú", ["Nueva Subasta", "Mi Colección"])

if menu == "Nueva Subasta":
    files = st.file_uploader("Sube las fotos (Cuadro y Ficha)", accept_multiple_files=True)
    casa = st.text_input("Casa de Subastas")
    comision_input = st.number_input("Comisión de la casa (%)", value=26.6)

    if st.button("Analizar y Guardar") and files and api_key:
        client = OpenAI(api_key=api_key)
        with st.spinner("La IA está leyendo las fotos reales..."):
            try:
                # La IA lee los datos de TUS fotos
                resultado = analizar_con_ia(client, files)
                autor, precio_m, alto, ancho = resultado.split("|")
                
                # Cálculos con datos REALES
                precio_r = float(precio_m) * (1 + comision_input/100)
                ratio = precio_r / (float(alto) * float(ancho))
                
                # Guardar foto
                if not os.path.exists(f"fotos/{autor}"): os.makedirs(f"fotos/{autor}")
                ruta = f"fotos/{autor}/{files[0].name}"
                with open(ruta, "wb") as f: f.write(files[0].getbuffer())
                
                # Guardar en base de datos
                c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?)", 
                          (autor, precio_r, ratio, ruta, casa, str(date.today())))
                conn.commit()
                st.success(f"¡Guardado! Autor detectado: {autor}")
            except Exception as e:
                st.error(f"Error al leer la foto: {e}. Asegúrate de que se vea bien el texto.")

elif menu == "Mi Colección":
    # (Aquí va el código de visualización que ya teníamos)
    obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
    for obra in obras:
        with st.expander(f"{obra[0]} - {obra[4]}"):
            st.image(obra[3])
            st.write(f"Precio Real: {obra[1]} € | Ratio: {obra[2]}")
