#!/usr/bin/env python3
"""
migration_utils.py

Control simple de la secuencia de ejecución de los scripts.
"""

from pathlib import Path
import sys

STATE_FILE = Path("migration.state")


def check_step(step):
    """
    Verifica que un paso haya sido ejecutado.
    """

    if not STATE_FILE.exists():
        print("[!] No existe migration.state")
        print("[!] Debe comenzar la migración desde el primer script.")
        sys.exit(1)

    pasos = {
        linea.strip()
        for linea in STATE_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
        if linea.strip()
    }

    if step not in pasos:
        print(f"[!] Debe ejecutarse previamente {step}.py")
        sys.exit(1)


def mark_step(step):
    """
    Registra un paso como finalizado.
    """

    pasos = set()

    if STATE_FILE.exists():

        pasos = {
            linea.strip()
            for linea in STATE_FILE.read_text(
                encoding="utf-8"
            ).splitlines()
            if linea.strip()
        }

    pasos.add(step)

    STATE_FILE.write_text(
        "\n".join(sorted(pasos)) + "\n",
        encoding="utf-8"
    )


def reset_state():
    """
    Elimina el estado previo de la migración.
    """

    if STATE_FILE.exists():
        STATE_FILE.unlink()