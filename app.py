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
    # Usamos la primera imagen (la de los datos) para el análisis
    base64_image = base64.b64encode(lista_imagenes[0].read()).decode('utf-8')
    
    prompt = """Analiza la foto de esta ficha de subasta de arte. 
    Extrae: 1. Nombre del autor, 2. Precio de martillo (solo el número), 3. Medidas (alto y ancho en cm).
    Responde estrictamente en este formato: Autor|Precio|Alto|Ancho
    Si no encuentras algún dato, pon 'Desconocido' o '0'."""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}]
    )
    return response.choices[0].message.content

# 3. INTERFAZ
st.set_page_config(page_title="Gestor Subastas Pro", layout="wide")
st.title("🎨 Analizador de Arte Inteligente")

api_key = st.sidebar.text_input("Pega tu OpenAI API Key", type="password")
menu = st.sidebar.selectbox("Menú", ["Nueva Subasta", "Mi Colección"])

if menu == "Nueva Subasta":
    st.subheader("Registrar Obra")
    
    col1, col2 = st.columns(2)
    with col1:
        files = st.file_uploader("Sube las fotos (Cuadro y Ficha)", accept_multiple_files=True)
        casa = st.text_input("Casa de Subastas (ej: Ansorena, Balclis...)")
    
    with col2:
        fecha_subasta = st.date_input("Fecha de la subasta", date.today())
        comision_input = st.number_input("Comisión de la casa (%)", value=26.6, step=0.1)

    if st.button("🚀 Analizar y Guardar en Historial") and files:
        if not api_key:
            st.error("Por favor, introduce tu API Key en la barra lateral.")
        else:
            client = OpenAI(api_key=api_key)
            with st.spinner("La IA está leyendo los datos de la subasta..."):
                try:
                    # La IA lee los datos REALES de la foto
                    resultado = analizar_con_ia(client, files)
                    autor, precio_m, alto, ancho = resultado.split("|")
                    
                    # Cálculos
                    p_martillo = float(precio_m.replace(',', '.'))
                    v_alto = float(alto.replace(',', '.'))
                    v_ancho = float(ancho.replace(',', '.'))
                    
                    precio_r = p_martillo * (1 + comision_input/100)
                    superficie = v_alto * v_ancho
                    ratio = precio_r / superficie if superficie > 0 else 0
                    
                    # Crear carpetas y guardar foto
                    autor_folder = autor.replace(" ", "_")
                    if not os.path.exists(f"fotos/{autor_folder}"): 
                        os.makedirs(f"fotos/{autor_folder}")
                    
                    ruta = f"fotos/{autor_folder}/{files[0].name}"
                    with open(ruta, "wb") as f: 
                        f.write(files[0].getbuffer())
                    
                    # Guardar en base de datos con FECHA seleccionada
                    c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?)", 
                              (autor, precio_r, ratio, ruta, casa, str(fecha_subasta)))
                    conn.commit()
                    
                    st.success(f"✅ ¡Guardado! Autor: {autor} | Precio Real: {precio_r:,.2f} €")
                    
                except Exception as e:
                    st.error(f"Error al procesar: {e}. Intenta que la foto de los datos sea clara.")

elif menu == "Mi Colección":
    st.subheader("📚 Historial de Obras Guardadas")
    
    # Obtener datos de la BD
    obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
    
    if not obras:
        st.info("Aún no hay obras en tu colección.")
    else:
        for obra in obras:
            with st.expander(f"📅 {obra[5]} | {obra[0]} - {obra[4]}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if os.path.exists(obra[3]):
                        st.image(obra[3], use_container_width=True)
                with c2:
                    st.write(f"🏛️ **Casa:** {obra[4]}")
                    st.write(f"💰 **Precio Total (inc. com.):** {obra[1]:,.2f} €")
                    st.write(f"📏 **Ratio de Inversión:** {obra[2]:.4f} €/cm²")
                    st.write(f"🗓️ **Fecha de Subasta:** {obra[5]}")
