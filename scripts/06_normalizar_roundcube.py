#!/usr/bin/env python3
# 06_normalizar_roundcube.py

from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE / "06_scripts_normalizacion"

PASOS = [
    "06_1_normalizar_usuarios.py",
    "06_2_consolidar_contactos.py",
    "06_3_validar_grupos.py",
    "06_4_auditar_identidades.py",
    "06_5_consolidar_identidades.py",
    "06_6_eliminar_registros_obsoletos.py",
]

for paso in PASOS:

    script = SCRIPTS / paso

    print()
    print("=" * 70)
    print(f"Ejecutando {script.name}")
    print("=" * 70)

    subprocess.run(
        [sys.executable, str(script)],
        check=True
    )

print()
print("[+] Roundcube normalizado correctamente.")