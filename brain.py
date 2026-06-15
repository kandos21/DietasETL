import os
import glob
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# =================================================================
# CONFIGURACIÓN DE PARÁMETROS - CARPETA ANUAL EN ONEDRIVE
# =================================================================
RUTA_CARPETA_ONEDRIVE = r"C:\Users\candido.lopez.i\Documents\OneDrive - Servicio Nacional de Sanidad, Inocuidad y Calidad Agroalimentaria (SENASICA)\POWER BI\Almacen-Dietas\2026"

# Cargar las variables ocultas del archivo .env
load_dotenv()

def conectar_postgres():
    usuario = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    db = os.getenv("PG_DATABASE")

    # Forzamos opciones de búsqueda para asegurar el esquema 'public'
    cadena_conexion = f"postgresql+psycopg2://{usuario}:{password}@{host}:{port}/{db}"
    return create_engine(cadena_conexion, connect_args={"options": "-c search_path=public"})

def pipeline_etl_anual_mensual():
    print("🚀 Iniciando el Pipeline ETL de Dietas e Ingredientes...")
    
    if not os.path.isdir(RUTA_CARPETA_ONEDRIVE):
        print(f"❌ ERROR CRÍTICO: No se encontró la carpeta en la ruta especificada: {RUTA_CARPETA_ONEDRIVE}")
        sys.exit(1)

    try:
        engine = conectar_postgres()
    except Exception as e:
        print(f"❌ ERROR DE CONEXIÓN A POSTGRESQL: No se pudo conectar al servidor. Detalle: {e}")
        sys.exit(1)
    
    patron_archivos = os.path.join(RUTA_CARPETA_ONEDRIVE, "Control Ingredientes*.xlsx")
    archivos_anuales = glob.glob(patron_archivos)
    
    if not archivos_anuales:
        print(f"⚠️ ADVERTENCIA: No se encontraron archivos que coincidan con 'Control Ingredientes*.xlsx' en {RUTA_CARPETA_ONEDRIVE}")
        return
    
    print(f"📂 Archivos anuales detectados: {[os.path.basename(a) for a in archivos_anuales]}")
    
    for ruta_excel in archivos_anuales:
        nombre_archivo = os.path.basename(ruta_excel)
        print(f"\n📖 Leyendo Archivo Anual: {nombre_archivo}")
        
        try:
            excel_objeto = pd.ExcelFile(ruta_excel)
            hojas_disponibles = excel_objeto.sheet_names
        except Exception as e:
            print(f"❌ ERROR AL ABRIR EL ARCHIVO [{nombre_archivo}]: ¿Está dañado o abierto por otro usuario? Detalle: {e}")
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
                    print(f"    ⚠️ Estructura inválida o vacía en la hoja [{nombre_hoja}]. Saltando...")
                    continue
                
                # 🔥 SOLUCIÓN FILAS BASURA: Filtrar renglones donde 'Almacen' o 'Clave ITEM' estén vacíos u nulos
                df_raw = df_raw[df_raw['Almacen'].notna() & (df_raw['Almacen'].astype(str).str.strip() != '')]
                df_raw = df_raw[df_raw['Clave ITEM'].notna() & (df_raw['Clave ITEM'].astype(str).str.strip() != '')]
                
                if df_raw.empty:
                    print(f"    ⚠️ La hoja [{nombre_hoja}] no contiene registros válidos después de filtrar notas. Saltando...")
                    continue

                # ----------------------------------------------------------------
                # PASO 1: Transformación del Inventario Mensual (Bloque Izquierdo)
                # ----------------------------------------------------------------
                df_inv = df_raw.iloc[:, 0:15].copy()
                
                columnas_map = {
                    'Almacen': 'almacen', 'Clave ITEM': 'clave_item', 'Ingrediente': 'ingrediente',
                    'UM': 'um', 'Ubicacion': 'ubicacion', 'Tipo': 'tipo', 'Lote': 'lote',
                    'Fecha Ingreso': 'fecha_ingreso', 'Dias Estadía en Almacén': 'dias_estadia',
                    'Exis Inicial': 'exis_inicial', 'Exis Final': 'exis_final'
                }
                
                df_inv = df_inv[[c for c in columnas_map.keys() if c in df_inv.columns]].rename(columns=columnas_map)
                
                # Sanitización de datos
                df_inv['exis_inicial'] = pd.to_numeric(df_inv['exis_inicial'].replace('POR ACEPTAR', 0), errors='coerce').fillna(0)
                df_inv['exis_final'] = pd.to_numeric(df_inv['exis_final'].replace('#¡VALOR!', 0), errors='coerce').fillna(0)
                df_inv['consumo_total'] = df_inv['exis_inicial'] - df_inv['exis_final']
                df_inv['clave_item'] = df_inv['clave_item'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_inv['lote'] = df_inv['lote'].fillna('SIN LOTE').astype(str).str.strip()
                df_inv['periodo_id'] = nombre_hoja
                
                # ----------------------------------------------------------------
                # PASO 2: Transformación de Retiros Diarios (Bloque Derecho - Unpivot)
                # ----------------------------------------------------------------
                df_matriz = pd.read_excel(ruta_excel, sheet_name=nombre_hoja, header=[8, 9])
                # Sincronizar las filas de la matriz con el df_raw ya filtrado sin notas
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

                # ----------------------------------------------------------------
                # PASO 3: Carga Idempotente con Manejo de IDs Autoincrementales
                # ----------------------------------------------------------------
                try:
                    with engine.begin() as conexion:
                        query_ids = text("SELECT id FROM fact_inventario_mensual WHERE periodo_id = :periodo")
                        ids_a_borrar = [row[0] for row in conexion.execute(query_ids, {"periodo": nombre_hoja})]
                        
                        if ids_a_borrar:
                            conexion.execute(
                                text("DELETE FROM fact_retiros_diarios WHERE inventario_id = ANY(:ids)"),
                                {"ids": ids_a_borrar}
                            )
                            conexion.execute(
                                text("DELETE FROM fact_inventario_mensual WHERE id = ANY(:ids)"),
                                {"ids": ids_a_borrar}
                            )
                    
                    # Insertar inventario limpio
                    df_inv.to_sql('fact_inventario_mensual', con=engine, if_exists='append', index=False)
                    
                    # Vincular retiros con los nuevos IDs creados
                    if not df_retiros.empty:
                        df_nuevos_ids = pd.read_sql(
                            text("SELECT id, periodo_id, almacen, clave_item, lote FROM fact_inventario_mensual WHERE periodo_id = :periodo"),
                            con=engine,
                            params={"periodo": nombre_hoja}
                        )
                        df_nuevos_ids['clave_item'] = df_nuevos_ids['clave_item'].astype(str)
                        df_nuevos_ids['lote'] = df_nuevos_ids['lote'].astype(str)
                        
                        df_retiros_enlazados = pd.merge(
                            df_retiros, 
                            df_nuevos_ids, 
                            on=['periodo_id', 'almacen', 'clave_item', 'lote'], 
                            how='inner'
                        )
                        
                        df_retiros_enlazados = df_retiros_enlazados.rename(columns={'id': 'inventario_id'})
                        
                        if not df_retiros_enlazados.empty:
                            columnas_finales = ['almacen', 'clave_item', 'lote', 'fecha_retiro', 'cantidad_retiro', 'folio_ie', 'periodo_id', 'inventario_id']
                            df_retiros_enlazados[columnas_finales].to_sql('fact_retiros_diarios', con=engine, if_exists='append', index=False)
                            
                    print(f"    ✅ Hoja [{nombre_hoja}] integrada y vinculada correctamente sin renglones basura.")
                    
                except Exception as error_sql:
                    print(f"    ❌ ERROR DE BASE DE DATOS EN LA HOJA [{nombre_hoja}]: Detalle: {error_sql}")
                    continue

            except Exception as error_transformacion:
                print(f"    ❌ ERROR DE PROCESAMIENTO EN LA HOJA [{nombre_hoja}]: Detalle: {error_transformacion}")
                continue
                
    print("\n🏁 ¡Pipeline finalizado! Todos los archivos analizados y corregidos.")

if __name__ == "__main__":
    pipeline_etl_anual_mensual()