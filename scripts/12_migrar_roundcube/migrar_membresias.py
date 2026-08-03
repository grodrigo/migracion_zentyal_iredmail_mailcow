#!/usr/bin/env python3
# migrar_membresias.py

import mysql.connector

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import NEW_DB

print("[*] Conectando a base destino...")

conn = mysql.connector.connect(**NEW_DB)
cur = conn.cursor(dictionary=True, buffered=True)

miembros_creados = 0
miembros_existentes = 0
sin_mapeo_contacto = 0
sin_mapeo_grupo = 0

print("[*] Migrando membresias...")

cur.execute("""
SELECT
    ogm.old_group_id,
    ocm.old_contact_id,
    ogm.new_group_id,
    ocm.new_contact_id
FROM migration_group_map ogm
JOIN roundcube_old.contactgroupmembers src
    ON src.contactgroup_id = ogm.old_group_id
JOIN migration_contact_map ocm
    ON ocm.old_contact_id = src.contact_id
WHERE ogm.new_user_id = ocm.new_user_id;
""")

rows = cur.fetchall()
print(f"[*] {len(rows)} membresías encontradas.")

try:
    for row in rows:

        new_group_id = row["new_group_id"]
        new_contact_id = row["new_contact_id"]

        if not new_group_id:
            sin_mapeo_grupo += 1
            continue

        if not new_contact_id:
            sin_mapeo_contacto += 1
            continue

        cur.execute("""
            SELECT 1
            FROM contactgroupmembers
            WHERE contactgroup_id=%s
            AND contact_id=%s
        """, (
            new_group_id,
            new_contact_id
        ))

        existing = cur.fetchone()

        if existing:
            miembros_existentes += 1
            continue

        cur.execute("""
            INSERT INTO contactgroupmembers
            (
                contactgroup_id,
                contact_id,
                created
            )
            VALUES
            (
                %s,
                %s,
                NOW()
            )
        """, (
            new_group_id,
            new_contact_id
        ))

        miembros_creados += 1

        if miembros_creados % 500 == 0:
            conn.commit()

    conn.commit()

except Exception:
    print("[!] Error durante la migración.")
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()

print()
print(f"[+] Membresias creadas: {miembros_creados}")
print(f"[+] Membresias existentes: {miembros_existentes}")
print(f"[+] Sin mapeo contacto: {sin_mapeo_contacto}")
print(f"[+] Sin mapeo grupo: {sin_mapeo_grupo}")

print("""
    Recordar eliminar las tablas auxiliares luego de validar la migración:

    DROP TABLE migration_contact_map;
    DROP TABLE migration_group_map;
""")

print("[+] Finalizado.")
