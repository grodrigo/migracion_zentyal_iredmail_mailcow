#!/usr/bin/env python3
"""
06_2_consolidar_contactos_v4.py

Versión producción.
- Consolida contactos sobre roundcube_old.
- Fusiona información del contacto más completo.
- Reasigna grupos.
- Idempotente.
"""

import logging
from pathlib import Path
from datetime import datetime
import mysql.connector
from config import OLD_DB

LOGDIR=Path("logs"); LOGDIR.mkdir(exist_ok=True)
LOGFILE=LOGDIR/f"06_2_consolidar_contactos_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOGFILE,encoding="utf8"),
              logging.StreamHandler()]
)

def score(c):
    s=0
    for f in ("firstname","surname","name","email"):
        if c.get(f): s+=20
    if c.get("vcard"):
        s+=len(c["vcard"])
    return s

def best(a,b):
    return a if score(a)>=score(b) else b

def merge(dst,src):
    out=dict(dst)
    for f in ("firstname","surname","name","email"):
        if (not out.get(f)) and src.get(f):
            out[f]=src[f]
    if len(src.get("vcard") or "")>len(out.get("vcard") or ""):
        out["vcard"]=src["vcard"]
    if src.get("changed") and (not out.get("changed") or src["changed"]>out["changed"]):
        out["changed"]=src["changed"]
    return out

print("[*] Conectando...")
conn=mysql.connector.connect(**OLD_DB)
cur=conn.cursor(dictionary=True,buffered=True)

cur.execute("""
SELECT old_user_id,new_user_id,username_normalizado
FROM migration_user_map
WHERE es_principal=0
ORDER BY username_normalizado
""")
usuarios=cur.fetchall()

movidos=fusionados=eliminados=grupos=actualizados=ops=0

try:
    for n,u in enumerate(usuarios,1):
        print(f"[{n}/{len(usuarios)}] {u['username_normalizado']}")
        cur.execute("SELECT * FROM contacts WHERE user_id=%s ORDER BY contact_id",
                    (u["old_user_id"],))
        for c in cur.fetchall():
            cur.execute("""
            SELECT *
            FROM contacts
            WHERE user_id=%s
            AND (
                 (email<>'' AND email=%s)
              OR (IFNULL(vcard,'')<>'' AND vcard=%s)
              OR (IFNULL(name,'')=%s
                  AND IFNULL(firstname,'')=%s
                  AND IFNULL(surname,'')=%s)
            )
            LIMIT 1
            """,(u["new_user_id"],
                 c["email"],c["vcard"],
                 c["name"],c["firstname"],c["surname"]))
            p=cur.fetchone()

            if not p:
                cur.execute("UPDATE contacts SET user_id=%s WHERE contact_id=%s",
                            (u["new_user_id"],c["contact_id"]))
                movidos+=1
            else:
                keep=best(p,c)
                drop=c if keep["contact_id"]==p["contact_id"] else p
                merged=merge(keep,drop)
                cur.execute("""
                UPDATE contacts
                SET changed=%s,
                    name=%s,
                    email=%s,
                    firstname=%s,
                    surname=%s,
                    vcard=%s
                WHERE contact_id=%s
                """,(merged["changed"],merged["name"],merged["email"],
                     merged["firstname"],merged["surname"],
                     merged["vcard"],keep["contact_id"]))
                actualizados+=cur.rowcount
                cur.execute("""
                UPDATE contactgroupmembers
                SET contact_id=%s
                WHERE contact_id=%s
                """,(keep["contact_id"],drop["contact_id"]))
                grupos+=cur.rowcount
                cur.execute("DELETE FROM contacts WHERE contact_id=%s",
                            (drop["contact_id"],))
                eliminados+=cur.rowcount
                fusionados+=1
            ops+=1
            if ops%500==0:
                conn.commit()
                logging.info("Commit %d",ops)
    conn.commit()
except Exception:
    conn.rollback()
    logging.exception("Rollback")
    raise
finally:
    cur.close(); conn.close()

print("="*70)
print("Resumen")
print("="*70)
print(f"Usuarios secundarios : {len(usuarios)}")
print(f"Contactos movidos    : {movidos}")
print(f"Fusionados           : {fusionados}")
print(f"Actualizados         : {actualizados}")
print(f"Grupos actualizados  : {grupos}")
print(f"Eliminados           : {eliminados}")
print(f"Log                  : {LOGFILE}")
print("[+] OK")
