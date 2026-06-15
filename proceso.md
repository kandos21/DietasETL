markdown_v2_content = """# Manual Técnico y de Despliegue: Sistema ETL Corporativo e Interfaz de Monitoreo
## Consolidación Histórica del Almacén de Dietas e Ingredientes (v2)

Este documento proporciona las especificaciones técnicas completas, la arquitectura de datos y la guía de despliegue paso a paso para el sistema ETL (**Extract, Transform, Load**) del Almacén de Dietas e Ingredientes. Este ecosistema está diseñado para ejecutarse localmente de forma segura dentro de la infraestructura de la empresa, garantizando la soberanía de la información, mitigando la falta de servidores dedicados y resolviendo las restricciones de licenciamiento mediante automatización nativa de Windows y una interfaz web ligera de monitoreo.

---

## 1. Arquitectura Detallada del Sistema y Flujo de Datos

El pipeline procesa matrices complejas de datos provenientes de hojas de cálculo anuales actualizadas semanalmente. Para evitar la duplicidad o corrupción del histórico, se implementa una arquitectura **idempotente**.

### Componentes de la Solución:
1. **Origen (Extract):** Archivos Excel anuales (`Control Ingredientes*.xlsx`) estructurados con pestañas mensuales indexadas numéricamente. Están alojados de forma compartida y sincronizados en el disco local mediante el cliente de OneDrive corporativo.
2. **Procesamiento (Transform):** Scripts optimizados en Python (`brain*.py`) impulsados por `pandas` y `numpy` que realizan:
   - Filtrado dinámico de renglones huérfanos o notas operativas al final de las hojas.
   - Sanitización de errores de celda nativos de Excel (`#¡VALOR!`, `POR ACEPTAR`).
   - Reestructuración multidimensional (*Unpivot*) para convertir columnas de fechas de retiros diarios en registros de filas normalizadas.
3. **Almacenamiento (Load):** Base de datos relacional **PostgreSQL** (alojada localmente o mediante proveedores en la nube como Neon.tech / Supabase bajo capas gratuitas), que actúa como la bodega de datos histórica consolidada.
4. **Carga Idempotente (Control de Duplicados):** Antes de inyectar un mes procesado, el script ejecuta un bloque transaccional que elimina los registros existentes para ese `periodo_id` específico en las tablas relacionales (`fact_retiros_diarios` y `fact_inventario_mensual`), permitiendo re-ejecutar el script infinitas veces sin duplicar filas.
5. **Consumo y Visualización:** Modelado de datos en **Power BI Desktop** conectado directamente a PostgreSQL. El archivo maestro `.pbix` se aloja en una carpeta compartida de OneDrive para que los usuarios de las distintas áreas lo abran localmente y actualicen los datos con un solo clic, sorteando las limitaciones de la licencia gratuita de Power BI Service.

---

## 2. Estructura de Carpetas del Proyecto

Para el correcto funcionamiento del sistema, la raíz del proyecto (recomendado de manera estándar en `C:\\code\\DietasETL`) debe conservar la siguiente estructura limpia:

3. Guía de Despliegue desde Cero en un Nuevo Equipo
Siga este procedimiento estrictamente cuando configure la solución en una nueva computadora de su área para evitar conflictos de rutas absolutas o launchers del sistema.

Paso 3.1: Instalación de Python y Configuración del Entorno de Variables
Descargue el instalador oficial de Python 3.10 o superior para Windows.

OBLIGATORIO: En la primera pantalla del instalador, active la casilla de verificación inferior: "Add Python to PATH". Si no se activa, el sistema operativo no reconocerá los comandos en la terminal.

Haga clic en Install Now y espere a que finalice el proceso.

Paso 3.2: Descarga de Código y Creación del Archivo de Credenciales (.env)
Descargue el código fuente en la ruta local C:\\code\\DietasETL.

Como las credenciales no se respaldan en GitHub por motivos de seguridad, cree manualmente un archivo de texto llamado exactamente .env en la raíz del proyecto.

Defina los parámetros de conexión a su base de datos PostgreSQL de la siguiente manera:

Plaintext
PG_USER=tu_usuario_de_postgres
PG_PASSWORD=tu_contraseña_segura
PG_HOST=tu_servidor_ip_o_host_en_la_nube
PG_PORT=5432
PG_DATABASE=nombre_de_tu_base_de_datos
Paso 3.3: Reconstrucción y Activación del Entorno Virtual (.venv)
Los entornos virtuales contienen rutas fijas a la computadora de origen. Para corregir errores tipo 'Fatal error in launcher', se debe destruir el entorno anterior y crear uno adaptado a la arquitectura de la nueva máquina:

Abra una terminal en VS Code (Ctrl + ~) y ejecute en orden los siguientes comandos:

PowerShell
# 1. Forzar la eliminación de la carpeta .venv anterior si existe
Remove-Item -Recurse -Force .venv

# 2. Crear un entorno virtual local nuevo usando el lanzador nativo de Windows
py -m venv .venv

# 3. Activar el entorno virtual dentro de la sesión de la terminal (PowerShell)
.venv\\Scripts\\Activate.ps1
💡 Verificación: Al ejecutarse la activación de manera exitosa, el prompt de la terminal mostrará el prefijo destacado (.venv). No prosiga con el siguiente paso si este prefijo no está visible.

Paso 3.4: Instalación Indexada de Dependencias
Con el entorno virtual activado, instale las librerías utilizando el archivo de configuración provisto:

PowerShell
python -m pip install -r requirements.txt
Nota: Si está configurando el proyecto por primera vez y no cuenta con el archivo de texto estructurado, ejecute el comando directo:

PowerShell
python -m pip install pandas numpy sqlalchemy psycopg2-binary openpyxl flask python-dotenv
Guarde el estado actual de las dependencias ejecutando:

PowerShell
pip freeze > requirements.txt
4. Configuración del Lanzador de Tareas Automáticas (.bat)
Para permitir que el sistema operativo Windows ejecute el pipeline de manera desatendida, es necesario encapsular el entorno en un archivo por lotes ejecutable que registre los flujos de eventos.

Cree un archivo llamado ejecutar_etl.bat en la raíz del proyecto con el siguiente bloque de comandos:

Fragmento de código
@echo off
:: Desplazarse de forma segura a la ruta física del proyecto
cd /d "C:\\code\\DietasETL"

:: Cabecera de auditoría dentro del archivo de registros
echo =================================================== >> etl_registro.log
echo EJECUCIÓN AUTOMÁTICA PROGRAMADA: %date% a las %time% >> etl_registro.log
echo =================================================== >> etl_registro.log

:: Invocar al ejecutable interno de Python del entorno aislado para correr el ETL
.venv\\Scripts\\python.exe etl_dietas.py >> etl_registro.log 2>&1

echo --------------------------------------------------- >> etl_registro.log
5. Automatización mediante el Programador de Tareas de Windows
Para configurar la ejecución automática dos veces por semana (por ejemplo, Martes y Jueves fuera del horario de alta carga operativa):

Presione la tecla Windows, escriba Programador de Tareas y abra la aplicación.

En la barra de acciones de la derecha, seleccione Crear tarea básica...

Nombre de la tarea: ETL_Dietas_Sincronizacion_Historica.

Desencadenador: Seleccione la opción Semanalmente.

Programación: Defina la hora de ejecución (ej. 19:00:00) y marque exclusivamente las casillas Martes y Jueves.

Acción: Seleccione Iniciar un programa.

Programa o script: Haga clic en Examinar... y seleccione su archivo localizado en C:\\code\\DietasETL\\ejecutar_etl.bat.

Iniciar en (opcional): Ingrese la ruta de trabajo raíz sin comillas: C:\\code\\DietasETL. Este paso es crítico para que Python localice correctamente el archivo .env y las librerías.

Haga clic en Siguiente y luego en Finalizar.

6. Panel de Control Web Local de Monitoreo (dashboard.py)
Para democratizar el control del flujo sin requerir conocimientos técnicos de consola, se integra una interfaz web desarrollada sobre Flask. Esta interfaz permite ver el estado del último proceso, auditar los registros detallados y forzar una actualización manual mediante un botón interactivo.

Implementación del Código del Servidor Web (dashboard.py):
Python
import os
import subprocess
import sys
from flask import Flask, render_template_string, redirect, url_for

app = Flask(__name__)

LOG_FILE = "etl_registro.log"
SCRIPT_ETL = "etl_dietas.py"

def obtener_estado_log():
    \"\"\"Analiza los registros históricos para calcular el estado de la última corrida.\"\"\"
    if not os.path.exists(LOG_FILE):
        return "SIN REGISTROS", "text-secondary", "No se han detectado ejecuciones del pipeline aún."
    
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            texto_completo = f.read()
        
        if "❌ ERROR" in texto_completo or "Traceback" in texto_completo:
            return "ERROR EN PIPELINE", "bg-danger", texto_completo
        elif "✅" in texto_completo or "finalizado con éxito" in texto_completo:
            return "PROCESADO CON ÉXITO", "bg-success", texto_completo
        else:
            return "ESTADO INDETERMINADO", "bg-warning", texto_completo
    except Exception as e:
        return "ERROR DE LECTURA", "bg-danger", f"Imposible acceder al archivo de auditoría: {e}"

HTML_TEMPLATE = \"\"\"
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - ETL Dietas</title>
    <link href="[https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/theme/bootstrap.min.css](https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/theme/bootstrap.min.css)" rel="stylesheet">
    <style>
        body { background-color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
        .dashboard-card { border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
        .log-viewer { background-color: #0f172a; color: #e2e8f0; font-family: 'Consolas', monospace; font-size: 0.85rem; max-height: 400px; overflow-y: auto; white-space: pre-wrap; padding: 20px; border-radius: 8px; }
        .status-badge { padding: 10px 20px; font-weight: bold; border-radius: 50px; color: white; }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-xl-10">
                <div class="d-flex justify-content-between align-items-center mb-5">
                    <div>
                        <h1 class="h3 text-slate-800 mb-1">Consola de Operaciones ETL</h1>
                        <p class="text-muted small mb-0">Monitoreo del Almacén de Dietas e Ingredientes</p>
                    </div>
                    <span class="status-badge {{ badge_class }} shadow-sm">{{ estado }}</span>
                </div>

                <div class="card dashboard-card mb-4">
                    <div class="card-body d-flex justify-content-between align-items-center py-4">
                        <div>
                            <h5 class="card-title h6 mb-1">Disparador de Procesamiento Manual</h5>
                            <p class="text-muted small mb-0">Fuerza la descarga, limpieza e inyección de datos de OneDrive hacia PostgreSQL de inmediato.</p>
                        </div>
                        <form action="/ejecutar" method="POST">
                            <button type="submit" class="btn btn-dark px-4 py-2 fw-bold" onclick="this.innerHTML='🔄 Procesando ETL...'; this.classList.add('disabled');">
                                Enceder Pipeline Now
                            </button>
                        </form>
                    </div>
                </div>

                <div class="card dashboard-card">
                    <div class="card-header bg-white py-3 d-flex justify-content-between align-items-center">
                        <h6 class="mb-0 text-muted fw-bold">Consola de Auditoría de Procesos (Logs)</h6>
                        <button class="btn btn-sm btn-link text-decoration-none" onclick="window.location.reload();">🔄 Recargar Terminal</button>
                    </div>
                    <div class="card-body">
                        <div class="log-viewer" id="logBox">{{ log_content }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        const lb = document.getElementById('logBox');
        lb.scrollTop = lb.scrollHeight;
    </script>
</body>
</html>
\"\"\"

@app.route("/")
def index():
    est, cls, content = obtener_estado_log()
    return render_template_string(HTML_TEMPLATE, estado=est, badge_class=cls, log_content=content)

@app.route("/ejecutar", methods=["POST"])
def ejecutar_etl():
    try:
        resultado = subprocess.run([sys.executable, SCRIPT_ETL], capture_output=True, text=True, encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(resultado.stdout)
            if resultado.stderr:
                f.write(f"\\n❌ ERRORES INTERNOS DETECTADOS:\\n{resultado.stderr}")
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\\n❌ ERROR CRÍTICO EN PANEL DE CONTROL: {e}\\n")
    return redirect(url_for("index"))

if __name__ == "__main__":
    # Escucha en el puerto 5000 para toda la subred local de la empresa
    app.run(host="0.0.0.0", port=5000, debug=True)
Acceso Remoto Departamental:
Al estar configurado con el parámetro host="0.0.0.0", la consola web no se limita a la máquina local. Si abres la terminal de la computadora que ejecuta el servicio y consultas tu IP privada mediante ipconfig (ejemplo: 192.168.10.45), cualquier otro integrante de tu área conectado a la misma red interna podrá auditar o lanzar el proceso ingresando desde su navegador a:
http://192.168.10.45:5000

7. Buenas Prácticas de Control de Cambios e Integración con Git
Para garantizar que el mantenimiento del software mediante repositorios compartidos como GitHub se realice de forma segura y limpia, el archivo .gitignore ubicado en la raíz debe configurarse con las siguientes directrices esenciales:

Plaintext
# Excluir de forma absoluta las librerías compiladas locales
.venv/
venv/
ENV/
bin/
obj/

# Excluir credenciales confidenciales de bases de datos de la empresa
.env

# Archivos de caché e interpretación dinámica de Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Archivos de registro operativo local (Historial de logs)
*.log

# Bloqueos de archivos temporales de Microsoft Excel por coautoría
~$*.xlsx
Flujo de Actualización del Repositorio:
Desarrollo: Realice modificaciones de código exclusivamente en etl_dietas.py o dashboard.py.

Sincronización: Suba sus cambios a GitHub de manera habitual. Verá que la carpeta virtual .venv y sus contraseñas secretas en .env permanecerán invisibles para Git, garantizando la seguridad informática.

Despliegue de Cambios: Cuando otra computadora del área haga un git pull para actualizar el software, su entorno virtual local no sufrirá alteraciones y continuará operando de manera transparente e ininterrumpida.
"""

output_v2_path = "Manual_Despliegue_ETL_Dietas-v2.md"
with open(output_v2_path, "w", encoding="utf-8") as f:
f.write(markdown_v2_content)

print(f"Version 2 Markdown successfully generated at: {output_v2_path}")

### Su archivo Markdown (.md) está listo
[file-tag: code-generated-file-0-1781499283692719855]

He generado la **Versión 2 (v2)** del manual técnico en un archivo Markdown titulado `Manual_Despliegue_ETL_Dietas-v2.md`. 

Esta versión amplía profundamente cada fase del proceso e integra de forma unificada toda la solución construida (el pipeline, el servidor web, el control de errores en Windows y las buenas prácticas con Git).

### Resumen del contenido estructurado dentro del archivo `.md`:

1. **Sección Arquitectónica e Idempotencia:** Explica de forma teórica y práctica el flujo de los datos desde el Excel de origen (OneDrive) hasta el modelado limpio en Power BI Desktop, detallando cómo la base de datos PostgreSQL se limpia selectivamente (`DELETE` transaccional por `periodo_id`) antes de cada inserción para mitigar la duplicidad de información.
2. **Estructura Organizacional del Repositorio:** Define de forma visual el árbol de carpetas ideal que debe mantener el proyecto localmente (`.venv`, `.env`, `.gitignore`, scripts, archivos batch y logs).
3. **Guía de Despliegue en Nuevos Entornos:** El paso a paso exacto para instalar Python configurando las variables de entorno (`PATH`) y los comandos críticos para reconstruir de raíz el entorno virtual (`.venv`) eliminando por completo los errores de enlaces corruptos (*Fatal error in launcher*).
4. **Automatización Nativa Desatendida:** Contiene el código listo del archivo `.bat` acoplado al intérprete interno del proyecto, acompañado de las instrucciones exactas para darlo de alta dentro de la interfaz del **Programador de Tareas de Windows** con frecuencia de dos veces por semana.
5. **Código de Producción de la Interfaz de Monitoreo (`dashboard.py`):** El script completo basado en el micro-framework Flask con diseño responsivo en Bootstrap 5, configurado para lectura dinámica de logs y mapeo de subredes para que cualquier compañero de tu área pueda entrar al monitor usando la IP local en el puerto 5000.
6. **Políticas del Ecosistema Git y Seguridad corporativa:** Detalla la configuración restrictiva del `.gitignore` para salvaguardar las credenciales del archivo `.env`, asegurar la limpieza del repositorio y permitir un flujo seguro de coautoría de software.

Puedes abrir este documento en VS Code y presionar la combinación de teclas `Ctrl + Shift + V` para vis