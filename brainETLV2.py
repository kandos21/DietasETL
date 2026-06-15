import os
import glob
import sys
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar las variables del archivo .env o del entorno de GitHub
load_dotenv()

# =================================================================
# CONFIGURACIÓN DE RUTAS (Nube o Local)
# =================================================================
# Si existe la variable en el entorno (ej. en GitHub), la usa; si no, usa tu ruta local por defecto.
RUTA_LOCAL_DEFECTO = r"C:\Users\candido.lopez.i\Documents\OneDrive - Servicio Nacional de Sanidad, Inocuidad y Calidad Agroalimentaria (SENASICA)\POWER BI\Almacen-Dietas\2026"
RUTA_TRABAJO = os.getenv("RUTA_CARPETA_ETL", RUTA_LOCAL_DEFECTO)

def conectar_postgres():
    usuario = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    db = os.getenv("PG_DATABASE")

    cadena_conexion = f"postgresql+psycopg2://{usuario}:{password}@{host}:{port}/{db}"
    return create_engine(cadena_conexion, connect_args={"options": "-c search_path=public"})

def descargar_archivos_desde_url():
    """
    Opcional para GitHub Actions: Si configuras URLs de descarga directa 
    en tus variables de entorno, el script las descargará antes de procesar.
    """
    urls_env = os.getenv("URLS_DESCARGA_DIRECTA") # Separadas por comas en el .env
    if urls_env:
        print("🌐 Detectadas URLs de OneDrive. Descargando archivos a la carpeta de trabajo...")
        os.makedirs(RUTA_TRABAJO, exist_ok=True)
        for i, url in enumerate(urls_env.split(",")):
            url = url.strip()
            if url:
                try:
                    # Forzar nombre secuencial si no se puede extraer de la URL
                    nombre_archivo = f"Control Ingredientes_Descargado_{i}.xlsx"
                    ruta_destino = os.path.join(RUTA_TRABAJO, nombre_archivo)
                    
                    respuesta = requests.get(url, allow_redirects=True)
                    if respuesta.status_code == 200:
                        with open(ruta_destino, 'wb') as f:
                            f.write(respuesta.content)
                        print(f"  ✅ Descargado: {nombre_archivo}")
                    else:
                        print(f"  ❌ No se pudo descargar desde la URL. Código: {respuesta.status_code}")
                except Exception as e:
                    print(f"  ❌ Error en descarga: {e}")

def pipeline_etl_anual_mensual():
    print("🚀 Iniciando el Pipeline ETL de Dietas e Ingredientes...")
    
    # Intentar descargar si estamos en entorno nube
    descargar_archivos_desde_url()
    
    if not os.path.isdir(RUTA_TRABAJO):
        print(f"❌ ERROR CRÍTICO: No se encontró la carpeta de trabajo: {RUTA_TRABAJO}")
        sys.exit(1)

    try:
        engine = conectar_postgres()
    except Exception as e:
        print(f"❌ ERROR DE CONEXIÓN A POSTGRESQL: Detalle: {e}")
        sys.exit(1)
    
    # Buscar tanto los locales originales como los descargados por URL
    patron_archivos = os.path.join(RUTA_TRABAJO, "Control Ingredientes*.xlsx")
    archivos_anuales = glob.glob(patron_archivos)
    
    if not archivos_anuales:
        print(f"⚠️ ADVERTENCIA: No se encontraron archivos en {RUTA_TRABAJO}")
        return
    
    print(f"📂 Archivos anuales detectados: {[os.path.basename(a) for a in archivos_anuales]}")
    
    for ruta_excel in archivos_anuales:
        nombre_archivo = os.path.basename(ruta_excel)
        print(f"\n📖 Leyendo Archivo Anual: {nombre_archivo}")
        
        try:
            excel_objeto = pd.ExcelFile(ruta_excel)
            hojas_disponibles = excel_objeto.sheet_names
        except Exception as e:
            print(f"❌ ERROR AL ABRIR EL ARCHIVO [{nombre_archivo}]: Detalle: {e}")
            continue 
        
        for nombre_hoja in hojas_disponibles:
            if not any(char.isdigit() for char in nombre_hoja):
                print(f"  ⚠️ Saltando pestaña informativa/no operativa: {nombre_hoja}")
                continue
                
            print(f"  └── 🔄 Procesando pestaña mensual: [{nombre_hoja}]")
            
            try:
                # --- EXTRACCIÓN CRUDA ---
                df_raw = pd.read_excel(ruta_excel, sheet_name=nombre_hoja, skiprows=9)
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                
                if 'Clave ITEM' not in df_raw.columns or df_raw.empty:
                    print(f"    ⚠️ Estructura inválida en la hoja [{nombre_hoja}]. Saltando...")
                    continue
                
                # Filtrar renglones vacíos
                df_raw = df_raw[df_raw['Almacen'].notna() & (df_raw['Almacen'].astype(str).str.strip() != '')]
                df_raw = df_raw[df_raw['Clave ITEM'].notna() & (df_raw['Clave ITEM'].astype(str).str.strip() != '')]
                
                if df_raw.empty:
                    print(f"    ⚠️ La hoja [{nombre_hoja}] no contiene registros válidos. Saltando...")
                    continue

                # --- PASO 1: Inventario Mensual ---
                df_inv = df_raw.iloc[:, 0:15].copy()
                columnas_map = {
                    'Almacen': 'almacen', 'Clave ITEM': 'clave_item', 'Ingrediente': 'ingrediente',
                    'UM': 'um', 'Ubicacion': 'ubicacion', 'Tipo': 'tipo', 'Lote': 'lote',
                    'Fecha Ingreso': 'fecha_ingreso', 'Dias Estadía en Almacén': 'dias_estadia',
                    'Exis Inicial': 'exis_inicial', 'Exis Final': 'exis_final'
                }
                
                df_inv = df_inv[[c for c in columnas_map.keys() if c in df_inv.columns]].rename(columns=columnas_map)
                
                df_inv['exis_inicial'] = pd.to_numeric(df_inv['exis_inicial'].replace('POR ACEPTAR', 0), errors='coerce').fillna(0)
                df_inv['exis_final'] = pd.to_numeric(df_inv['exis_final'].replace('#¡VALOR!', 0), errors='coerce').fillna(0)
                df_inv['consumo_total'] = df_inv['exis_inicial'] - df_inv['exis_final']
                df_inv['clave_item'] = df_inv['clave_item'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_inv['lote'] = df_inv['lote'].fillna('SIN LOTE').astype(str).str.strip()
                df_inv['periodo_id'] = nombre_hoja
                
                # --- PASO 2: Retiros Diarios (Unpivot) ---
                df_matriz = pd.read_excel(ruta_excel, sheet_name=nombre_hoja, header=[8, 9])
                df_matriz = df_matriz.iloc[df_raw.index].copy()
                
                registros_retiros = []
                for i in range(15, df_matriz.shape[1], 2):
                    col_cant = df_matriz.columns[i]
                    fecha_retiro = col_cant[0]
                    
                    df_dia = pd.DataFrame({
                        'almacen': df_raw['Almacen'],
                        'clave_item': df_raw['Clave ITEM'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip(),
                        'lote': df_raw['Lote'].fillna('SIN LOTE').astype(str).str.strip(),
                        'fecha_retiro': pd.to_datetime(fecha_retiro, errors='coerce'),
                        'cantidad_retiro': pd.to_numeric(df_matriz.iloc[:, i], errors='coerce'),
                        'folio_ie': df_matriz.iloc[:, i+1].fillna('SIN FOLIO').astype(str).str.strip()
                    })
                    
                    df_dia = df_dia[df_dia['cantidad_retiro'] > 0]
                    if not df_dia.empty:
                        registros_retiros.append(df_dia)
                        
                df_retiros = pd.concat(registros_retiros, ignore_index=True) if registros_retiros else pd.DataFrame()
                if not df_retiros.empty:
                    df_retiros['periodo_id'] = nombre_hoja

                # --- PASO 3: Carga Idempotente ---
                try:
                    with engine.begin() as conexion:
                        query_ids = text("SELECT id FROM fact_inventario_mensual WHERE periodo_id = :periodo")
                        ids_a_borrar = [row[0] for row in conexion.execute(query_ids, {"periodo": nombre_hoja})]
                        
                        if ids_a_borrar:
                            conexion.execute(text("DELETE FROM fact_retiros_diarios WHERE inventario_id = ANY(:ids)"), {"ids": ids_a_borrar})
                            conexion.execute(text("DELETE FROM fact_inventario_mensual WHERE id = ANY(:ids)"), {"ids": ids_a_borrar})
                    
                    # Insertar maestro
                    df_inv.to_sql('fact_inventario_mensual', con=engine, if_exists='append', index=False)
                    
                    # Vincular y cargar detalle
                    if not df_retiros.empty:
                        df_nuevos_ids = pd.read_sql(
                            text("SELECT id, periodo_id, almacen, clave_item, lote FROM fact_inventario_mensual WHERE periodo_id = :periodo"),
                            con=engine, params={"periodo": nombre_hoja}
                        )
                        df_nuevos_ids['clave_item'] = df_nuevos_ids['clave_item'].astype(str)
                        df_nuevos_ids['lote'] = df_nuevos_ids['lote'].astype(str)
                        
                        df_retiros_enlazados = pd.merge(df_retiros, df_nuevos_ids, on=['periodo_id', 'almacen', 'clave_item', 'lote'], how='inner')
                        df_retiros_enlazados = df_retiros_enlazados.rename(columns={'id': 'inventario_id'})
                        
                        if not df_retiros_enlazados.empty:
                            columnas_finales = ['almacen', 'clave_item', 'lote', 'fecha_retiro', 'cantidad_retiro', 'folio_ie', 'periodo_id', 'inventario_id']
                            df_retiros_enlazados[columnas_finales].to_sql('fact_retiros_diarios', con=engine, if_exists='append', index=False)
                            
                    print(f"    ✅ Hoja [{nombre_hoja}] integrada correctamente.")
                    
                except Exception as error_sql:
                    print(f"    ❌ ERROR DE BASE DE DATOS EN [{nombre_hoja}]: {error_sql}")
                    continue

            except Exception as error_transformacion:
                print(f"    ❌ ERROR DE PROCESAMIENTO EN [{nombre_hoja}]: {error_transformacion}")
                continue
                
    print("\n🏁 ¡Pipeline finalizado con éxito!")

if __name__ == "__main__":
    pipeline_etl_anual_mensual()