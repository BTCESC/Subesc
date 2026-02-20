import streamlit as st
import sqlite3
import os
from PIL import Image
from datetime import date

# 1. CONFIGURACIÓN DE BASE DE DATOS (Añadimos columnas de fecha y casa)
conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS obras 
             (autor TEXT, titulo TEXT, precio_real REAL, ratio REAL, 
              imagen_ruta TEXT, casa_subasta TEXT, fecha_subasta TEXT)''')
conn.commit()

st.set_page_config(page_title="Mi Tasador de Arte Pro", layout="wide")

# --- MENÚ LATERAL ---
menu = st.sidebar.selectbox("Selecciona una opción", ["Nueva Subasta", "Ver Mi Colección"])

if menu == "Nueva Subasta":
    st.title("🎨 Analizar y Registrar Obra")
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        files = st.file_uploader("Sube foto del cuadro y ficha", accept_multiple_files=True)
        casa_input = st.text_input("Casa de Subastas (ej: Templum, Ansorena...)", placeholder="Nombre de la casa")
        fecha_input = st.date_input("Fecha de la subasta", date.today())
    
    if st.button("Procesar y Guardar en Historial") and files:
        with st.spinner("La IA está calculando el valor real..."):
            # --- LÓGICA DE IA ---
            # En la versión real, aquí llamaríamos a OpenAI para sacar el autor y precio
            autor_detectado = "Charles James" 
            precio_martillo = 1000.0
            comision_pct = 26.6  # Aquí podrías poner un slider para ajustarlo
            
            precio_r = precio_martillo * (1 + comision_pct/100)
            ratio = precio_r / (50*70) # Ejemplo cm2
            
            # Guardar imagen físicamente
            if not os.path.exists(f"fotos/{autor_detectado}"):
                os.makedirs(f"fotos/{autor_detectado}")
            
            ruta_foto = f"fotos/{autor_detectado}/{files[0].name}"
            with open(ruta_foto, "wb") as f:
                f.write(files[0].getbuffer())
            
            # GUARDAR EN BASE DE DATOS con los nuevos campos
            c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                      (autor_detectado, "Obra en subasta", precio_r, ratio, ruta_foto, casa_input, str(fecha_input)))
            conn.commit()
            st.success(f"✅ ¡Obra guardada! Registrada en {casa_input} para el día {fecha_input}")

elif menu == "Ver Mi Colección":
    st.title("📚 Historial de Obras y Casas de Subastas")
    
    # Obtener lista de autores para filtrar
    autores = [row[0] for row in c.execute("SELECT DISTINCT autor FROM obras").fetchall()]
    
    if not autores:
        st.info("Tu catálogo está vacío. Sube una foto en 'Nueva Subasta'.")
    else:
        autor_sel = st.selectbox("Filtrar por Pintor", ["Todos"] + autores)
        
        # Consulta según el filtro
        if autor_sel == "Todos":
            obras = c.execute("SELECT * FROM obras ORDER BY fecha_subasta DESC").fetchall()
        else:
            obras = c.execute("SELECT * FROM obras WHERE autor=? ORDER BY fecha_subasta DESC", (autor_sel,)).fetchall()
        
        for obra in obras:
            with st.expander(f"🖼️ {obra[0]} - {obra[5]} ({obra[6]})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if os.path.exists(obra[4]):
                        st.image(obra[4], use_container_width=True)
                with c2:
                    st.write(f"🏛️ **Casa de Subastas:** {obra[5]}")
                    st.write(f"📅 **Fecha:** {obra[6]}")
                    st.write(f"💰 **Precio Real:** {obra[2]:,.2f} €")
                    st.write(f"📏 **Ratio de Inversión:** {obra[3]:.4f} €/cm²")
                    st.info(f"Ficha técnica guardada para {obra[0]}")
