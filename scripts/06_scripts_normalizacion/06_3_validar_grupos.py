#!/usr/bin/env python3
"""
06_3_validar_grupos.py

Valida la consistencia de los grupos de contactos luego de la
consolidación de contactos.

No modifica grupos activos.

Verificaciones:
- Grupos activos duplicados (mismo usuario + mismo nombre).
- Referencias huérfanas en contactgroupmembers.
- Grupos marcados como eliminados (del=1) que aún poseen miembros.
- Grupos eliminados sin miembros (informativo).
"""

import logging
from pathlib import Path
from datetime import datetime
import mysql.connector

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import OLD_DB

LOGDIR = Path("logs")
LOGDIR.mkdir(exist_ok=True)
LOGFILE = LOGDIR / f"06_3_validar_grupos_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)

conn = mysql.connector.connect(**OLD_DB)
cur = conn.cursor(dictionary=True)

try:
    print("[*] Validando grupos...")

    cur.execute("""
    SELECT user_id,
           LOWER(TRIM(name)) grupo,
           COUNT(*) cantidad
    FROM contactgroups
    WHERE del=0
    GROUP BY user_id, LOWER(TRIM(name))
    HAVING COUNT(*)>1
    """)
    dup = cur.fetchall()

    cur.execute("""
    SELECT COUNT(*) c
    FROM contactgroupmembers gm
    LEFT JOIN contactgroups g
      ON gm.contactgroup_id=g.contactgroup_id
    WHERE g.contactgroup_id IS NULL
    """)
    huerfanos = cur.fetchone()["c"]

    cur.execute("""
    SELECT contactgroup_id,user_id,name
    FROM contactgroups g
    WHERE del=1
      AND NOT EXISTS(
        SELECT 1
        FROM contactgroupmembers gm
        WHERE gm.contactgroup_id=g.contactgroup_id
      )
    """)
    eliminables = cur.fetchall()

    cur.execute("""
    SELECT g.contactgroup_id,g.user_id,g.name,
           COUNT(gm.contact_id) miembros
    FROM contactgroups g
    JOIN contactgroupmembers gm
      ON gm.contactgroup_id=g.contactgroup_id
    WHERE g.del=1
    GROUP BY g.contactgroup_id,g.user_id,g.name
    """)
    del_con_miembros = cur.fetchall()

    logging.info("Duplicados activos: %d", len(dup))
    logging.info("Referencias huerfanas: %d", huerfanos)
    logging.info("Grupos del=1 sin miembros: %d", len(eliminables))
    logging.info("Grupos del=1 con miembros: %d", len(del_con_miembros))

    print("="*70)
    print("RESUMEN")
    print("="*70)
    print("Grupos activos duplicados :", len(dup))
    print("Referencias huérfanas     :", huerfanos)
    print("Grupos del=1 sin miembros :", len(eliminables))
    print("Grupos del=1 con miembros :", len(del_con_miembros))
    print("Log                       :", LOGFILE)

    if dup:
        print("\n[!] Grupos activos duplicados:")
        for d in dup:
            print(f"    user={d['user_id']} grupo='{d['grupo']}' cantidad={d['cantidad']}")
    else:
        print("\n[+] No existen grupos activos duplicados.")

finally:
    cur.close()
    conn.close()
