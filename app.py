import streamlit as st
import sqlite3
import os
import google.generativeai as genai
from PIL import Image
from datetime import date

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('coleccion_arte.db', check_same_thread=False)
    c = conn.cursor()
    # Tabla con todos los campos: autor, precio real, ratio, ruta cuadro, ruta ficha, casa subasta y fecha
    c.execute('''CREATE TABLE IF NOT EXISTS obras 
                 (autor TEXT, precio_real REAL, ratio REAL, imagen_cuadro TEXT, 
                  imagen_ficha TEXT, casa TEXT, fecha TEXT)''')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# --- 2. CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="Tasador Arte Gemini", layout="wide", page_icon="🎨")

st.title("🎨 Art Auction Intelligence (Powered by Gemini)")

# Barra lateral para la API Key y el Menú
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("Introduce tu Google API Key", type="password")

menu = st.sidebar.selectbox("Selecciona una opción", ["Nueva Subasta", "Mi Colección"])

# --- 3. LÓGICA DE PROCESAMIENTO CON GEMINI ---
if menu == "Nueva Subasta":
    st.subheader("📸 Registro de Nueva Obra")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Imágenes")
        foto_cuadro = st.file_uploader("1. Sube la foto del CUADRO (limpia)", type=['jpg', 'jpeg', 'png'])
        foto_ficha = st.file_uploader("2. Sube la foto de la FICHA (datos)", type=['jpg', 'jpeg', 'png'])
    
    with col2:
        st.write("### Datos de la Subasta")
        casa_subasta = st.text_input("Casa de Subastas", placeholder="Ej: Ansorena, Templum...")
        fecha_subasta = st.date_input("Fecha de la subasta", date.today())
        comision_pct = st.number_input("Comisión de la casa (%)", value=26.6, step=0.1)

    if st.button("🚀 Analizar y Guardar"):
        if not api_key:
            st.error("⚠️ Por favor, introduce tu Google API Key en la barra lateral.")
        elif not foto_cuadro or not foto_ficha:
            st.warning("⚠️ Debes subir ambas fotos (cuadro y ficha) para continuar.")
        else:
            with st.spinner("Gemini está analizando la ficha técnica..."):
                try:
                    # Configurar Gemini
                    genai.configure(api_key=api_key)
                    # Usamos 'gemini-1.5-flash-latest' para máxima compatibilidad
                    model = genai.GenerativeModel('gemini-1.5-flash-latest')
                    
                    # Cargar imagen de la ficha
                    img_ficha = Image.open(foto_ficha)
                    
                    # Instrucciones para la IA
                    prompt = """
                    Analiza esta imagen de una ficha de subasta de arte.
                    Extrae los siguientes datos:
                    1. Nombre del autor.
                    2. Precio de martillo (solo el número).
                    3. Altura en cm.
                    4. Anchura en cm.
                    Responde estrictamente en este formato, sin palabras extra:
                    Nombre del Autor|Precio|Altura|Anchura
                    """
                    
                    response = model.generate_content([prompt, img_ficha])
                    
                    if response.text:
                        # Separar los datos recibidos
                        datos = response.text.strip().split("|")
                        autor = datos[0]
                        p_martillo = float(datos[1].replace(',', '.'))
                        alto = float(datos[2].replace(',', '.'))
                        ancho = float(datos[3].replace(',', '.'))
                        
                        # Cálculos automáticos
                        precio_real = p_martillo * (1 + comision_pct / 100)
                        superficie = alto * ancho
                        ratio = precio_real / superficie if superficie > 0 else 0
                        
                        # --- GUARDAR FOTOS ---
                        autor_folder = f"fotos/{autor.replace(' ', '_')}"
                        if not os.path.exists(autor_folder):
                            os.makedirs(autor_folder)
                        
                        path_cuadro = f"{autor_folder}/CUADRO_{foto_cuadro.name}"
                        path_ficha = f"{autor_folder}/FICHA_{foto_ficha.name}"
                        
                        with open(path_cuadro, "wb") as f:
                            f.write(foto_cuadro.getbuffer())
                        with open(path_ficha, "wb") as f:
                            f.write(foto_ficha.getbuffer())
                        
                        # --- GUARDAR EN BASE DE DATOS ---
                        c.execute("INSERT INTO obras VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                  (autor, precio_real, ratio, path_cuadro, path_ficha, casa_subasta, str(fecha_subasta)))
                        conn.commit()
                        
                        st.success(f"✅ ¡Obra de {autor} guardada con éxito!")
                        st.balloons()
                        
                        # Mostrar resumen rápido
                        st.info(f"**Precio Final:** {precio_real:,.2f} € | **Ratio:** {ratio:.4f} €/cm²")
                    else:
                        st.error("La IA no pudo extraer datos. Asegúrate de que la foto de la ficha sea clara.")
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar: {e}")

# --- 4. GALERÍA DE LA COLECCIÓN ---
elif menu == "Mi Colección":
    st.subheader("📚 Historial de Obras y Pintores")
    
    # Obtener todas las obras ordenadas por fecha reciente
    obras = c.execute("SELECT * FROM obras ORDER BY fecha DESC").fetchall()
    
    if not obras:
        st.info("Todavía no has registrado ninguna obra. Ve a 'Nueva Subasta' para empezar.")
    else:
        # Filtro por autor
        lista_autores = ["Todos"] + sorted(list(set([o[0] for o in obras])))
        filtro = st.selectbox("Filtrar por autor:", lista_autores)
        
        for o in obras:
            if filtro == "Todos" or o[0] == filtro:
                with st.expander(f"📅 {o[6]} | {o[0]} - {o[5]}"):
                    col_img1, col_img2, col_txt = st.columns([2, 1, 2])
                    
                    with col_img1:
                        if os.path.exists(o[3]):
                            st.image(o[3], caption="Obra/Cuadro", use_container_width=True)
                    
                    with col_img2:
                        if os.path.exists(o[4]):
                            st.image(o[4], caption="Ficha Técnica", use_container_width=True)
                            
                    with col_txt:
                        st.write(f"🏛️ **Casa de Subastas:** {o[5]}")
                        st.write(f"💰 **Precio Real (con {comision_pct}%):** {o[1]:,.2f} €")
                        st.write(f"📏 **Ratio Inversión:** {o[2]:.4f} €/cm²")
                        st.write(f"🗓️ **Fecha de registro:** {o[6]}")
