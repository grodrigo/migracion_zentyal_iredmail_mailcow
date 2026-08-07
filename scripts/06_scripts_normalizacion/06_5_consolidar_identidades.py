#!/usr/bin/env python3
"""
06_4_consolidar_identidades.py

Consolida las identidades de usuarios normalizados.

Requisitos previos
------------------
- Ejecutar 05_3_auditar_identidades.py.
- No deben existir registros pendientes de revisión.
- Debe existir user_normalization_map.

El proceso:

1. Recorre los usuarios secundarios.
2. Reasigna las identities al usuario principal.
3. Si ya existe una identity con el mismo email:
    - conserva la identity activa previamente validada;
    - reasigna la identity del usuario secundario
      al usuario principal;
    - la marca como eliminada (del=1).
4. Verifica que no queden identities asociadas a
   usuarios secundarios.

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
    f"06_4_consolidar_identidades_"
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


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def norm(texto):

    if texto is None:
        return ""

    return str(texto).strip().lower()


# ------------------------------------------------------------
# Base
# ------------------------------------------------------------

print("=" * 70)
print("CONSOLIDACIÓN DE IDENTIDADES")
print("=" * 70)

CSV_REVISION = Path("validacion_roundcube") / "identidades_pendientes_revision.csv"

if not CSV_REVISION.exists():
    print("[!] No se encontró identidades_pendientes_revision.csv")
    print("[!] Debe ejecutarse previamente 05_3_auditar_identidades.py")
    sys.exit(1)

with open(CSV_REVISION, encoding="utf8") as f:
    lineas = sum(1 for _ in f)

pendientes = lineas - 1
if pendientes > 0:
    print(f"[!] Existen {pendientes} identidades pendientes de revisión.")
    print("[!] Ejecute nuevamente 06_4_auditar_identidades.py.")
    sys.exit(1)

conn = mysql.connector.connect(**OLD_DB)

cur = conn.cursor(
    dictionary=True,
    buffered=True
)

logging.info("Conectado a Roundcube.")


# ------------------------------------------------------------
# Usuarios normalizados
# ------------------------------------------------------------

cur.execute("""
SELECT
    old_user_id,
    new_user_id,
    username_normalizado
FROM user_normalization_map
WHERE es_principal=0
ORDER BY username_normalizado
""")

usuarios = cur.fetchall()

print(f"Usuarios secundarios : {len(usuarios)}")

logging.info(
    "Usuarios secundarios: %d",
    len(usuarios)
)


# ------------------------------------------------------------
# Estadísticas
# ------------------------------------------------------------

identidades_movidas = 0

identidades_fusionadas = 0

identidades_descartadas = 0

usuarios_procesados = 0

identidades_eliminadas_reubicadas = 0

logging.info("Iniciando consolidación...")

# ------------------------------------------------------------
# Reubicar identities previamente eliminadas
# ------------------------------------------------------------

logging.info(
    "Reubicando identities del=1 a usuarios principales..."
)

cur.execute("""
UPDATE identities i
JOIN user_normalization_map m
  ON i.user_id = m.old_user_id
SET
    i.user_id = m.new_user_id,
    i.changed = NOW()
WHERE
    m.es_principal = 0
AND i.del = 1
""")

identidades_eliminadas_reubicadas = cur.rowcount

logging.info(
    "Identities del=1 reubicadas: %d",
    cur.rowcount
)

# ------------------------------------------------------------
# Consolidación
# ------------------------------------------------------------

for idx, usuario in enumerate(usuarios, 1):

    usuarios_procesados += 1

    if idx == 1 or idx % 25 == 0 or idx == len(usuarios):

        logging.info(
            "[%d/%d] %s",
            idx,
            len(usuarios),
            usuario["username_normalizado"]
        )

    #
    # Identities del usuario secundario
    #
    cur.execute("""
        SELECT *
        FROM identities
        WHERE user_id=%s
        AND del=0
        ORDER BY identity_id
    """, (usuario["old_user_id"],))

    secundarias = cur.fetchall()

    for identidad in secundarias:

        #
        # ¿Existe una identity con el mismo email
        # en el usuario principal?
        #
        cur.execute("""
            SELECT *
            FROM identities
            WHERE user_id=%s
              AND LOWER(TRIM(email))=%s
              AND del=0
            ORDER BY
                standard DESC,
                identity_id
            LIMIT 1
        """, (
            usuario["new_user_id"],
            norm(identidad["email"])
        ))

        principal = cur.fetchone()

        #
        # Caso 1:
        # No existe.
        #
        if principal is None:

            cur.execute("""
                UPDATE identities
                SET
                    user_id=%s,
                    del=0,
                    changed=NOW()
                WHERE identity_id=%s
            """, (
                usuario["new_user_id"],
                identidad["identity_id"]
            ))

            identidades_movidas += 1

            logging.info(
                "MOVE identity=%s -> user=%s",
                identidad["identity_id"],
                usuario["new_user_id"]
            )

            continue


        #
        # Si debemos conservar la identity que viene
        # del usuario secundario, primero la movemos
        # al usuario principal y luego descartamos
        # la anterior.
        #
        cur.execute("""
            UPDATE identities
            SET
                user_id=%s,
                del=1,
                standard=0,
                changed=NOW()
            WHERE identity_id=%s
        """, (
            usuario["new_user_id"],
            identidad["identity_id"],
        ))
        identidades_descartadas += 1
        identidades_fusionadas += 1

conn.commit()

logging.info(
    "Consolidación finalizada."
)

# ------------------------------------------------------------
# Validaciones finales
# ------------------------------------------------------------

print()
print("=" * 70)
print("VALIDACIONES")
print("=" * 70)

#
# Identities activas en usuarios secundarios
#
cur.execute("""
SELECT COUNT(*)
FROM identities i
JOIN user_normalization_map m
ON i.user_id=m.old_user_id
WHERE m.es_principal=0;
""")

identidades_en_secundarios = cur.fetchone()["COUNT(*)"]

print(f"Usuarios procesados            : {usuarios_procesados}")
print(f"Identidades activas movidas            : {identidades_movidas}")
print(f"Identidades fusionadas         : {identidades_fusionadas}")
print(f"Identidades descartadas        : {identidades_descartadas}")
print(f"Identidades del=1 reubicadas   :  {identidades_eliminadas_reubicadas}")
print(f"Identidades en usuarios secundarios  : {identidades_en_secundarios}")

print()
print(f"Log : {LOGFILE}")

logging.info("=" * 60)
logging.info("Usuarios procesados         : %d", usuarios_procesados)
logging.info("Identidades activas movidas         : %d", identidades_movidas)
logging.info("Identidades fusionadas      : %d", identidades_fusionadas)
logging.info("Identidades descartadas     : %d", identidades_descartadas)
logging.info("Identidades del=1 reubicadas   : %d", identidades_eliminadas_reubicadas)
logging.info("Identidades en usuarios secundarios  : %d", identidades_en_secundarios)
logging.info("=" * 60)


print()
print("Resultado")
print("---------")

if identidades_en_secundarios == 0:

    print("[+] Consolidación finalizada correctamente.")
    print("[+] Puede ejecutarse 06_5_eliminar_registros_obsoletos.py")

else:

    print("[!] Existen identities asociadas a usuarios secundarios.")
    print("[!] Revisar el log antes de continuar.")

logging.info("Consolidación finalizada.")

cur.close()
conn.close()

print()
print("[+] Finalizado.")