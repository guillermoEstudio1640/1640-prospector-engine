import streamlit as st
import pandas as pd
import json
import re
from google import genai
from google.genai import types

st.set_page_config(page_title="1640 Prospector Engine", page_icon="⚡", layout="wide")

st.title("⚡ 1640 Prospector Engine")
st.subheader("Motor B2B de Extracción y Enriquecimiento de Leads")

st.sidebar.header("⚙️ Configuración")
api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Tu clave de Google AI Studio")

col1, col2 = st.columns(2)
with col1:
    nombre_proyecto = st.text_input("Nombre del Proyecto / Archivo", placeholder="Ej: Dobladoras Córdoba")
    pais = st.text_input("País / Estado / Ciudad", placeholder="Ej: Córdoba, Argentina")
with col2:
    industria = st.text_input("Industria / Producto / ICP", placeholder="Ej: Talleres mecánicos que vendan caños de escape")

btn_ejecutar = st.button("🚀 Iniciar Prospección y Generar CSV", type="primary")

def prospectar_fase1_busqueda(client, country_val, ind_val):
    # 1 SOLA llamada con búsqueda web para identificar empresas reales
    prompt_search = f"Busca empresas reales en {country_val} del rubro/ICP: {ind_val}. Lista de 10 a 15 empresas con sus sitios web oficiales y ubicaciones."
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt_search,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
            temperature=0.2
        )
    )
    return response.text

def prospectar_fase2_extraccion(client, raw_search_results, country_val, ind_val):
    # Procesamiento denso de emails y formato JSON sin gastar cuota de Search Grounding
    prompt_json = f"""
    Basándote en la siguiente información de empresas encontradas:
    
    {raw_search_results}
    
    REGLA DE ORO INNEGOCIABLE: Solo debes incluir empresas que posean o infieras un EMAIL comercial o de contacto válido.
    Si no hay email accesible o deduible, omite la empresa.
    
    Devuelve la respuesta ÚNICAMENTE como un arreglo JSON estricto con las siguientes llaves:
    [
      {{
        "email": "contacto@empresa.com",
        "company": "Nombre Empresa",
        "country": "{country_val}",
        "category": "Categoría Brevo según el rubro",
        "city": "Ciudad",
        "phone": "Teléfono",
        "website": "sitio.com",
        "notes": "Detalles del rubro"
      }}
    ]
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt_json,
        config=types.GenerateContentConfig(
            temperature=0.1
        )
    )
    return response.text

if btn_ejecutar:
    if not api_key:
        st.error("⚠️ Por favor ingresá tu Gemini API Key en el panel lateral.")
    elif not nombre_proyecto or not pais or not industria:
        st.warning("⚠️ Por favor completá todos los campos del formulario.")
    else:
        status_box = st.empty()
        status_box.info("⚡ Paso 1/2: Rastreando empresas en la web...")
        
        try:
            client = genai.Client(api_key=api_key)
            
            # Paso 1: Búsqueda rápida
            search_results = prospectar_fase1_busqueda(client, pais, industria)
            
            status_box.info("⚡ Paso 2/2: Validando emails y formateando para Brevo...")
            
            # Paso 2: Estructuración JSON limpia
            json_raw = prospectar_fase2_extraccion(client, search_results, pais, industria)
            
            status_box.empty()
            
            # Extraer y renderizar CSV
            json_match = re.search(r'\[[\s\S]*\]', json_raw)
            if json_match:
                data = json.loads(json_match.group(0))
                df = pd.DataFrame(data)
                
                col_map = {
                    "email": "EMAIL", "company": "COMPANY", "country": "COUNTRY",
                    "category": "CATEGORY", "city": "CITY", "phone": "PHONE",
                    "website": "WEBSITE", "notes": "NOTES"
                }
                df = df.rename(columns=col_map)
                
                if 'EMAIL' in df.columns:
                    df = df[df['EMAIL'].str.contains('@', na=False)]
                
                st.success(f"¡Prospección finalizada! Se obtuvieron {len(df)} prospectos.")
                st.dataframe(df, use_container_width=True)
                
                csv_data = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Descargar CSV para Brevo / Google Sheets",
                    data=csv_data,
                    file_name=f"{nombre_proyecto}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No se pudieron validar correos electrónicos para esta búsqueda.")
                
        except Exception as e:
            status_box.empty()
            st.error(f"Error durante la ejecución: {str(e)}")
