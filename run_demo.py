import os
import sys
import subprocess
from sentinel.database.seed import seed_data
from sentinel.database.connection import DEFAULT_DB_PATH

def main():
    print("=" * 60)
    print("           🛡️ AGENTE VIGÍA — INICIANDO SISTEMA 🛡️")
    print("=" * 60)

    print(f"[*] Paso 1: Inicializando y sembrando base de datos SQLite en: {DEFAULT_DB_PATH}...")
    try:
        seed_data(DEFAULT_DB_PATH)
        print("[+] Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"[-] Error al sembrar la base de datos: {e}")
        sys.exit(1)

    print("\n[*] Paso 2: Iniciando servidor del Dashboard Streamlit...")
    print("[*] Comando: streamlit run sentinel/dashboard/app.py")
    print("[*] (El navegador debería abrirse automáticamente)")
    print("=" * 60)
    
    # Run streamlit as a subprocess
    app_path = os.path.join(
        os.path.dirname(__file__), 
        "sentinel", "dashboard", "app.py"
    )
    
    # Add project root directory to PYTHONPATH for the subprocess
    env = os.environ.copy()
    project_root = os.path.dirname(os.path.abspath(__file__))
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    
    # We execute using python interpreter's module to avoid path problems
    subprocess.run(["streamlit", "run", app_path], env=env)


if __name__ == "__main__":
    main()
