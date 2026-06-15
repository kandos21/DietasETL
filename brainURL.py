import os
import io
import sys
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# =================================================================
# CONFIGURACIÓN DE PARÁMETROS - ENLACE DE ONEDRIVE COMPARTIDO
# =================================================================
# Aquí pegas el enlace de compartir que te mande la otra persona
URL_COMPARTIDA_ONEDRIVE = "https://login.microsoftonline.com/c59dc56a-93ec-4b07-b71d-43c844925718/oauth2/authorize?client%5Fid=00000003%2D0000%2D0ff1%2Dce00%2D000000000000&response%5Fmode=form%5Fpost&ear%5Fjwe%5Fcrypto=eyJhbGciOiJFQ0RILUVTIiwiZW5jIjoiQTI1NkdDTSIsImFwdiI6IkFBQUFDVVZoY2tOc2FXVnVkR2dBQUFCRlEwc3pNQUFBQU1QbTVjRjcxLy95dmtuSCtiT0x3L3lOdmp1UTJNSkI1ektpSFA3cEt3ek85RlBmd0xqNGNEVTJtb2t3VHZWWXJvTWxPL2NzcDhLU2IvZlNvQitEbXNpQzZqd2I4dCs3Z3dtcmczTEhTTnBnU2Y3VzFNWVFwcGFHenNvV3NKd0JjQUFBQUJoblFoOEMvc1pHYTk2T05pcm5GRFNuNXM3L21reDU3Wjg9In0%3D&ear%5Fjwk=eyJhbGciOiJFQ0RILUVTIiwiY3J2IjoiUC0zODQiLCJ4IjoiQUFBQU1NUG01Y0Y3MS8veXZrbkgrYk9Mdy95TnZqdVEyTUpCNXpLaUhQN3BLd3pPOUZQZndMajRjRFUybW9rd1R2VllyZz09IiwieSI6IkFBQUFNSU1sTy9jc3A4S1NiL2ZTb0IrRG1zaUM2andiOHQrN2d3bXJnM0xIU05wZ1NmN1cxTVlRcHBhR3pzb1dzSndCY0E9PSIsImt0eSI6IkVDIn0%3D&spa%5Fclient%5Fid=08e18876%2D6177%2D487e%2Db8b5%2Dcf950c1e598c&client%5Finfo=1&response%5Ftype=code%20id%5Ftoken%20spa%5Frt&resource=00000003%2D0000%2D0ff1%2Dce00%2D000000000000&scope=openid&nonce=363C761EED1446115C3DC81B20AE73EE9682C31496AFE683%2DF8FFA82417954EDE0E32E467646279B402C1E70211225C2BC4B169F8EB817CE3&redirect%5Furi=https%3A%2F%2Fsenasica%2Dmy%2Esharepoint%2Ecom%2F%5Fforms%2Fdefault%2Easpx&state=OD0wJjMyPUFBTHNnQUFBQUJRNzI4MlFkU1lLamZBU0pYSiUyRmI4aVo4VzV2aHNDSXFBWFNyYjFGaUY5WmJseENqYTNhMnRISWRQV1RzQmZ2dk9KWWRVaDNEeGlmckFYNXQ2OWVQcUJLTmR6RU1jWlhQSHJEVVhxMGtEb3BQV0dmdUI4Yk80cW1EWFljRjBkOG5DTnR1aW9DVFNjS3d2dGY1bjlDdCUyRmVEV0clMkZzU1M2cHA3djdhR0wwZ1o5Nk9Eck1qUlFOaTRSZVdjbWpPSnU0TjBkSmVlelZYZzR4SGlOTkx5M3FPRmxjbU1kbmh6U3dsR0swZ3Q4bkRrV0w4cGFtMmNEMGkybFpkanFqZEswaklQcmQzbVYycW5EQTRTUXpTRGM5YjJhR2NuaXY2OWxMNkd5dzZoM3h4SzFmdnFYMFhsNmhaSWlHYjFXWCUyRnVVMTJhMGozMG5pZ0klMkY3SGlabHlnZm03elNzd0FFWGslMkZQUXkwVnBvQ3hSJTJGZTFVcmJ3YW5XZUlKdGpXZmc4JTNE&claims=%7B%22id%5Ftoken%22%3A%7B%22xms%5Fcc%22%3A%7B%22values%22%3A%5B%22CP1%22%5D%7D%7D%7D&wsucxt=1&cobrandid=11bd8083%2D87e0%2D41b5%2Dbb78%2D0bc43c8a8e8a&client%2Drequest%2Did=1b011da2%2D1097%2Dd000%2D2550%2D16543d397488"

load_dotenv()

def transformar_enlace_onedrive(url_compartida):
    """ Convierte un enlace estándar de OneDrive compartido en un enlace de descarga directa """
    import base64
    if "1drv.ms" in url_compartida:
        # Enlaces cortos comerciales
        return url_compartida.replace("?web=1", "").replace("/x/s!", "/x/s!") + "?download=1"
    else:
        # Enlaces institucionales (SharePoint/OneDrive Business)
        # Convertimos la URL a formato de ID seguro para la API de Microsoft
        data_bytes = url_compartida.encode("utf-8")
        base64_bytes = base64.b64encode(data_bytes).decode("utf-8").replace("=", "").replace("/", "_").replace("+", "-")
        return f"https://api.onedrive.com/v1.0/shares/u!{base64_bytes}/root/content"

def conectar_postgres():
    usuario = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    db = os.getenv("PG_DATABASE")
    cadena_conexion = f"postgresql+psycopg2://{usuario}:{password}@{host}:{port}/{db}"
    return create_engine(cadena_conexion, connect_args={"options": "-c search_path=public"})

def pipeline_etl_nube():
    print("🚀 Iniciando el Pipeline ETL automático desde OneDrive Cloud...")
    
    try:
        engine = conectar_postgres()
    except Exception as e:
        print(f"❌ ERROR DE CONEXIÓN A POSTGRESQL: {e}")
        sys.exit(1)
        
    # Descargar el archivo directamente de la nube a la memoria RAM
    print("📥 Descargando archivo de Excel desde OneDrive...")
    try:
        url_descarga = transformar_enlace_onedrive(URL_COMPARTIDA_ONEDRIVE)
        respuesta = requests.get(url_descarga)
        respuesta.raise_for_status()
        # Convertimos los bytes descargados en un objeto que Pandas pueda abrir
        excel_objeto = pd.ExcelFile(io.BytesIO(respuesta.content))
        hojas_disponibles = excel_objeto.sheet_names
    except Exception as e:
        print(f"❌ ERROR AL DESCARGAR EL ARCHIVO DESDE ONEDRIVE: Enlace roto o privado. Detalle: {e}")
        return

    # [A partir de aquí, el resto de tu lógica de procesamiento de hojas sigue exactamente IGUAL]
    for nombre_hoja in hojas_disponibles:
        if not any(char.isdigit() for char in nombre_hoja):
            continue
            
        print(f"  └── 🔄 Procesando pestaña mensual de la nube: [{nombre_hoja}]")
        try:
            df_raw = pd.read_excel(excel_objeto, sheet_name=nombre_hoja, skiprows=9)
            df_raw.columns = [str(c).strip() for c in df_raw.columns]
            
            # (Filtros de limpieza de notas que implementamos anteriormente...)
            df_raw = df_raw[df_raw['Almacen'].notna() & (df_raw['Almacen'].astype(str).str.strip() != '')]
            df_raw = df_raw[df_raw['Clave ITEM'].notna() & (df_raw['Clave ITEM'].astype(str).str.strip() != '')]
            
            if df_raw.empty:
                continue
                
            # [El código continúa con PASO 1, PASO 2 y PASO 3 de cargas idempotentes a Postgres...]
            # ...
            print(f"    ✅ Hoja [{nombre_hoja}] sincronizada con éxito.")
        except Exception as ex:
            print(f"❌ Error en hoja {nombre_hoja}: {ex}")

if __name__ == "__main__":
    pipeline_etl_nube()