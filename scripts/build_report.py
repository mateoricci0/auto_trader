"""
Convierte notebooks/fase0_analisis.ipynb → reports/fase0_reporte.html.

Prerrequisito: run_oos_final.py completado (reports/fase0_oos.parquet existente).
Uso: python scripts/build_report.py
"""
import subprocess
import sys
from pathlib import Path

ROOT     = Path(__file__).parent.parent
NOTEBOOK = ROOT / "notebooks" / "fase0_analisis.ipynb"
OUTPUT   = ROOT / "reports" / "fase0_reporte.html"


def main():
    if not NOTEBOOK.exists():
        print(f"ERROR: no se encuentra el notebook: {NOTEBOOK}")
        sys.exit(1)

    oos_parquet = ROOT / "reports" / "fase0_oos.parquet"
    if not oos_parquet.exists():
        print("ERROR: reports/fase0_oos.parquet no existe.")
        print("Ejecuta primero: python scripts/run_oos_final.py")
        sys.exit(1)

    print(f"Ejecutando notebook: {NOTEBOOK}")
    print("(puede tardar 2-5 minutos en re-ejecutar todos los backtests OOS)...")

    result = subprocess.run(
        [
            sys.executable, "-m", "jupyter", "nbconvert",
            "--to", "html",
            "--execute",
            "--ExecutePreprocessor.timeout=600",
            "--output", str(OUTPUT),
            "--output-dir", str(OUTPUT.parent),
            str(NOTEBOOK),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("ERROR al convertir el notebook:")
        print(result.stderr[-3000:] if result.stderr else "(sin salida de error)")
        sys.exit(1)

    print(f"\nReporte generado: {OUTPUT}")
    print(f"Tamaño: {OUTPUT.stat().st_size / 1024:.1f} KB")
    print(f"Abrir en navegador: file://{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
