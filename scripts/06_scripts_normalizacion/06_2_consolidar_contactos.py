#!/usr/bin/env python3
"""
06_2_consolidar_contactos_v6_1.py

Basada en la V6 original.

Cambios mínimos:
- Comparación TRIM(LOWER()) para email y nombres.
- Segunda pasada utilizando exactamente el mismo algoritmo.
- Log más detallado.
- Generación de contactos_pendientes.csv.
- Sin cambiar la estrategia de búsqueda de la V6.
"""

import csv
import logging
import sys
from pathlib import Path
from datetime import datetime
import mysql.connector

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import OLD_DB

LOGDIR = Path("logs")
LOGDIR.mkdir(exist_ok=True)
LOGFILE = LOGDIR / f"06_2_consolidar_contactos_{datetime.now():%Y%m%d_%H%M%S}.log"
CSVFILE = Path("contactos_pendientes.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def score(c):
    s = 0
    for f in ("firstname","surname","name","email"):
        if c.get(f):
            s += 20
    s += len(c.get("vcard") or "")
    return s

def merge(a,b):
    out=dict(a)
    for f in ("firstname","surname","name","email"):
        if (not out.get(f)) and b.get(f):
            out[f]=b[f]
    if len(b.get("vcard") or "") > len(out.get("vcard") or ""):
        out["vcard"]=b["vcard"]
    if b.get("changed") and (not out.get("changed") or b["changed"]>out["changed"]):
        out["changed"]=b["changed"]
    return out

conn=mysql.connector.connect(**OLD_DB)
cur=conn.cursor(dictionary=True, buffered=True)

cur.execute("""
SELECT old_user_id,new_user_id,username_normalizado
FROM user_normalization_map
WHERE es_principal=0
ORDER BY username_normalizado
""")
usuarios=cur.fetchall()

movidos=fusionados=eliminados=grupos=ops=0

try:

    for pasada in (1,2):

        logging.info("========== PASADA %d ==========", pasada)

        for i,u in enumerate(usuarios,1):

            logging.info("[%d/%d] %s",
                         i,len(usuarios),u["username_normalizado"])

            cur.execute(
                "SELECT * FROM contacts WHERE user_id=%s ORDER BY contact_id",
                (u["old_user_id"],)
            )
            secundarios=cur.fetchall()

            for c in secundarios:

                p=None

                if c["email"]:
                    cur.execute("""
                    SELECT *
                    FROM contacts
                    WHERE user_id=%s
                      AND TRIM(LOWER(email))=TRIM(LOWER(%s))
                    ORDER BY
                        LENGTH(IFNULL(vcard,'')) DESC,
                        changed DESC,
                        contact_id
                    LIMIT 1
                    """,(u["new_user_id"],c["email"]))
                    p=cur.fetchone()

                if p is None and c.get("vcard"):
                    cur.execute("""
                    SELECT *
                    FROM contacts
                    WHERE user_id=%s
                      AND vcard=%s
                    ORDER BY
                        LENGTH(IFNULL(vcard,'')) DESC,
                        changed DESC,
                        contact_id
                    LIMIT 1
                    """,(u["new_user_id"],c["vcard"]))
                    p=cur.fetchone()

                if p is None:
                    cur.execute("""
                    SELECT *
                    FROM contacts
                    WHERE user_id=%s
                      AND TRIM(LOWER(IFNULL(name,'')))=TRIM(LOWER(IFNULL(%s,'')))
                      AND TRIM(LOWER(IFNULL(firstname,'')))=TRIM(LOWER(IFNULL(%s,'')))
                      AND TRIM(LOWER(IFNULL(surname,'')))=TRIM(LOWER(IFNULL(%s,'')))
                    ORDER BY
                        LENGTH(IFNULL(vcard,'')) DESC,
                        changed DESC,
                        contact_id
                    LIMIT 1
                    """,(u["new_user_id"],c["name"],c["firstname"],c["surname"]))
                    p=cur.fetchone()

                if p is None:
                    cur.execute(
                        "UPDATE contacts SET user_id=%s WHERE contact_id=%s",
                        (u["new_user_id"],c["contact_id"])
                    )
                    movidos += 1
                    logging.info("MOVE contact_id=%s -> user_id=%s",
                                 c["contact_id"],u["new_user_id"])
                else:
                    keep=p if score(p)>=score(c) else c
                    drop=c if keep["contact_id"]==p["contact_id"] else p

                    m=merge(keep,drop)

                    cur.execute("""
                    UPDATE contacts
                    SET changed=%s,
                        name=%s,
                        email=%s,
                        firstname=%s,
                        surname=%s,
                        vcard=%s
                    WHERE contact_id=%s
                    """,(m["changed"],m["name"],m["email"],
                         m["firstname"],m["surname"],
                         m["vcard"],keep["contact_id"]))

                    cur.execute("""
                    SELECT contactgroup_id
                    FROM contactgroupmembers
                    WHERE contact_id=%s
                    """,(drop["contact_id"],))

                    for g in cur.fetchall():
                        cur.execute("""
                        INSERT IGNORE INTO contactgroupmembers
                        (contactgroup_id,contact_id,created)
                        VALUES(%s,%s,NOW())
                        """,(g["contactgroup_id"],keep["contact_id"]))

                    cur.execute(
                        "DELETE FROM contactgroupmembers WHERE contact_id=%s",
                        (drop["contact_id"],)
                    )
                    grupos += cur.rowcount

                    cur.execute(
                        "DELETE FROM contacts WHERE contact_id=%s",
                        (drop["contact_id"],)
                    )
                    eliminados += cur.rowcount
                    fusionados += 1

                    logging.info("MERGE keep=%s drop=%s",
                                 keep["contact_id"],drop["contact_id"])

                ops += 1
                if ops % 500 == 0:
                    conn.commit()
                    logging.info("Commit %d",ops)

    conn.commit()

    cur.execute("""
    SELECT c.contact_id,c.user_id,c.name,c.email
    FROM contacts c
    JOIN user_normalization_map m
      ON c.user_id=m.old_user_id
    WHERE m.es_principal=0
    ORDER BY c.user_id,c.contact_id
    """)

    pendientes=cur.fetchall()

    with open(CSVFILE,"w",newline="",encoding="utf8") as f:
        w=csv.writer(f)
        w.writerow(["contact_id","user_id","name","email"])
        for r in pendientes:
            w.writerow([r["contact_id"],r["user_id"],r["name"],r["email"]])

finally:
    cur.close()
    conn.close()

print("="*70)
print("RESUMEN")
print("="*70)
print("Usuarios secundarios :",len(usuarios))
print("Movidos              :",movidos)
print("Fusionados           :",fusionados)
print("Grupos               :",grupos)
print("Eliminados           :",eliminados)
print("Pendientes           :",len(pendientes))
print("Log                  :",LOGFILE)
print("CSV                  :",CSVFILE)
