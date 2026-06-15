import os
import subprocess
import sys
from flask import Flask, render_template_string, redirect, url_for

app = Flask(__name__)

# Rutas de los archivos (asume que están en la misma carpeta)
LOG_FILE = "etl_registro.log"
SCRIPT_ETL = "etl_dietas.py"

def obtener_estado_log():
    """Analiza el archivo log para determinar el estado del último proceso."""
    if not os.path.exists(LOG_FILE):
        return "SIN REGISTROS", "text-secondary", "No se ha ejecutado el ETL aún."
    
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lineas = f.readlines()
            
        texto_completo = "".join(lineas)
        
        # Buscar palabras clave en el log para determinar el estado
        if "❌ ERROR" in texto_completo or "Traceback" in texto_completo:
            return "ERROR", "bg-danger", texto_completo
        elif "✅" in texto_completo or "¡Pipeline finalizado con éxito!" in texto_completo:
            return "ÉXITO", "bg-success", texto_completo
        else:
            return "DESCONOCIDO", "bg-warning", texto_completo
    except Exception as e:
        return "ERROR DE LECTURA", "bg-danger", f"No se pudo leer el log: {e}"

# Plantilla HTML integrada con diseño limpio y responsivo
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - ETL Dietas</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/theme/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .dashboard-card { border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .log-viewer { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Courier New', Courier, monospace; font-size: 0.9rem; max-height: 450px; overflow-y: auto; white-space: pre-wrap; border-radius: 8px; padding: 15px; }
        .status-badge { padding: 8px 16px; font-weight: 600; border-radius: 30px; color: white; display: inline-block; }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-lg-10">
                
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <h1 class="h3 text-dark mb-1">Monitor de Proceso ETL</h1>
                        <p class="text-muted small mb-0">Almacén de Dietas e Ingredientes</p>
                    </div>
                    <div>
                        <span class="status-badge {{ badge_class }} shadow-sm">
                            Estado Actual: {{ estado }}
                        </span>
                    </div>
                </div>

                <div class="card dashboard-card mb-4">
                    <div class="card-body d-flex justify-content-between align-items-center py-4">
                        <div>
                            <h5 class="card-title mb-1">Control Manual</h5>
                            <p class="text-muted small mb-0">Haz clic para descargar los archivos de OneDrive y actualizar PostgreSQL inmediatamente.</p>
                        </div>
                        <form action="/ejecutar" method="POST">
                            <button type="submit" class="btn btn-primary px-4 py-2 fw-bold shadow-sm" onclick="this.innerHTML='🔄 Procesando ETL...'; this.classList.add('disabled');">
                                🚀 Ejecutar ETL Ahora
                            </button>
                        </form>
                    </div>
                </div>

                <div class="card dashboard-card">
                    <div class="card-header bg-white border-bottom py-3 d-flex justify-content-between align-items-center">
                        <h5 class="mb-0 text-secondary">Historial de Ejecución e Inspección de Errores</h5>
                        <button class="btn btn-sm btn-outline-secondary" onclick="window.location.reload();">🔄 Refrescar Vista</button>
                    </div>
                    <div class="card-body">
                        <div class="log-viewer shadow-inner" id="logBox">{% if log_content %}{{ log_content }}{% else %}El archivo de log está vacío o no se ha generado.{% endif %}</div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
        // Auto-scroll al final del log para ver siempre lo último que pasó
        const logBox = document.getElementById('logBox');
        logBox.scrollTop = logBox.scrollHeight;
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    estado, badge_class, log_content = obtener_estado_log()
    return render_template_string(HTML_TEMPLATE, estado=estado, badge_class=badge_class, log_content=log_content)

@app.route("/ejecutar", methods=["POST"])
def ejecutar_etl():
    try:
        # Ejecuta tu script original de python usando el mismo intérprete actual
        # Redirecciona la salida para que se guarde en tu archivo log
        print("🛠️ Ejecución manual disparada desde la interfaz web...")
        
        # Ejecutamos el proceso de manera síncrona para que la página cargue cuando termine
        resultado = subprocess.run([sys.executable, SCRIPT_ETL], capture_output=True, text=True, encoding="utf-8")
        
        # Escribimos los flujos de salida directamente en el log para actualizar la vista
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(resultado.stdout)
            if resultado.stderr:
                f.write(f"\n❌ ERRORES DEL SISTEMA:\n{resultado.stderr}")
                
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n❌ CRITICAL INTERFACE ERROR: No se pudo lanzar el script: {e}\n")
            
    return redirect(url_for("index"))

if __name__ == "__main__":
    # Cambia host a '0.0.0.0' para que otras computadoras de tu área puedan entrar usando tu IP
    app.run(host="0.0.0.0", port=5000, debug=True)