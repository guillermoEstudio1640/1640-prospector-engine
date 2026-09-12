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

# La API Key se toma de los "Secrets" configurados en Streamlit Community Cloud
# (o de un archivo .streamlit/secrets.toml en local) para que todo el equipo
# use la misma key sin tener que pegarla cada uno. Si no está configurada,
# se muestra un campo para pegarla manualmente (útil para probar en local).
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key:
    st.sidebar.success("API Key configurada centralmente ✅")
else:
    st.sidebar.warning("No hay una API Key central configurada (Secrets).")
    api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Tu clave de Google AI Studio")

modelo = st.sidebar.selectbox(
    "Modelo de Gemini",
    ["gemini-3.6-flash", "gemini-2.5-flash"],
    index=0,
    help="gemini-3.6-flash es el recomendado. Si tu cuenta no tiene acceso todavía, usá gemini-2.5-flash.",
)

# Formulario de Prospección
col1, col2 = st.columns(2)
with col1:
    nombre_proyecto = st.text_input("Nombre del Proyecto / Archivo", placeholder="Ej: Dobladoras Córdoba")
    pais = st.text_input("País / Estado / Ciudad", placeholder="Ej: Córdoba, Argentina")
with col2:
    industria = st.text_input("Industria / Producto / ICP", placeholder="Ej: Talleres mecánicos que vendan caños de escape")

btn_ejecutar = st.button("🚀 Iniciar Prospección y Generar CSV", type="primary")

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

COLUMNAS = ["email", "company", "country", "category", "city", "phone", "website", "notes"]


def _extraer_json(texto: str):
    """El modelo a veces envuelve el JSON en ```json ... ``` u otro texto alrededor."""
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", texto, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Si no hay bloque de código, buscamos el primer '[' y el último ']'
    inicio = texto.find("[")
    fin = texto.rfind("]")
    if inicio != -1 and fin != -1 and fin > inicio:
        return json.loads(texto[inicio:fin + 1])

    # Último intento: el texto entero es JSON
    return json.loads(texto)


def prospectar_leads(key: str, model_name: str, proj_name: str, country_val: str, ind_val: str):
    client = genai.Client(api_key=key)

    prompt = f"""
    Sos '1640 Prospector Engine', un agente experto en inteligencia comercial B2B.
    Busca empresas reales en {country_val} del rubro/ICP: {ind_val}.

    REGLA DE ORO INNEGOCIABLE: Solo debes devolver empresas que posean un EMAIL comercial público validado.
    Si una empresa no tiene correo electrónico accesible en la web, DESÉCHALA Y NO LA INCLUYAS.

    Deduce la categoría de Brevo más adecuada e inclúyela en 'category'.

    Devuelve la respuesta ÚNICAMENTE como un arreglo JSON de objetos con estas llaves exactas,
    sin texto adicional antes ni después:
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

    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[grounding_tool],  # Búsqueda web en vivo
        ),
    )

    texto_respuesta = response.text or ""
    data = _extraer_json(texto_respuesta)

    if not isinstance(data, list):
        raise ValueError("La respuesta del modelo no es una lista JSON de empresas.")

    leads_validos = []
    for item in data:
        if not isinstance(item, dict):
            continue
        email = str(item.get("email", "")).strip()
        if not EMAIL_REGEX.match(email):
            continue  # segunda validación local, además de la que le pedimos al modelo
        fila = {col: item.get(col, "") for col in COLUMNAS}
        fila["email"] = email
        leads_validos.append(fila)

    df = pd.DataFrame(leads_validos, columns=COLUMNAS)
    return df, texto_respuesta


if btn_ejecutar:
    if not api_key:
        st.error("Ingresá tu Gemini API Key en la barra lateral.")
    elif not pais or not industria:
        st.error("Completá País/Ciudad e Industria/ICP.")
    else:
        with st.spinner("Buscando empresas y validando emails... esto puede tardar un minuto."):
            try:
                df, raw = prospectar_leads(api_key, modelo, nombre_proyecto, pais, industria)
            except Exception as e:
                st.error(f"Ocurrió un error al consultar el modelo: {e}")
                df, raw = None, None

        if df is not None:
            if df.empty:
                st.warning("El modelo no devolvió empresas con email validado para esa búsqueda.")
            else:
                st.success(f"Se encontraron {len(df)} leads con email validado.")
                st.dataframe(df, use_container_width=True)

                nombre_archivo = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre_proyecto or "leads").strip("_") or "leads"
                csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇️ Descargar CSV",
                    data=csv_bytes,
                    file_name=f"{nombre_archivo}.csv",
                    mime="text/csv",
                )

            with st.expander("Ver respuesta cruda del modelo (debug)"):
                st.code(raw or "", language="json")
