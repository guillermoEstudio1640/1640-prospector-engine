import streamlit as st
import pandas as pd
import json
import re
from google import genai
from google.genai import types

# Configuración de página Streamlit
st.set_page_config(page_title="1640 Prospector Engine", page_icon="⚡", layout="wide")

st.title("⚡ 1640 Prospector Engine")
st.subheader("Motor B2B de Extracción y Enriquecimiento de Leads con Email Validado")

# Sidebar - Credenciales
st.sidebar.header("⚙️ Configuración")
api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Tu clave de Google AI Studio")

# Formulario de Prospección
col1, col2 = st.columns(2)
with col1:
    nombre_proyecto = st.text_input("Nombre del Proyecto / Archivo", placeholder="Ej: Dobladoras Córdoba")
    pais = st.text_input("País / Estado / Ciudad", placeholder="Ej: Córdoba, Argentina")
with col2:
    industria = st.text_input("Industria / Producto / ICP", placeholder="Ej: Talleres mecánicos que vendan caños de escape")

btn_ejecutar = st.button("🚀 Iniciar Prospección y Generar CSV", type="primary")

def prospectar_leads(key, proj_name, country_val, ind_val):
    client = genai.Client(api_key=key)
    
    prompt = f"""
    Sos '1640 Prospector Engine', un agente experto en inteligencia comercial B2B.
    Busca empresas reales en {country_val} del rubro/ICP: {ind_val}.
    
    REGLA DE ORO INNEGOCIABLE: Solo debes devolver empresas que posean un EMAIL comercial público validado.
    Si una empresa no tiene correo electrónico accesible en la web, DESÉCHALA Y NO LA INCLUYAS.
    
    Deduce la categoría de Brevo más adecuada e inclúyela en 'category'.
    
    Devuelve la respuesta ÚNICAMENTE como un arreglo JSON de objetos con estas llaves exactas:
    [
      {{
        "email": "ejemplo@empresa.com",
        "company": "Nombre Empresa",
        "country": "{country_val}",
        "category": "Categoría Brevo",
        "city": "Ciudad",
        "phone": "+54...",
        "website": "empresa.com",
        "notes": "Detalles del negocio"
      }}
    ]
    """
    
    # Se utiliza el modelo gemini-2.5-flash requerido por tu cuenta
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],  # Búsqueda web en vivo
            temperature=0.2
        )
    )
    return response.text

if btn_ejecutar:
    if not api_key:
        st.error("⚠️ Por favor ingresá tu Gemini API Key en el panel lateral.")
    elif not nombre_proyecto or not pais or not industria:
        st.warning("⚠️ Por favor completá todos los campos del formulario.")
    else:
        with st.spinner("⚡ 1640 Prospector Engine ejecutando búsquedas web en vivo y filtrando correos electrónicos..."):
            try:
                raw_text = prospectar_leads(api_key, nombre_proyecto, pais, industria)
                
                # Extraer JSON de la respuesta
                json_match = re.search(r'\[[\s\S]*\]', raw_text)
                if json_match:
                    data = json.loads(json_match.group(0))
                    df = pd.DataFrame(data)
                    
                    # Renombrar columnas al estándar Brevo
                    col_map = {
                        "email": "EMAIL", "company": "COMPANY", "country": "COUNTRY",
                        "category": "CATEGORY", "city": "CITY", "phone": "PHONE",
                        "website": "WEBSITE", "notes": "NOTES"
                    }
                    df = df.rename(columns=col_map)
                    
                    # Filtrar filas vacías de email
                    df = df[df['EMAIL'].str.contains('@', na=False)]
                    
                    st.success(f"¡Prospección finalizada! Se encontraron {len(df)} prospectos validados con email.")
                    st.dataframe(df, use_container_width=True)
                    
                    # Botón de descarga de CSV listo para Brevo / Google Sheets
                    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Descargar CSV para Brevo / Google Sheets",
                        data=csv_data,
                        file_name=f"{nombre_proyecto}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No se encontraron empresas con email público disponible para esa consulta.")
            except Exception as e:
                st.error(f"Error durante la ejecución: {str(e)}")
