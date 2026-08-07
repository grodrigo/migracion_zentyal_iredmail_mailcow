#!/usr/bin/env python3
"""
06_4_auditar_identidades.py

Audita las identidades que quedarían asociadas a un mismo usuario
luego de la normalización de usuarios.

No modifica la base de datos.

Objetivos
---------
- Detectar identidades con el mismo correo electrónico que
  coexistirán en un mismo usuario luego de la normalización.
- Comparar su configuración.
- Determinar qué casos pueden resolverse automáticamente.
- Identificar únicamente aquellos que requieren intervención
  manual del administrador.
- Generar los reportes necesarios antes de ejecutar
  06_4_consolidar_identidades.py.

Archivos generados
------------------
- identidades_pendientes_revision.csv
- auditoria_identidades_auto.csv
- identidades_duplicadas_principal.csv
"""

import csv
import logging
from pathlib import Path
from datetime import datetime

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
    f"05_3_auditar_identidades_{datetime.now():%Y%m%d_%H%M%S}.log"
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

def csv_text(texto):

    if texto is None:
        return ""

    return (
        str(texto)
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )

def norm(valor):
    if valor is None:
        return ""

    return str(valor).strip().lower()


def distintos(registros, campo):
    valores = {
        norm(r.get(campo))
        for r in registros
        if norm(r.get(campo))
    }
    return sorted(valores)


# def clasificar_riesgo(diferencias):

#     if not diferencias:
#         return "BAJO"

#     criticos = {
#         "reply_to",
#         "bcc",
#         "signature"
#     }

#     if criticos.intersection(diferencias):
#         return "ALTO"

#     return "MEDIO"

def aporta_informacion(secundaria, principal):

    campos = [
        "name",
        "organization",
        "reply-to",
        "bcc",
        "signature",
    ]

    for campo in campos:

        valor_sec = norm(secundaria.get(campo))
        valor_pri = norm(principal.get(campo))

        #
        # Si el secundario está vacío, no aporta nada.
        #
        if valor_sec == "":
            continue

        #
        # Si el principal está vacío y el secundario no,
        # sí aporta información.
        #
        if valor_pri == "":
            return True

        #
        # Si ambos tienen información distinta,
        # requiere revisión.
        #
        if valor_sec != valor_pri:
            return True

    return False

# ------------------------------------------------------------
# Base de datos
# ------------------------------------------------------------

print("=" * 70)
print("AUDITORÍA DE IDENTIDADES")
print("=" * 70)

conn = mysql.connector.connect(**OLD_DB)

cur = conn.cursor(
    dictionary=True,
    buffered=True
)

logging.info("Conectado a Roundcube.")


# ------------------------------------------------------------
# Usuarios secundarios
# ------------------------------------------------------------

cur.execute("""
SELECT DISTINCT
    old_user_id,
    new_user_id,
    username_normalizado
FROM user_normalization_map
WHERE es_principal=0
ORDER BY username_normalizado
""")

usuarios = cur.fetchall()

logging.info(
    "Usuarios secundarios: %d",
    len(usuarios)
)

print(f"Usuarios secundarios: {len(usuarios)}")


# ------------------------------------------------------------
# Estructuras de salida
# ------------------------------------------------------------

registros = []

total_conflictos = 0

# riesgo_bajo = 0
# riesgo_medio = 0
# riesgo_alto = 0


# ------------------------------------------------------------
# Auditoría
# ------------------------------------------------------------

logging.info("Iniciando auditoría...")

for idx, usuario in enumerate(usuarios, 1):

    if idx == 1 or idx % 25 == 0 or idx == len(usuarios):
        logging.info(
            "[%d/%d] %s",
            idx,
            len(usuarios),
            usuario["username_normalizado"]
        )

        logging.debug(
            "[%d/%d] %s (%s -> %s)",
            idx,
            len(usuarios),
            usuario["username_normalizado"],
            usuario["old_user_id"],
            usuario["new_user_id"],
        )

    #
    # Todas las identidades del usuario principal
    #
    cur.execute("""
        SELECT *
        FROM identities
        WHERE user_id=%s
        AND del=0
        ORDER BY identity_id
    """, (usuario["new_user_id"],))

    principales = cur.fetchall()

    #
    # Todas las identidades del usuario secundario
    #
    cur.execute("""
        SELECT *
        FROM identities
        WHERE user_id=%s
        AND del=0
        ORDER BY identity_id
    """, (usuario["old_user_id"],))

    secundarias = cur.fetchall()

    #
    # Agrupar por email normalizado
    #
    emails = {}

    for r in principales:

        key = norm(r["email"])

        emails.setdefault(
            key,
            {
                "principal": [],
                "secundario": []
            }
        )

        emails[key]["principal"].append(r)

    for r in secundarias:

        key = norm(r["email"])

        emails.setdefault(
            key,
            {
                "principal": [],
                "secundario": []
            }
        )

        emails[key]["secundario"].append(r)

    #
    # Analizar únicamente los emails presentes
    # tanto en principal como en secundario
    #
    for email, grupo in sorted(emails.items()):

        if not grupo["principal"]:
            continue

        if not grupo["secundario"]:
            continue

        principal = grupo["principal"]
        secundario = grupo["secundario"]

        ids_principal = ",".join(
            str(x["identity_id"])
            for x in principal
        )

        ids_secundario = ",".join(
            str(x["identity_id"])
            for x in secundario
        )

        nombres = distintos(principal + secundario, "name")
        organizaciones = distintos(principal + secundario, "organization")
        reply_to = distintos(principal + secundario, "reply-to")
        bcc = distintos(principal + secundario, "bcc")
        firmas = distintos(principal + secundario, "signature")

        diferencias = []

        principal_ref = sorted(
            principal,
            key=lambda x: (
                x["del"],          # primero activas
                -x["standard"],    # luego estándar
                x["identity_id"]   # finalmente la más antigua
            )
        )[0]

        secundaria_ref = sorted(
            secundario,
            key=lambda x: (
                x["del"],
                -x["standard"],
                x["identity_id"]
            )
        )[0]

        requiere_revision = False

        for s in secundario:
            for p in principal:

                if aporta_informacion(s, p):
                    requiere_revision = True
                    break

            if requiere_revision:
                break

        if len(nombres) > 1:
            diferencias.append("name")

        if len(organizaciones) > 1:
            diferencias.append("organization")

        if len(reply_to) > 1:
            diferencias.append("reply_to")

        if len(bcc) > 1:
            diferencias.append("bcc")

        if len(firmas) > 1:
            diferencias.append("signature")

        if requiere_revision:
            estado = "REVISAR"
            accion = "REVISION_MANUAL"
        else:
            estado = "APTO"
            accion = "CONSOLIDACION_AUTOMATICA"

        total_conflictos += 1

        activas_principal = sum(
            1 for x in principal
            if x["del"] == 0
        )

        activas_secundario = sum(
            1 for x in secundario
            if x["del"] == 0
        )

        consulta = (
            "SELECT * FROM identities "
            "WHERE identity_id IN ("
            f"{ids_principal},{ids_secundario}"
            ");"
        )

        registros.append({

            "usuario": usuario["username_normalizado"],

            "email": email,

            "old_user_id": usuario["old_user_id"],

            "new_user_id": usuario["new_user_id"],

            "ids_principal": ids_principal,

            "ids_secundario": ids_secundario,

            "activas_principal": activas_principal,

            "activas_secundario": activas_secundario,

            "nombres": " | ".join(map(csv_text, nombres)),
            
            "organizaciones": " | ".join(map(csv_text, organizaciones)),
            
            "reply_to": " | ".join(map(csv_text, reply_to)),
            
            "bcc": " | ".join(map(csv_text, bcc)),

            "firmas": " | ".join(
                csv_text(f)[:40]
                for f in firmas
            ),

            "estado": estado,

            "diferencias": " | ".join(diferencias),

            "accion": accion,

            "consulta_sql": consulta

        })

# ------------------------------------------------------------
# Auditoría adicional:
# identities duplicadas dentro del mismo usuario
# ------------------------------------------------------------

cur.execute("""
SELECT
    u.username,
    i.user_id,
    LOWER(TRIM(i.email)) AS email,
    COUNT(*) AS cantidad,
    GROUP_CONCAT(
        i.identity_id
        ORDER BY i.standard DESC, i.identity_id
    ) AS identity_ids
FROM identities i
JOIN users u
    ON u.user_id = i.user_id
WHERE i.del = 0
GROUP BY
    i.user_id,
    LOWER(TRIM(i.email))
HAVING COUNT(*) > 1
ORDER BY
    u.username,
    email
""")

duplicadas_internas = cur.fetchall()


# ------------------------------------------------------------
# Generar CSV
# ------------------------------------------------------------

CSVFILE = Path("validacion_roundcube") / "identidades_pendientes_revision.csv"

CSV_AUTO = Path("validacion_roundcube") / "auditoria_identidades_auto.csv"

CSV_DUP = Path("validacion_roundcube") / "identidades_duplicadas_principal.csv"

logging.info("Generando reportes...")

revision_manual = [
    r for r in registros
    if r["estado"] == "REVISAR"
]

automaticas = [
    r for r in registros
    if r["estado"] == "APTO"
]

with open(
    CSVFILE,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    campos = [
        "usuario",
        "email",
        "old_user_id",
        "new_user_id",
        "ids_principal",
        "ids_secundario",
        "activas_principal",
        "activas_secundario",
        "nombres",
        "organizaciones",
        "reply_to",
        "bcc",
        "firmas",
        "estado",
        "diferencias",
        "accion",
        "consulta_sql",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=campos
    )

    writer.writeheader()

    writer.writerows(revision_manual)

with open(
    CSV_AUTO,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=campos
    )

    writer.writeheader()

    writer.writerows(automaticas)


with open(
    CSV_DUP,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "username",
            "user_id",
            "email",
            "cantidad",
            "identity_ids",
        ]
    )

    writer.writeheader()

    writer.writerows(duplicadas_internas)

# ------------------------------------------------------------
# Resumen
# ------------------------------------------------------------

print()
print("=" * 70)
print("RESUMEN")
print("=" * 70)

aptos = sum(
    1 for r in registros
    if r["estado"] == "APTO"
)

revision = len(registros) - aptos

print(f"Usuarios analizados        : {len(usuarios)}")
print(f"Identidades a consolidar   : {total_conflictos}")
print(f"Consolidación automática   : {aptos}")
print(f"Requieren revisión manual  : {revision}")
print(f"Duplicadas internas        : {len(duplicadas_internas)}")

print()

if revision == 0 and len(duplicadas_internas) == 0:
    print("Estado final           : APTO")
else:
    print("Estado final           : NO APTO")
print()
print(f"CSV revisión : {CSVFILE}")
if automaticas:
    print(f"CSV automático : {CSV_AUTO}")

print(f"Log : {LOGFILE}")

logging.info("=" * 60)
logging.info("Usuarios analizados         : %d", len(usuarios))
logging.info("Identidades a consolidar    : %d", total_conflictos)
logging.info("Consolidación automática    : %d", aptos)
logging.info("Requieren revisión manual   : %d", revision)
logging.info("CSV generado                : %s", CSVFILE)
logging.info(
    "Duplicadas internas        : %d",
    len(duplicadas_internas)
)
logging.info("=" * 60)


# ------------------------------------------------------------
# Recomendaciones
# ------------------------------------------------------------

print()
print("Acciones recomendadas")
print("---------------------")

if revision == 0 and len(duplicadas_internas) == 0:

    print("[+] No existen conflictos manuales.")
    print("[+] Puede ejecutarse todo 06_ (donde también está 06_4_consolidar_identidades.py)")

else:

    print(f"[!] Existen {revision} conflictos que requieren revisión.\n")

    for r in revision_manual:
        print(
            f" - {r['usuario']} "
            f"({r['email']}) -> {r['diferencias']}"
        )

    print()
    print(f"[ ] Revisar {CSVFILE}")
    if duplicadas_internas:
        print(f"[ ] Revisar {CSV_DUP}")

    print("""
    Para resolver cada conflicto:

    1. Ejecutar la consulta SQL incluida en
    identidades_pendientes_revision.csv.

    2. Comparar las identities involucradas.

    3. Si una identity corresponde a una configuración
    obsoleta, inválida o innecesaria:

        UPDATE identities
        SET del=1
        WHERE identity_id=<identity_id>;

    4. Si ambas identities contienen información válida:

    - conservar manualmente en una única identity la
        configuración deseada (nombre, organización,
        Reply-To, BCC o firma);

    - marcar la restante como eliminada:

        UPDATE identities
        SET del=1
        WHERE identity_id=<identity_id>;

    5- Además revisar identidades_duplicadas_principal.csv
       (poseen múltiples identities activas con el mismo correo electrónico
        antes de la consolidación)
        Conservar únicamente la identity correcta y marcar las
        restantes como eliminadas.

    5. Ejecutar nuevamente:

        06_4_auditar_identidades.py
    
    El proceso podrá continuar únicamente cuando no existan
    registros pendientes de revisión.
    """)

# ------------------------------------------------------------
# Validaciones SQL sugeridas
# ------------------------------------------------------------

print()
print("=" * 70)
print("CONSULTAS DE VALIDACIÓN")
print("=" * 70)

print("""
-- Emails duplicados entre principal y secundario

SELECT COUNT(*)
FROM identities i
JOIN user_normalization_map m
  ON i.user_id=m.old_user_id
JOIN identities p
  ON p.user_id=m.new_user_id
 AND LOWER(TRIM(i.email))=
     LOWER(TRIM(p.email));

-- Usuarios secundarios con identidades

SELECT COUNT(*)
FROM identities i
JOIN user_normalization_map m
  ON i.user_id=m.old_user_id
WHERE m.es_principal=0;
""")

logging.info("Auditoría finalizada.")

cur.close()
conn.close()

print()
print("[+] Finalizado.")