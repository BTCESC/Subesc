import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date
import uuid
import json

# --- 1. BASE DE DATOS ---
@st.cache_resource
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
    try:
        # Busca imagen_cuadro en vez de casa. Si tenías la base de datos vieja, 
        # esto fallará a propósito, borrará la antigua y creará la nueva perfecta.
        c.execute("SELECT imagen_cuadro FROM obras LIMIT 1")
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
    
    col1, col2 = st.columns(2)
    with col1:
        foto_cuadro = st.file_uploader("1. Foto del Cuadro", type=['jpg', 'jpeg', 'png'])
        foto_ficha = st.file_uploader("2. Foto de la Ficha (Datos)", type=['jpg', 'jpeg', 'png'])
    with col2:
        casa_subasta = st.text_input("Casa de Subastas", value="Ansorena")
        fecha_subasta = st.date_input("Fecha de Subasta", date.today())
        comision_pct = st.number_input("Comisión (%)", value=26.6)

    # PASO 1: LEER CON IA
    if st.button("🔍 1. Leer ficha con IA"):
        if not api_key:
            st.error("Por favor, pega tu clave API en el menú de la izquierda.")
        elif not foto_cuadro or not foto_ficha:
            st.warning("Faltan fotos.")
        else:
            with st.spinner("Analizando la ficha con precisión..."):
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
                        
                        prompt = """
                        Analiza cuidadosamente esta ficha técnica de una obra de arte en subasta. 
                        Busca el precio (puede aparecer como 'Precio de salida', 'Estimación', 'Salida', 'Remate' o un número con el símbolo €). 
                        Si hay un rango (ej: 1000 - 1500), coge el número más bajo.
                        Extrae los datos y devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
                        {
                            "autor": "Nombre del autor",
                            "precio_martillo": 1500.0,
                            "alto_cm": 100.0,
                            "ancho_cm": 80.0
                        }
                        Si un dato no aparece, pon 0 para los números o "Desconocido" para el autor. NO incluyas texto extra, solo el JSON.
                        """
                        
                        # Generación con temperatura 0.0 para que sea analítico y no invente datos
                        response = model.generate_content(
                            [prompt, img_ficha],
                            generation_config=genai.types.GenerationConfig(temperature=0.0)
                        )
                        
                        if response:
                            texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
                            datos = json.loads(texto_limpio)
                            
                            # Guardamos los resultados temporalmente en memoria
                            st.session_state['datos_temporales'] = {
                                "autor": str(datos.get("autor", "Desconocido")).strip().upper(),
                                "precio": float(datos.get("precio_martillo", 0.0)),
                                "alto": float(datos.get("alto_cm", 0.0)),
                                "ancho": float(datos.get("ancho_cm", 0.0))
                            }
                            st.success("✅ Ficha leída. Por favor, revisa y confirma los datos abajo.")
                            
                except json.JSONDecodeError:
                    st.error("Error: La IA no devolvió los datos correctamente. Inténtalo de nuevo.")
                except Exception as e:
                    st.error(f"Error detallado: {e}")

    # PASO 2: REVISAR, CORREGIR Y GUARDAR
    if 'datos_temporales' in st.session_state:
        st.info("✏️ Revisa los datos extraídos. Puedes modificar el precio si la IA no lo leyó bien.")
        
        with st.form("form_confirmacion"):
            autor_editado = st.text_input("Autor", value=st.session_state['datos_temporales']['autor'])
            precio_editado = st.number_input("Precio de Martillo / Salida (€)", value=st.session_state['datos_temporales']['precio'], format="%.2f")
            
            col_dim1, col_dim2 = st.columns(2)
            with col_dim1:
                alto_editado = st.number_input("Alto (cm)", value=st.session_state['datos_temporales']['alto'], format="%.2f")
            with col_dim2:
                ancho_editado = st.number_input("Ancho (cm)", value=st.session_state['datos_temporales']['ancho'], format="%.2f")
                
            confirmar = st.form_submit_button("💾 2. Confirmar y Guardar en Colección")
            
            if confirmar:
                if foto_cuadro and foto_ficha:
                    # Cálculos con los datos definitivos
                    precio_r = precio_editado * (1 + comision_pct / 100)
                    ratio = precio_r / (alto_editado * ancho_editado) if (alto_editado * ancho_editado) > 0 else 0
                    
                    autor_folder = f"fotos/{autor_editado.replace(' ', '_')}"
                    if not os.path.exists(autor_folder): os.makedirs(autor_folder)
                    
                    id_unico = uuid.uuid4().hex[:8]
                    path_c = f"{autor_folder}/C_{id_unico}_{foto_cuadro.name}"
                    path_f = f"{autor_folder}/F_{id_unico}_{foto_ficha.name}"
                    
                    with open(path_c, "wb") as f: f.write(foto_cuadro.getbuffer())
                    with open(path_f, "wb") as f: f.write(foto_ficha.getbuffer())
                    
                    # Inserción blindada con los nombres exactos de las columnas
                    c.execute('''INSERT INTO obras (autor, precio_real, ratio, imagen_cuadro, imagen_ficha, casa, fecha) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                              (autor_editado, precio_r, ratio, path_c, path_f, casa_subasta, str(fecha_subasta)))
                    conn.commit()
                    
                    # Borramos la memoria para subir la siguiente obra
                    del st.session_state['datos_temporales']
                    st.success(f"🎉 ¡Obra de {autor_editado} guardada con éxito!")
                else:
                    st.error("Las fotos se han perdido de la pantalla, por favor vuelve a seleccionarlas.")

# --- 4. COLECCIÓN AGRUPADA POR AUTOR ---
elif menu == "📚 Ver Mi Colección":
    st.subheader("Tu Archivo Clasificado por Autores")
    autores = c.execute("SELECT DISTINCT autor FROM obras ORDER BY autor ASC").fetchall()
    
    if not autores:
        st.info("Tu colección está vacía. ¡Empieza a subir cuadros!")
    else:
        for (nombre_autor,) in autores:
            with st.expander(f"📁 AUTOR: {nombre_autor}"):
                obras_autor = c.execute("SELECT * FROM obras WHERE autor=? ORDER BY fecha DESC", (nombre_autor,)).fetchall()
                for obra in obras_autor:
                    col_info, col_img_c, col_img_f = st.columns([2, 2, 1])
                    with col_info:
                        st.write(f"🏛️ **Casa:** {obra[5]}")
                        st.write(f"💰 **Precio Total:** {obra[1]:,.2f} €")
                        st.write(f"📏 **Ratio:** {obra[2]:.4f} €/cm²")
                        st.write(f"📅 **Fecha:** {obra[6]}")
                    with col_img_c:
                        if os.path.exists(obra[3]): st.image(obra[3], caption="Cuadro", use_column_width=True)
                    with col_img_f:
                        if os.path.exists(obra[4]): st.image(obra[4], caption="Ficha")
                    st.divider()
