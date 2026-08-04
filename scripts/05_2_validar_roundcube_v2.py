
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
SELECT u.username,i.email,i.standard
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND LOWER(i.email)<>LOWER(u.username)
""")

reply=export_csv("replyto_externos.csv","""
SELECT u.username,i.email,i.`reply-to`
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND i.`reply-to`<>'' AND i.`reply-to` NOT LIKE '%@mp.gba.gov.ar'
""")

bcc=export_csv("bcc_externos.csv","""
SELECT u.username,i.email,i.bcc
FROM identities i JOIN users u USING(user_id)
WHERE i.del=0 AND i.bcc<>'' AND i.bcc NOT LIKE '%@mp.gba.gov.ar'
""")

firmas=export_csv("firmas_sospechosas.csv","""
SELECT u.username,i.email,LEFT(i.signature,200) firma
FROM identities i JOIN users u USING(user_id)
WHERE i.signature REGEXP
'Toyota|Lottery|winner|Congratulations|million|claim|bank|beneficiary|donation|airport|inherit|fund|compensation'
""")

idel=export_csv("identidades_eliminadas.csv","""
SELECT u.username,i.email,i.standard,i.changed
FROM identities i JOIN users u USING(user_id)
WHERE i.del=1
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


print("\nInconsistencias detectadas")
checks=[
("Usuarios duplicados",dup),
("Contactos a consolidar",cons),
("Identidades externas",ident),
("Reply-To externos",reply),
("BCC externos",bcc),
("Firmas sospechosas",firmas),
("Identidades eliminadas",idel)
]
apto=True
for t,n in checks:
    estado="OK" if n==0 else f"REVISAR ({n})"
    if n: apto=False
    print(f"{t:.<30} {estado}")
    logging.info("%s -> %s", t, estado)


print()
print("="*72)
print("Resultado")
print("="*72)

if apto:
    print("[+] Base apta para iniciar la normalización.")
    logging.info("Base apta para iniciar la normalización.")
else:
    print("[!] Existen observaciones que deben revisarse antes de continuar.")
    logging.warning("Existen observaciones que deben revisarse.")

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

print()
print(f"Log de ejecución       : {LOGFILE}")

logging.info("=" * 60)
logging.info("Validación finalizada.")
logging.info("Reportes generados en: %s", OUTDIR)
logging.info("Los detalles de cada inconsistencia se encuentran en los archivos CSV correspondientes.")
logging.info("=" * 60)

cur.close()
conn.close()
