#!/usr/bin/env python3
"""
06_5_eliminar_registros_obsoletos.py

Elimina físicamente los registros que quedaron obsoletos luego
de finalizar la normalización de Roundcube.

Debe ejecutarse únicamente después de:

    06_4_consolidar_identidades.py

Acciones realizadas
-------------------
- Elimina usuarios secundarios.
- Elimina identities marcadas como eliminadas.
- Elimina contactos marcados como eliminados.
- Elimina grupos marcados como eliminados.
- Elimina miembros de grupos huérfanos.
- Verifica que la base haya quedado consistente.
- Elimina la tabla temporal user_normalization_map.

"""

import logging
from datetime import datetime
from pathlib import Path
import mysql.connector
import sys

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import OLD_DB


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

LOGDIR = Path("logs")
LOGDIR.mkdir(exist_ok=True)

LOGFILE = LOGDIR / (
    f"06_5_eliminar_registros_obsoletos_"
    f"{datetime.now():%Y%m%d_%H%M%S}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE, encoding="utf8"),
        logging.StreamHandler()
    ]
)

print("=" * 70)
print("ELIMINACIÓN DE REGISTROS OBSOLETOS")
print("=" * 70)

conn = mysql.connector.connect(**OLD_DB)

cur = conn.cursor()

logging.info("Conectado a Roundcube.")


# ------------------------------------------------------------
# Usuarios secundarios
# ------------------------------------------------------------

cur.execute("""
DELETE u
FROM users u
JOIN user_normalization_map m
  ON u.user_id = m.old_user_id
WHERE m.es_principal = 0
""")

usuarios = cur.rowcount


# ------------------------------------------------------------
# Identities eliminadas
# ------------------------------------------------------------

cur.execute("""
DELETE
FROM identities
WHERE del = 1
""")

identidades = cur.rowcount


# ------------------------------------------------------------
# Contactos eliminados
# ------------------------------------------------------------

cur.execute("""
DELETE
FROM contacts
WHERE del = 1
""")

contactos = cur.rowcount


# ------------------------------------------------------------
# Grupos eliminados
# ------------------------------------------------------------

cur.execute("""
DELETE
FROM contactgroups
WHERE del = 1
""")

grupos = cur.rowcount


# ------------------------------------------------------------
# Miembros huérfanos
# ------------------------------------------------------------

cur.execute("""
DELETE gm
FROM contactgroupmembers gm
LEFT JOIN contactgroups g
       ON gm.contactgroup_id = g.contactgroup_id
WHERE g.contactgroup_id IS NULL
""")

miembros = cur.rowcount

conn.commit()

logging.info("Depuración finalizada.")


# ------------------------------------------------------------
# Resumen
# ------------------------------------------------------------

print()
print("=" * 70)
print("RESUMEN")
print("=" * 70)

print(f"Usuarios eliminados............. {usuarios}")
print(f"Identidades eliminadas.......... {identidades}")
print(f"Contactos eliminados............ {contactos}")
print(f"Grupos eliminados............... {grupos}")
print(f"Miembros eliminados............. {miembros}")

print()
print(f"Log : {LOGFILE}")

logging.info("=" * 60)
logging.info("Usuarios eliminados    : %d", usuarios)
logging.info("Identidades eliminadas : %d", identidades)
logging.info("Contactos eliminados   : %d", contactos)
logging.info("Grupos eliminados      : %d", grupos)
logging.info("Miembros eliminados    : %d", miembros)
logging.info("=" * 60)


# ------------------------------------------------------------
# Validaciones
# ------------------------------------------------------------

print()
print("=" * 70)
print("VALIDACIONES")
print("=" * 70)

cur.close()
cur = conn.cursor(dictionary=True)

cur.execute("""
SELECT COUNT(*) AS c
FROM identities
WHERE del = 1
""")
identidades_restantes = cur.fetchone()["c"]

cur.execute("""
SELECT COUNT(*) AS c
FROM contacts
WHERE del = 1
""")
contactos_restantes = cur.fetchone()["c"]

cur.execute("""
SELECT COUNT(*) AS c
FROM contactgroups
WHERE del = 1
""")
grupos_restantes = cur.fetchone()["c"]

cur.execute("""
SELECT COUNT(*) AS c
FROM users u
JOIN user_normalization_map m
  ON u.user_id = m.old_user_id
WHERE m.es_principal = 0
""")
usuarios_secundarios = cur.fetchone()["c"]

print(f"Usuarios secundarios restantes : {usuarios_secundarios}")
print(f"Identidades del=1 restantes    : {identidades_restantes}")
print(f"Contactos del=1 restantes      : {contactos_restantes}")
print(f"Grupos del=1 restantes         : {grupos_restantes}")

logging.info("Usuarios secundarios restantes : %d", usuarios_secundarios)
logging.info("Identidades del=1 restantes    : %d", identidades_restantes)
logging.info("Contactos del=1 restantes      : %d", contactos_restantes)
logging.info("Grupos del=1 restantes         : %d", grupos_restantes)

print()

ok = (
    usuarios_secundarios == 0
    and identidades_restantes == 0
    and contactos_restantes == 0
    and grupos_restantes == 0
)

if ok:

    print("[+] Base Roundcube normalizada correctamente.")

    logging.info("Base Roundcube normalizada correctamente.")

    # --------------------------------------------------------
    # Eliminar tabla temporal
    # --------------------------------------------------------

    cur.execute("""
    DROP TABLE IF EXISTS user_normalization_map
    """)

    conn.commit()

    print("[+] Tabla temporal user_normalization_map eliminada.")

    logging.info("Tabla temporal user_normalization_map eliminada.")

else:

    print("[!] Existen registros pendientes de depuración.")
    print("[!] No se eliminó user_normalization_map.")

    logging.error("Validaciones fallidas.")
    logging.error("No se eliminó user_normalization_map.")

    cur.close()
    conn.close()
    sys.exit(1)

cur.close()
conn.close()

print()
print("[+] Finalizado.")