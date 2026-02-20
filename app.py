import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date
import uuid
import json

# --- 1. BASE DE DATOS ---
@st.cache_resource # MEJORA: Mantiene la conexión abierta eficientemente
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
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

# --- 3. SUBIDA DE DATOS ---
if menu == "➕ Subir Nueva Obra":
    st.subheader("Registrar nueva obra")
    
    # MEJORA: Usamos un formulario para que la app no se recargue con cada clic
    with st.form("formulario_obra"):
        col1, col2 = st.columns(2)
        with col1:
            foto_cuadro = st.file_uploader("1. Foto del Cuadro", type=['jpg', 'jpeg', 'png'])
            foto_ficha = st.file_uploader("2. Foto de la Ficha (Datos)", type=['jpg', 'jpeg', 'png'])
        with col2:
            casa_subasta = st.text_input("Casa de Subastas", value="Ansorena")
            fecha_subasta = st.date_input("Fecha de Subasta", date.today())
            comision_pct = st.number_input("Comisión (%)", value=26.6)
            
        # El botón de envío del formulario
        submitted = st.form_submit_button("🚀 Analizar y Guardar")

    if submitted:
        if not api_key:
            st.error("Por favor, pega tu clave API en el menú de la izquierda.")
        elif not foto_cuadro or not foto_ficha:
            st.warning("Faltan fotos por subir.")
        else:
            with st.spinner("Buscando modelo compatible y analizando la ficha..."):
                try:
                    genai.configure(api_key=api_key)
                    
                    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    vision_models = [m for m in available_models if "flash" in m or "pro" in m]
                    
                    if not vision_models:
                        st.error("Tu API Key no tiene acceso a modelos de visión.")
                    else:
                        selected_model = vision_models[0]
                        model = genai.GenerativeModel(selected_model)
                        
                        img_ficha = Image.open(foto_ficha)
                        
                        # MEJORA: Pedimos a la IA que responda estrictamente en JSON
                        prompt = """
                        Analiza esta ficha técnica de una obra de arte. 
                        Extrae los siguientes datos y devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
                        {
                            "autor": "Nombre del autor",
                            "precio_martillo": 1500.50,
                            "alto_cm": 100,
                            "ancho_cm": 80
                        }
                        Si no encuentras un dato, pon 0 o "Desconocido". Devuelve SOLO el JSON, sin bloques de código (```).
                        """
                        response = model.generate_content([prompt, img_ficha])
                        
                        if response:
                            # Limpiamos posibles restos de formato markdown
                            texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
                            datos = json.loads(texto_limpio)
                            
                            autor_raw = str(datos.get("autor", "Desconocido")).strip().upper()
                            p_martillo = float(datos.get("precio_martillo", 0))
                            alto = float(datos.get("alto_cm", 0))
                            ancho = float(datos.get("ancho_cm", 0))
                            
                            precio_r = p_martillo * (1 + comision_pct / 100)
                            ratio = precio_r / (alto * ancho) if (alto * ancho) > 0 else 0
                            
                            autor_folder = f"fotos/{autor_raw.replace(' ', '_')}"
                            if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                            
                            # MEJORA: Generamos un ID único para no sobreescribir fotos
                            id_unico = uuid.uuid4().hex[:8]
                            path_c = f"{autor_folder}/C_{id_unico}_{foto_cuadro.name}"
                            path_f = f"{autor_folder}/F_{id_unico}_{foto_ficha.name}"
                            
                            with open(path_c, "wb") as f: f.write(foto_cuadro.getbuffer())
                            with open(path_f, "wb") as f: f.write(foto_ficha.getbuffer())
                            
                            c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                      (autor_raw, precio_r, ratio, path_c, path_f, casa_subasta, str(fecha_subasta)))
                            conn.commit()
                            st.success(f"✅ ¡Guardado con éxito! Autor detectado: {autor_raw}")
                        
                except json.JSONDecodeError:
                    st.error("Error: La IA no devolvió los datos correctamente. Por favor, inténtalo de nuevo.")
                except Exception as e:
                    st.error(f"Error detallado: {e}")

# --- 4. COLECCIÓN AGRUPADA POR AUTOR ---
elif menu == "📚 Ver Mi Colección":
    st.subheader("Tu Archivo Clasificado por Autores")
    autores = c.execute("SELECT DISTINCT autor FROM obras ORDER BY autor ASC").fetchall()
    
    if not autores:
        st.info("Tu colección está vacía.")
    else:
        for (nombre_autor,) in autores:
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
                        if os.path.exists(obra[3]): st.image(obra[3], caption="Cuadro")
                    with col_img_f:
                        if os.path.exists(obra[4]): st.image(obra[4], caption="Ficha", width=150)
                    st.divider()
