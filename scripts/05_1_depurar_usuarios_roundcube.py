#!/usr/bin/env python3
"""
05_1_depurar_usuarios_roundcube.py

Depura la base de Roundcube eliminando usuarios que no existen
en el LDAP institucional (fuente de verdad).

Por defecto ejecuta en modo DRY-RUN.

Características
----------------
- Consulta LDAP.
- Consulta Roundcube.
- Compara usuarios normalizados.
- Genera CSV de auditoría.
- Genera log.
- --dry-run (default)
- --apply (pendiente de implementar en la siguiente versión)
"""

from pathlib import Path
import sys
import csv
import argparse
import logging

import mysql.connector
from ldap3 import Server, Connection, ALL

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import OLD_DB, LDAP, LOG_DIR

# ---------------------------------------------------------
# Argumentos
# ---------------------------------------------------------

parser = argparse.ArgumentParser()

parser.add_argument(
    "--apply",
    action="store_true",
    help="Realiza los borrados (no implementado todavía)."
)

args = parser.parse_args()

DRY_RUN = not args.apply

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logdir = Path(LOG_DIR)
logdir.mkdir(exist_ok=True)

logfile = logdir / "05_1_depurar_usuarios_roundcube.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(logfile, encoding="utf8"),
        logging.StreamHandler()
    ]
)

print("=" * 70)
print("DEPURACIÓN DE USUARIOS ROUNDCUBE")
print("=" * 70)

print("Modo:", "DRY RUN" if DRY_RUN else "APPLY")

# ---------------------------------------------------------
# LDAP
# ---------------------------------------------------------

print("[*] Conectando LDAP...")

server = Server(
    LDAP["host"],
    port=LDAP["port"],
    use_ssl=LDAP["use_ssl"],
    get_info=ALL
)

ldap = Connection(
    server,
    user=LDAP["bind_dn"],
    password=LDAP["password"],
    auto_bind=True
)

ldap.search(
    LDAP["base_dn"],
    LDAP["user_filter"],
    attributes=["mail"]
)

ldap_users = set()

for e in ldap.entries:

    if not hasattr(e, "mail"):
        continue

    mail = str(e.mail).strip().lower()

    if mail:
        ldap_users.add(mail)

print(f"[+] LDAP: {len(ldap_users)} usuarios")

# ---------------------------------------------------------
# Roundcube
# ---------------------------------------------------------

print("[*] Conectando Roundcube...")

conn = mysql.connector.connect(**OLD_DB)

cur = conn.cursor(dictionary=True)

cur.execute("""
SELECT
    user_id,
    username
FROM users
ORDER BY user_id
""")

usuarios_rc = cur.fetchall()

rc_users = {}

for u in usuarios_rc:

    rc_users[u["username"].strip().lower()] = u

print(f"[+] Roundcube: {len(rc_users)} usuarios")

# ---------------------------------------------------------
# Comparación
# ---------------------------------------------------------

solo_rc = sorted(set(rc_users.keys()) - ldap_users)
solo_ldap = sorted(ldap_users - set(rc_users.keys()))

print(f"[+] Sólo Roundcube : {len(solo_rc)}")
print(f"[+] Sólo LDAP      : {len(solo_ldap)}")



