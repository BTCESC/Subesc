import streamlit as st
import google.generativeai as genai
from PIL import Image
from datetime import date
import uuid
import json
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Archivo de Arte Pro", layout="wide")
st.title("🎨 Mi Clasificador de Subastas (Modo Nube ☁️)")

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_supabase()
except Exception as e:
    st.error("⚠️ Faltan las claves de Supabase. Recuerda poner SUPABASE_URL y SUPABASE_KEY en los Secrets de Streamlit.")
    st.stop()

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
                        Busca también la TÉCNICA o TIPO de obra (ejemplo: óleo sobre lienzo, acuarela, litografía, grabado, técnica mixta, etc.).
                        Extrae los datos y devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
                        {
                            "autor": "Nombre del autor",
                            "tecnica": "Óleo sobre lienzo",
                            "precio_martillo": 1500.0,
                            "alto_cm": 100.0,
                            "ancho_cm": 80.0
                        }
                        Si un dato no aparece, pon 0 para los números o "Desconocido" para el texto. NO incluyas texto extra, solo el JSON.
                        """
                        
                        response = model.generate_content(
                            [prompt, img_ficha],
                            generation_config=genai.types.GenerationConfig(temperature=0.0)
                        )
                        
                        if response:
                            texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
                            datos = json.loads(texto_limpio)
                            
                            st.session_state['datos_temporales'] = {
                                "autor": str(datos.get("autor", "Desconocido")).strip().upper(),
                                "tecnica": str(datos.get("tecnica", "Desconocida")).strip().capitalize(),
                                "precio": float(datos.get("precio_martillo", 0.0)),
                                "alto": float(datos.get("alto_cm", 0.0)),
                                "ancho": float(datos.get("ancho_cm", 0.0))
                            }
                            st.success("✅ Ficha leída. Por favor, revisa y confirma los datos abajo.")
                            
                except Exception as e:
                    st.error(f"Error: {e}")

    # PASO 2: REVISAR Y GUARDAR EN NUBE
    if 'datos_temporales' in st.session_state:
        st.info("✏️ Revisa los datos extraídos.")
        
        with st.form("form_confirmacion"):
            col_txt1, col_txt2 = st.columns(2)
            with col_txt1:
                autor_editado = st.text_input("Autor", value=st.session_state['datos_temporales']['autor'])
            with col_txt2:
                tecnica_editada = st.text_input("Técnica / Soporte", value=st.session_state['datos_temporales']['tecnica'])

            precio_editado = st.number_input("Precio de Martillo / Salida (€)", value=st.session_state['datos_temporales']['precio'], format="%.2f")
            
            col_dim1, col_dim2 = st.columns(2)
            with col_dim1:
                alto_editado = st.number_input("Alto (cm)", value=st.session_state['datos_temporales']['alto'], format="%.2f")
            with col_dim2:
                ancho_editado = st.number_input("Ancho (cm)", value=st.session_state['datos_temporales']['ancho'], format="%.2f")
                
            confirmar = st.form_submit_button("☁️ 2. Subir a la Colección en Nube")
            
            if confirmar:
                if foto_cuadro and foto_ficha:
                    with st.spinner("Subiendo archivos y datos a Supabase..."):
                        precio_r = precio_editado * (1 + comision_pct / 100)
                        ratio = precio_r / (alto_editado * ancho_editado) if (alto_editado * ancho_editado) > 0 else 0
                        
                        id_unico = str(uuid.uuid4().hex[:8])
                        autor_limpio = autor_editado.replace(' ', '_')
                        
                        # 1. Subir fotos
                        path_c = f"{autor_limpio}/C_{id_unico}_{foto_cuadro.name}"
                        supabase.storage.from_('fotos').upload(
                            file=foto_cuadro.getvalue(), 
                            path=path_c, 
                            file_options={"content-type": foto_cuadro.type}
                        )
                        url_c = supabase.storage.from_('fotos').get_public_url(path_c)
                        
                        path_f = f"{autor_limpio}/F_{id_unico}_{foto_ficha.name}"
                        supabase.storage.from_('fotos').upload(
                            file=foto_ficha.getvalue(), 
                            path=path_f, 
                            file_options={"content-type": foto_ficha.type}
                        )
                        url_f = supabase.storage.from_('fotos').get_public_url(path_f)
                        
                        # 2. Guardar datos
                        data = {
                            "autor": autor_editado,
                            "tecnica": tecnica_editada,
                            "precio_real": precio_r,
                            "ratio": ratio,
                            "imagen_cuadro": url_c,
                            "imagen_ficha": url_f,
                            "casa": casa_subasta,
                            "fecha": str(fecha_subasta)
                        }
                        supabase.table("obras").insert(data).execute()
                        
                        del st.session_state['datos_temporales']
                        st.success(f"🎉 ¡Obra de {autor_editado} subida permanentemente!")
                        st.rerun()
                else:
                    st.error("Faltan las fotos.")

# --- 4. COLECCIÓN AGRUPADA ---
elif menu == "📚 Ver Mi Colección":
    st.subheader("Tu Archivo Clasificado por Autores")
    
    with st.spinner("Cargando tu colección desde la nube..."):
        response = supabase.table("obras").select("*").order("fecha", desc=True).execute()
        obras = response.data
    
    if not obras:
        st.info("Tu colección en la nube está vacía. ¡Empieza a subir cuadros!")
    else:
        autores = sorted(list(set([obra['autor'] for obra in obras])))
        
        for nombre_autor in autores:
            with st.expander(f"📁 AUTOR: {nombre_autor}"):
                obras_autor = [o for o in obras if o['autor'] == nombre_autor]
                
                for obra in obras_autor:
                    col_info, col_img_c, col_img_f = st.columns([2, 2, 1])
                    with col_info:
                        st.write(f"🏛️ **Casa:** {obra['casa']}")
                        st.write(f"🖌️ **Técnica:** {obra['tecnica']}")
                        st.write(f"💰 **Precio Total:** {obra['precio_real']:,.2f} €")
                        st.write(f"📏 **Ratio:** {obra['ratio']:.4f} €/cm²")
                        st.write(f"📅 **Fecha:** {obra['fecha']}")
                        
                        st.write("") 
                        if st.button("🗑️ Borrar esta obra", key=f"del_{obra['id']}"):
                            try:
                                path_c = obra['imagen_cuadro'].split('/fotos/')[-1]
                                path_f = obra['imagen_ficha'].split('/fotos/')[-1]
                                supabase.storage.from_('fotos').remove([path_c, path_f])
                            except:
                                pass
                                
                            supabase.table("obras").delete().eq("id", obra['id']).execute()
                            st.rerun()

                    with col_img_c:
                        if obra['imagen_cuadro']: st.image(obra['imagen_cuadro'], caption="Cuadro", use_container_width=True)
                    with col_img_f:
                        if obra['imagen_ficha']: st.image(obra['imagen_ficha'], caption="Ficha", use_container_width=True)
                    st.divider()

