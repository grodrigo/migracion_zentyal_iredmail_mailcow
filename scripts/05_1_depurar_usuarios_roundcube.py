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

from config import OLD_DB, LDAP, LOG_DIR, COMMIT_CADA

import re
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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

    if not EMAIL_RE.match(mail):
        continue

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
    username,

    (
        SELECT COUNT(*)
        FROM contacts c
        WHERE c.user_id = users.user_id
    ) AS contactos,

    (
        SELECT COUNT(*)
        FROM contactgroups g
        WHERE g.user_id = users.user_id
    ) AS grupos,

    (
        SELECT COUNT(*)
        FROM identities i
        WHERE i.user_id = users.user_id
    ) AS identidades

FROM users
ORDER BY user_id;
""")

usuarios_rc = cur.fetchall()

# Todos los usuarios, sin perder ninguno
rc_index = {}

for u in usuarios_rc:

    key = u["username"].strip().lower()

    if key not in rc_index:
        rc_index[key] = []

    rc_index[key].append(u)

print(f"[+] Roundcube: {len(usuarios_rc)} usuarios")


# ---------------------------------------------------------
# Comparación
# ---------------------------------------------------------
rc_set = set(rc_index.keys())

solo_rc = sorted(rc_set - ldap_users)
solo_ldap = sorted(ldap_users - rc_set)
comunes = sorted(rc_set & ldap_users)

print(f"[+] Sólo Roundcube : {len(solo_rc)}")
print(f"[+] Sólo LDAP      : {len(solo_ldap)}")

print("[*] Generando CSV...")

with open(
    "./work/usuarios_a_eliminar.csv",
    "w",
    newline="",
    encoding="utf8"
) as f:

    w = csv.writer(f)

    w.writerow([
        "user_id",
        "username",
        "contactos",
        "grupos",
        "identidades"
    ])

    for username in solo_rc:
        for u in rc_index[username]:
            w.writerow([
                u["user_id"],
                u["username"],
                u["contactos"],
                u["grupos"],
                u["identidades"]
            ])

with open(
    "./work/usuarios_solo_ldap.csv",
    "w",
    newline="",
    encoding="utf8"
) as f:

    w = csv.writer(f)

    w.writerow(["username"])

    for username in solo_ldap:
        w.writerow([username])

with open(
    "./work/usuarios_comunes.csv",
    "w",
    newline="",
    encoding="utf8"
) as f:

    w = csv.writer(f)

    w.writerow([
        "user_id",
        "username"
    ])

    for username in comunes:
        for u in rc_index[username]:
            w.writerow([
                u["user_id"],
                u["username"]
            ])

print("[+] CSV generados:")
print("./work/usuarios_a_eliminar.csv")
print("./work/usuarios_comunes.csv")
print("./work/usuarios_solo_ldap.csv")

print()

print("=" * 70)
print("RESUMEN")
print("=" * 70)

print(f"Usuarios LDAP           : {len(ldap_users)}")
print(f"Usuarios Roundcube      : {len(usuarios_rc)}")
print(f"Usuarios comunes        : {len(comunes)}")
print(f"Sólo Roundcube          : {len(solo_rc)}")
print(f"Sólo LDAP               : {len(solo_ldap)}")

if len(comunes) + len(solo_rc) != len(rc_set):
    raise RuntimeError("Error de consistencia en los usuarios de Roundcube.")

if len(comunes) + len(solo_ldap) != len(ldap_users):
    raise RuntimeError("Error de consistencia en los usuarios de LDAP.")

if DRY_RUN:

    print()
    print("[DRY RUN]")
    print("No se realizaron modificaciones.")
    print("Revise ./work/usuarios_a_eliminar.csv antes de ejecutar con --apply.")

else:

    print()
    print("=" * 70)
    print("MODO APPLY")
    print("=" * 70)

    if not solo_rc:
        print("No hay usuarios para eliminar.")
        sys.exit(0)

    # Resumen de impacto:
    total_contactos = 0
    total_grupos = 0
    total_identidades = 0

    for username in solo_rc:

        for u in rc_index[username]:

            total_contactos += u["contactos"]
            total_grupos += u["grupos"]
            total_identidades += u["identidades"]

    print()
    print("Impacto")
    print(f"Usuarios     : {len(solo_rc)}")
    print(f"Contactos    : {total_contactos}")
    print(f"Grupos       : {total_grupos}")
    print(f"Identidades  : {total_identidades}")
    print()

    print(f"Se eliminarán {len(solo_rc)} usuarios de Roundcube.")
    print()

    respuesta = input(
        "Escriba ELIMINAR para continuar: "
    )

    if respuesta != "ELIMINAR":

        print("Operación cancelada.")
        sys.exit(1)

    #
    # recién aquí procedemos a borrar
    #
    try:

        eliminados = 0

        for username in solo_rc:
            for u in rc_index[username]:
            
                logging.info(
                    "DELETE user_id=%s username=%s contactos=%s grupos=%s identidades=%s",
                    u["user_id"],
                    u["username"],
                    u["contactos"],
                    u["grupos"],
                    u["identidades"]
                )

                cur.execute(
                    """
                    DELETE
                    FROM users
                    WHERE user_id=%s
                    """,
                    (u["user_id"],)
                )

                eliminados += 1

                if eliminados % COMMIT_CADA == 0:

                    conn.commit()

                    logging.info(
                        "Commit (%d eliminados)",
                        eliminados
                    )
                print()

        conn.commit()

        logging.info("=" * 60)
        logging.info("DEPURACIÓN FINALIZADA")
        logging.info("Usuarios eliminados : %d", eliminados)
        logging.info("Contactos eliminados: %d", total_contactos)
        logging.info("Grupos eliminados   : %d", total_grupos)
        logging.info("Identidades         : %d", total_identidades)
        logging.info("=" * 60)

        print()
        print("=" * 70)
        print("DEPURACIÓN FINALIZADA")
        print("=" * 70)
        print(f"Usuarios eliminados : {eliminados}")
        print(f"Contactos eliminados: {total_contactos}")
        print(f"Grupos eliminados   : {total_grupos}")
        print(f"Identidades         : {total_identidades}")
        print(f"Log                 : {logfile}")

    except Exception:

        conn.rollback()

        logging.exception(
            "Rollback ejecutado."
        )

        raise

    finally:
        cur.close()
        conn.close()
        ldap.unbind()
