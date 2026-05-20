"""
Pipeline completo de Fase 0 en un solo comando.

Ejecuta en orden:
  1. download_all.py   — descarga datos OHLCV (~2-5 min)
  2. run_fase0.py      — walk-forward analysis (~20-40 min)
  3. run_oos_final.py  — análisis OOS + RECOMENDACION.md (~2-5 min)
  4. build_report.py   — reporte HTML interactivo (~2-5 min)

Uso: python scripts/run_all.py
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT    = Path(__file__).parent.parent
PYTHON  = sys.executable
SCRIPTS = ROOT / "scripts"

PIPELINE = [
    ("Descarga de datos",        SCRIPTS / "download_all.py"),
    ("Walk-forward analysis",    SCRIPTS / "run_fase0.py"),
    ("Análisis OOS final",       SCRIPTS / "run_oos_final.py"),
    ("Generación reporte HTML",  SCRIPTS / "build_report.py"),
]


def main():
    print("=" * 60)
    print("auto_trader — Pipeline Fase 0 completo")
    print("=" * 60)

    t_total = time.time()
    for step, (name, script) in enumerate(PIPELINE, 1):
        print(f"\n[{step}/{len(PIPELINE)}] {name}...")
        print(f"  Ejecutando: {script.name}")
        t0 = time.time()

        result = subprocess.run(
            [PYTHON, str(script)],
            cwd=str(ROOT),
        )

        elapsed = time.time() - t0
        if result.returncode != 0:
            print(f"\nERROR en {script.name} (código {result.returncode}).")
            print("Revisa el output anterior y corrige antes de continuar.")
            sys.exit(result.returncode)

        print(f"  OK ({elapsed:.0f}s)")

    total = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"Pipeline completado en {total/60:.1f} min")
    print(f"  Reporte:         reports/fase0_reporte.html")
    print(f"  Recomendación:   reports/RECOMENDACION.md")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
