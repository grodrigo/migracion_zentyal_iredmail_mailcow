#!/usr/bin/env python3
"""
05_2_validar_roundcube.py

Auditoría previa de Roundcube.
No modifica datos.
Genera reportes CSV con las inconsistencias detectadas en:
    validacion_roundcube/
y un log de ejecución en:
    logs/

Reportes generados:
    - usuarios_duplicados.csv
    - contactos_a_consolidar.csv
    - identidades_externas.csv
    - identidades_eliminadas.csv
    - replyto_externos.csv
    - bcc_externos.csv
    - firmas_sospechosas.csv
    - identidades_duplicadas.csv
    - identidades_con_configuracion_distinta.csv
    - identidades_sospechosas.csv
    - identidades_multiples_standard.csv

"""

import csv
import os
import mysql.connector

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import OLD_DB

import logging
from datetime import datetime

# Logging
LOGDIR = Path("logs")
LOGDIR.mkdir(exist_ok=True)

LOGFILE = LOGDIR / f"05_2_validar_roundcube_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE, encoding="utf8")
    ]
)
# / Logging

OUTDIR="validacion_roundcube"
os.makedirs(OUTDIR,exist_ok=True)

conn=mysql.connector.connect(**OLD_DB)
cur=conn.cursor(dictionary=True)

PATRONES_FRAUDE = (
    "Bank|Lottery|Winner|Beneficiary|Compensation|Donation|"
    "Western|MoneyGram|Bitcoin|Investment|Remittance|"
    "Inheritance|Fund|Transfer|Airport"
)

PATRONES_DETECTADOS = (
    "Toyota|Donald|Harrison|Guterres|Inspector|David"
)

REGEXP_SOSPECHOSO = f"{PATRONES_FRAUDE}|{PATRONES_DETECTADOS}"



def scalar(sql):
    cur.execute(sql)
    return list(cur.fetchone().values())[0]

def export_csv(name,sql):
    cur.execute(sql)
    rows=cur.fetchall()
    path=os.path.join(OUTDIR,name)
    with open(path,"w",newline="",encoding="utf-8") as f:
        if rows:
            w=csv.DictWriter(f,fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        else:
            w = csv.writer(f)
    return len(rows)

print("="*72)
print("VALIDACIÓN PREVIA DE ROUNDCUBE")
print("="*72)

u=scalar("SELECT COUNT(*) c FROM users")
uu=scalar("SELECT COUNT(DISTINCT TRIM(LOWER(username))) c FROM users")
c=scalar("SELECT COUNT(*) c FROM contacts")
g=scalar("SELECT COUNT(*) c FROM contactgroups")
ia=scalar("SELECT COUNT(*) c FROM identities WHERE del=0")

dup=export_csv("usuarios_duplicados.csv","""
SELECT LOWER(username) usuario_normalizado,
COUNT(*) registros,
GROUP_CONCAT(user_id ORDER BY user_id) user_ids
FROM users
GROUP BY TRIM(LOWER(username))
HAVING COUNT(*)>1
""")

cons=export_csv("contactos_a_consolidar.csv","""
SELECT usuario_norm,user_id_principal,contactos_principal,
contactos_restantes,contactos_total,cuentas
FROM(
SELECT t.usuario_norm,
SUBSTRING_INDEX(GROUP_CONCAT(t.user_id ORDER BY t.contactos DESC),',',1) user_id_principal,
MAX(t.contactos) contactos_principal,
SUM(t.contactos)-MAX(t.contactos) contactos_restantes,
SUM(t.contactos) contactos_total,
COUNT(*) cuentas
FROM(
SELECT LOWER(u.username) usuario_norm,u.user_id,COUNT(c.contact_id) contactos
FROM users u LEFT JOIN contacts c ON c.user_id=u.user_id
GROUP BY u.user_id,u.username
)t
GROUP BY t.usuario_norm
)x
WHERE contactos_restantes>0
""")

ident=export_csv("identidades_externas.csv","""
SELECT i.identity_id,u.username,i.email,i.standard
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND LOWER(i.email)<>LOWER(u.username)
""")

reply=export_csv("replyto_externos.csv","""
SELECT i.identity_id,u.username,i.email,i.`reply-to`
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND i.`reply-to`<>'' AND i.`reply-to` NOT LIKE '%@mp.gba.gov.ar'
""")

bcc=export_csv("bcc_externos.csv","""
SELECT i.identity_id,u.username,i.email,i.bcc
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND i.bcc<>'' AND i.bcc NOT LIKE '%@mp.gba.gov.ar'
""")

firmas=export_csv("firmas_sospechosas.csv", f"""
SELECT
    i.identity_id,
    u.username,
    i.email,
    LEFT(i.signature,200) firma
FROM identities i
JOIN users u USING(user_id)
WHERE IFNULL(i.signature,'') REGEXP '{REGEXP_SOSPECHOSO}'
""")

idel=export_csv("identidades_eliminadas.csv","""
SELECT i.identity_id,u.username,i.email,i.standard,i.changed
FROM identities i JOIN users u USING(user_id)
WHERE i.del=1
""")

ident_dup = export_csv("identidades_duplicadas.csv", """
SELECT
    u.username,
    LOWER(TRIM(i.email)) email,
    COUNT(*) cantidad,
    GROUP_CONCAT(i.identity_id ORDER BY i.identity_id) identity_ids
FROM identities i
JOIN users u USING(user_id)
GROUP BY u.username, LOWER(TRIM(i.email))
HAVING COUNT(*) > 1
""")

ident_cfg = export_csv("identidades_con_configuracion_distinta.csv", """
SELECT
    u.username,
    LOWER(TRIM(i.email)) AS email,

    GROUP_CONCAT(i.identity_id ORDER BY i.identity_id) AS identity_ids,
    COUNT(*) AS cantidad,

    GROUP_CONCAT(IFNULL(i.name,'') ORDER BY i.identity_id SEPARATOR ' | ') AS nombres,
    GROUP_CONCAT(IFNULL(i.organization,'') ORDER BY i.identity_id SEPARATOR ' | ') AS organizaciones,
    GROUP_CONCAT(IFNULL(i.`reply-to`,'') ORDER BY i.identity_id SEPARATOR ' | ') AS reply_to,
    GROUP_CONCAT(IFNULL(i.bcc,'') ORDER BY i.identity_id SEPARATOR ' | ') AS bcc,

    GROUP_CONCAT(i.standard ORDER BY i.identity_id) AS standard_flags,
    GROUP_CONCAT(i.del ORDER BY i.identity_id) AS del_flags,

    GROUP_CONCAT(
        LEFT(IFNULL(i.signature,''),80)
        ORDER BY i.identity_id
        SEPARATOR ' | '
    ) AS firmas

FROM identities i
JOIN users u USING(user_id)

GROUP BY
    u.username,
    LOWER(TRIM(i.email))

HAVING
    COUNT(*) > 1
AND (
       COUNT(DISTINCT i.name) > 1
    OR COUNT(DISTINCT i.organization) > 1
    OR COUNT(DISTINCT i.`reply-to`) > 1
    OR COUNT(DISTINCT i.bcc) > 1
    OR COUNT(DISTINCT IFNULL(i.signature,'')) > 1
)
""")

ident_sosp = export_csv("identidades_sospechosas.csv", f"""
SELECT
    u.username,
    i.identity_id,
    i.email,
    i.name,
    i.organization,
    i.`reply-to`,
    i.bcc,
    LEFT(i.signature,200) signature
FROM identities i
JOIN users u USING(user_id)
WHERE
    i.name REGEXP '{REGEXP_SOSPECHOSO}'
OR
    i.organization REGEXP '{REGEXP_SOSPECHOSO}'
OR
    IFNULL(i.signature,'') REGEXP '{REGEXP_SOSPECHOSO}'
""")

multi_std = export_csv("identidades_multiples_standard.csv", """
SELECT
    u.username,
    COUNT(*) cantidad
FROM identities i
JOIN users u USING(user_id)
WHERE i.standard=1
AND i.del=0
GROUP BY u.username
HAVING COUNT(*)>1
""")


logging.info("Usuarios               : %s", u)
logging.info("Usuarios únicos        : %s", uu)
logging.info("Contactos              : %s", c)
logging.info("Grupos                 : %s", g)
logging.info("Identidades activas    : %s", ia)

print("="*72)
print("Resumen")
print("="*72)

print(f"Usuarios               : {u}")
print(f"Usuarios únicos        : {uu}")
print(f"Contactos              : {c}")
print(f"Grupos                 : {g}")
print(f"Identidades activas    : {ia}")

orphan_groups = scalar("""
SELECT COUNT(*)
FROM contactgroupmembers gm
LEFT JOIN contacts c
ON gm.contact_id=c.contact_id
WHERE c.contact_id IS NULL
""")

print(f"Miembros huérfanos     : {orphan_groups}")
logging.info("Miembros huérfanos     : %s", orphan_groups)

# Reportes que continúan en los siguientes pasos
informativos = [
    ("Usuarios duplicados", dup, "NORMALIZACIÓN AUTOMÁTICA (06_1)"),
    ("Contactos a consolidar", cons, "CONSOLIDACIÓN AUTOMÁTICA (06_2)"),
    ("Identidades duplicadas", ident_dup, "CONSOLIDACIÓN AUTOMÁTICA (06_5)"),
    ("Configuración distinta", ident_cfg, "SE ANALIZA EN 06_4")
    ("Identidades eliminadas", idel, "CONSOLIDACIÓN AUTOMÁTICA (06_5)"),
]

# Requieren intervención del administrador
revision = [
    ("Identidades externas",
     ident,
     "identidades_externas.csv"),

    ("Identidades sospechosas",
     ident_sosp,
     "identidades_sospechosas.csv"),

    ("Múltiples estándar",
     multi_std,
     "identidades_multiples_standard.csv"),

    ("Reply-To externos",
     reply,
     "replyto_externos.csv"),

    ("BCC externos",
     bcc,
     "bcc_externos.csv"),

    ("Firmas sospechosas",
     firmas,
     "firmas_sospechosas.csv"),
]

print("\nResultado del análisis")

for titulo, cantidad, etapa in informativos:
    if cantidad == 0:
        estado = "OK"
    else:
        estado = f"{etapa} ({cantidad})"
    print(f"{titulo:.<30} {estado}")
    logging.info("%s -> %s", titulo, estado)

for titulo, cantidad, archivo in revision:
    estado = "OK" if cantidad == 0 else f"REVISAR MANUALMENTE ({cantidad})"
    print(f"{titulo:.<30} {estado}")
    logging.info("%s -> %s", titulo, estado)

apto = all(cantidad == 0 for _, cantidad, _ in revision)

print()
print("="*72)
print("Resultado")
print("="*72)

if apto:
    print("[+] Base apta para iniciar la normalización.")
    logging.info("Base apta para iniciar la normalización.")
else:
    print("[!] Existen configuraciones que requieren revisión manual.")
    logging.warning("Existen configuraciones que requieren revisión manual.")


print()
print("=" * 72)
print("SIGUIENTE PASO")
print("=" * 72)

if apto:

    print("[+] No existen observaciones pendientes.")
    print("[+] Puede continuar con:")
    print()
    print("    06_normalizar_roundcube.py")

else:

    print("Antes de continuar revise únicamente los siguientes reportes:")

    if ident:
        print()
        print("Identidades externas")
        print("  Verificar si la identity debe migrarse.")
        print("  Si no corresponde conservarla:")
        print()
        print("      UPDATE identities")
        print("      SET del=1")
        print("      WHERE identity_id=<identity_id>;")

    if ident_sosp:
        print()
        print("Identidades sospechosas")
        print("  Verificar que la configuración pertenezca realmente al usuario.")
        print("  Si corresponde a spam, phishing o una configuración ajena:")
        print()
        print("      UPDATE identities")
        print("      SET del=1")
        print("      WHERE identity_id=<identity_id>;")

    if reply:
        print()
        print("Reply-To externos")
        print("  Confirmar que el destino continúe siendo válido.")
        print("  Si no corresponde:")
        print()
        print("      UPDATE identities")
        print("      SET `reply-to`=''")
        print("      WHERE identity_id=<identity_id>;")

    if bcc:
        print()
        print("BCC externos")
        print("  Confirmar que el reenvío continúe siendo necesario.")
        print("  Si no corresponde:")
        print()
        print("      UPDATE identities")
        print("      SET bcc=''")
        print("      WHERE identity_id=<identity_id>;")

    if firmas:
        print()
        print("Firmas sospechosas")
        print("  Revisar el contenido.")
        print("  Si la firma no debe migrarse:")
        print()
        print("      UPDATE identities")
        print("      SET signature=''")
        print("      WHERE identity_id=<identity_id>;")

    if multi_std:
        print()
        print("Múltiples identities estándar")
        print("  Debe existir una única identity estándar por usuario.")
        print("  Corregir manualmente estableciendo:")
        print()
        print("      standard=1 para una identity")
        print("      standard=0 para las restantes")

    print()
    print("Los siguientes reportes son únicamente informativos")
    print("y serán resueltos automáticamente por los scripts de normalización:")

    if dup:
        print("  - usuarios_duplicados.csv (06_1)")

    if cons:
        print("  - contactos_a_consolidar.csv (06_2)")

    if ident_dup:
        print("  - identidades_duplicadas.csv (06_5)")

    if ident_cfg:
        print("  - identidades_con_configuracion_distinta.csv (06_4)")

    if idel:
        print("  - identidades_eliminadas.csv (06_5)")

    print()
    print("Una vez realizadas las correcciones anteriores ejecute 06_normalizar_roundcube.py:")
    print()
    print("    que ejecutará 06_4_auditar_identidades.py")


print()
print("=" * 72)
print("Archivos generados")
print("=" * 72)

print(f"Directorio de reportes : {OUTDIR}/")
print("  - usuarios_duplicados.csv")
print("  - contactos_a_consolidar.csv")
print("  - identidades_externas.csv")
print("  - identidades_eliminadas.csv")
print("  - replyto_externos.csv")
print("  - bcc_externos.csv")
print("  - firmas_sospechosas.csv")
print("  - identidades_duplicadas.csv")
print("  - identidades_con_configuracion_distinta.csv")
print("  - identidades_sospechosas.csv")
print("  - identidades_multiples_standard.csv")

print()
print(f"Log de ejecución       : {LOGFILE}")

logging.info("=" * 60)
logging.info("Validación finalizada.")
logging.info("Reportes generados en: %s", OUTDIR)
logging.info("Los detalles de cada inconsistencia se encuentran en los archivos CSV correspondientes.")
logging.info("=" * 60)

cur.close()
conn.close()
