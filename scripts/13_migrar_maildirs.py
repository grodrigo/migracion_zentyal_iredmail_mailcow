#!/usr/bin/env python3
# migrar_maildirs.py

import csv
import subprocess
import re

CSV_FILE = "/root/migration/usuarios_test2.csv"

ORIGEN_HOST = "zentyaldom"
ORIGEN_BASE = "/var/vmail/mp.gba.gov.ar"

CARPETAS = [
    "cur",
    "new",
    ".Drafts",
    ".Sent",
    ".Trash",
]

def run(cmd):
    print("[CMD]", " ".join(cmd))
    r = subprocess.run(cmd, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Fallo comando: {' '.join(cmd)}")

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

        for carpeta in CARPETAS:

            origen = f"root@{ORIGEN_HOST}:{ORIGEN_BASE}/{uid}/{carpeta}/"
            destino = f"{destino_maildir}/{carpeta}/"

            run([
                "rsync",
                "-a",
                origen,
                destino
            ])

        run([
            "chown",
            "-R",
            "vmail:vmail",
            destino_maildir
        ])

        try:
            run([
                "doveadm",
                "force-resync",
                "-u",
                mail,
                "*"
            ])
        except Exception as e:
            print(f"[WARN] force-resync fallo para {mail}: {e}")

print()
print("[+] Migracion finalizada")
