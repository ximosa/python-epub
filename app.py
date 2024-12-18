import streamlit as st
import os
import zipfile
import shutil
import google.generativeai as genai
from bs4 import BeautifulSoup
import logging
import time

# Configuración del logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Muestra logs en la consola también
)

def extraer_epub(ruta_epub):
    logging.info(f"Iniciando extracción de: {ruta_epub}")
    temp_dir = "libro_temp"
    
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        with zipfile.ZipFile(ruta_epub, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            logging.info("EPUB descomprimido correctamente")
        
        texto_completo = ""
        archivos_procesados = 0
        
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.html', '.xhtml')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            soup = BeautifulSoup(f.read(), 'html.parser')
                            texto_completo += soup.get_text(separator=' ', strip=True) + "\n"
                            archivos_procesados += 1
                            logging.info(f"Procesado archivo {file}")
                    except Exception as e:
                        logging.error(f"Error procesando {file}: {str(e)}")
        
        logging.info(f"Procesados {archivos_procesados} archivos")
        return texto_completo
        
    except Exception as e:
        logging.error(f"Error en extracción: {str(e)}")
        raise
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def dividir_texto(texto, max_chars=30000):
    logging.info(f"Dividiendo texto de {len(texto)} caracteres")
    texto = texto[:200000]  # Aumentado para permitir más contenido
    partes = []
    
    while texto:
        if len(texto) <= max_chars:
            partes.append(texto)
            break
        indice = texto[:max_chars].rfind('.')
        if indice == -1:
            indice = texto[:max_chars].rfind(' ')
        partes.append(texto[:indice + 1])
        texto = texto[indice + 1:].strip()
    
    logging.info(f"Texto dividido en {len(partes)} partes")
    return partes

def generar_resumen(texto):
    logging.info("Iniciando generación de resumen")
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    modelo = genai.GenerativeModel('gemini-pro')
    
    prompt = """
    Actúa como un lector profundo y reflexivo. Escribe un resumen conciso y coherente del texto en primera persona, como si tú hubieras vivido la experiencia o reflexionado sobre los temas presentados.
    Sigue estas pautas:
    - Evita mencionar nombres de personajes o del autor.
    - Concentra el resumen en la experiencia general, las ideas principales, los temas y las emociones transmitidas por el texto.
    - Utiliza un lenguaje evocador y personal, como si estuvieras compartiendo tus propias conclusiones tras una profunda reflexión.
    - No uses nombres propios ni nombres de lugares específicos, refiérete a ellos como "un lugar", "una persona", "otro personaje", etc.
    - Usa un lenguaje claro y directo
    - Escribe como si estuvieras narrando una historia
    - Separa ideas solo con puntos y comas
    - El texto debe fluir naturalmente al ser leído en voz alta
    
    Texto a resumir:
    """
    
    max_retries = 3
    base_delay = 5
    
    try:
        partes = dividir_texto(texto)
        resumenes = []
        
        for i, parte in enumerate(partes, 1):
            logging.info(f"Procesando parte {i}/{len(partes)}")
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    respuesta = modelo.generate_content(prompt + parte)
                    resumenes.append(respuesta.text)
                    logging.info(f"Parte {i} resumida correctamente")
                    time.sleep(base_delay)  # Mayor pausa entre llamadas
                    break
                    
                except Exception as e:
                    retry_count += 1
                    wait_time = base_delay * (2 ** retry_count)  # Backoff exponencial
                    logging.warning(f"Intento {retry_count} fallido. Esperando {wait_time} segundos...")
                    time.sleep(wait_time)
                    
                    if retry_count == max_retries:
                        logging.error(f"Error en parte {i} después de {max_retries} intentos: {str(e)}")
                        continue
        
        return "\n\n".join(resumenes)
        
    except Exception as e:
        logging.error(f"Error en generación de resumen: {str(e)}")
        raise

def main():
    st.title("Extractor de Libros EPUB")
    
    # Selector de archivo EPUB
    uploaded_file = st.file_uploader("Seleccionar archivo EPUB", type=['epub'])
    
    # Nombre del archivo de salida
    output_filename = st.text_input("Nombre del archivo de salida", "resumen.txt")
    
    if st.button("Procesar"):
        if uploaded_file is None:
            st.error("Por favor, selecciona un archivo EPUB")
            return
            
        try:
            with st.spinner("Extrayendo contenido del EPUB..."):
                # Guardado temporal del archivo
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Extracción del texto
                texto = extraer_epub(temp_path)
                
            with st.spinner("Generando resumen con IA..."):
                resumen = generar_resumen(texto)
                
            with st.spinner("Guardando resultado..."):
                # Guardar resultado
                with open(output_filename, 'w', encoding='utf-8') as f:
                    f.write(resumen)
                
            # Limpieza del archivo temporal
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            st.success(f"¡Proceso completado! Archivo guardado como: {output_filename}")
            
            # Botón de descarga
            with open(output_filename, 'r', encoding='utf-8') as f:
                st.download_button(
                    label="Descargar resumen",
                    data=f.read(),
                    file_name=output_filename,
                    mime="text/plain"
                )
                
        except Exception as e:
            st.error(f"Error durante el procesamiento: {str(e)}")

if __name__ == "__main__":
    main()
