#!/usr/bin/env python3
# migrar_maildirs.py

import csv
import subprocess
import re

CSV_FILE = "/root/migration/usuarios_test2.csv"

ORIGEN_HOST = "zentyaldom"
ORIGEN_BASE = "/var/vmail/mp.gba.gov.ar"


def run(cmd, check=True):
    print("[CMD]", " ".join(cmd))
    r = subprocess.run(cmd, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"Fallo comando: {' '.join(cmd)}")
    return r.returncode


with open(CSV_FILE, encoding="utf-8") as f:

    reader = csv.DictReader(f)

    for row in reader:

        uid = row["uid"].strip()
        mail = row["mail"].strip()

        print()
        print("=" * 70)
        print(f"Migrando {mail}")
        print("=" * 70)

        result = subprocess.run(
            ["doveadm", "user", "-u", mail],
            capture_output=True,
            text=True,
            check=True
        )

        m = re.search(r"home\s+:\s+(.+)", result.stdout)

        if not m:
            print(f"[ERROR] No pude obtener home para {mail}")
            continue

        home = m.group(1).strip()
        destino_maildir = f"{home}/Maildir"

        print(f"[INFO] Destino: {destino_maildir}")

        #
        # Crear Maildir destino si aún no existe
        #
        run([
            "mkdir",
            "-p",
            destino_maildir
        ])

        #
        # Copiar TODO el Maildir del usuario
        #
        #origen = f"root@{ORIGEN_HOST}:{ORIGEN_BASE}/{uid}/"
        usuario = mail.split("@")[0]
        origen = f"root@{ORIGEN_HOST}:{ORIGEN_BASE}/{usuario}/"

        run([
            "rsync",
            "-a",
            "--exclude=tmp/",
            "--exclude=dovecot*",
            "--exclude=maildirsize",
            origen,
            destino_maildir + "/"
        ])

        #
        # Corregir permisos
        #
        run([
            "chown",
            "-R",
            "vmail:vmail",
            destino_maildir
        ])

        #
        # Recalcular cuota (si está disponible)
        #
        try:
            run([
                "doveadm",
                "quota",
                "recalc",
                "-u",
                mail
            ])
        except Exception:
            print("[WARN] quota recalc no disponible")

        #
        # Regenerar índices
        #
        try:
            run([
                "doveadm",
                "force-resync",
                "-u",
                mail,
                "*"
            ])
        except Exception as e:
            print(f"[WARN] force-resync falló para {mail}: {e}")

print()
print("[+] Migración finalizada")
