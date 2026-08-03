#!/usr/bin/env python3
# migrar_grupos.py

import mysql.connector

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import OLD_DB, NEW_DB, MODO_POC, USUARIOS_POC

print("[*] Conectando a bases de datos...")

old_conn = mysql.connector.connect(**OLD_DB)
new_conn = mysql.connector.connect(**NEW_DB)

old_cur = old_conn.cursor(dictionary=True, buffered=True)
new_cur = new_conn.cursor(dictionary=True, buffered=True)

# ------------------------------------------------------------
# Tabla de mapeo para grupos
# ------------------------------------------------------------

new_cur.execute("""
CREATE TABLE IF NOT EXISTS migration_group_map (
    old_group_id INT UNSIGNED PRIMARY KEY,
    new_group_id INT UNSIGNED NOT NULL,
    old_user_id INT NOT NULL,
    new_user_id INT NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX(old_user_id),
    INDEX(new_user_id),
    INDEX(new_group_id)
)
""")

new_conn.commit()

grupos_creados = 0
grupos_existentes = 0
mapeos_creados = 0

print("[*] Cargando usuarios destino...")

new_cur.execute("""
SELECT user_id, LOWER(username) AS username
FROM users
""")

usuarios_destino = {}

for row in new_cur.fetchall():
    usuarios_destino[row["username"].lower()] = row["user_id"]

print(f"[+] Usuarios destino: {len(usuarios_destino)}")

print("[*] Migrando grupos...")

old_cur.execute("""
SELECT
    cg.contactgroup_id,
    cg.user_id,
    cg.changed,
    cg.del,
    cg.name,
    u.username
FROM contactgroups cg
JOIN users u
  ON u.user_id = cg.user_id
""")

try:
    for row in old_cur.fetchall():

        username = row["username"].lower()
        old_user_id = row["user_id"]
        
        if MODO_POC and username not in USUARIOS_POC:
            continue

        if username not in usuarios_destino:
            continue

        old_group_id = row["contactgroup_id"]
        new_user_id = usuarios_destino[username]

        # ¿Ya existe el mapeo?
        new_cur.execute("""
            SELECT new_group_id
            FROM migration_group_map
            WHERE old_group_id=%s
        """, (old_group_id,))

        mapping = new_cur.fetchone()

        if mapping:
            continue

        # ¿Ya existe el grupo en destino?
        new_cur.execute("""
            SELECT contactgroup_id
            FROM contactgroups
            WHERE user_id=%s
            AND name=%s
        """, (
            new_user_id,
            row["name"]
        ))

        existing = new_cur.fetchone()

        if existing:

            new_group_id = existing["contactgroup_id"]
            grupos_existentes += 1

        else:

            new_cur.execute("""
                INSERT INTO contactgroups
                (
                    user_id,
                    changed,
                    del,
                    name
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                new_user_id,
                row["changed"],
                row["del"],
                row["name"]
            ))

            new_group_id = new_cur.lastrowid
            grupos_creados += 1

        new_cur.execute("""
            INSERT INTO migration_group_map
            (
                old_group_id,
                new_group_id,
                old_user_id,
                new_user_id
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
        """, (
            old_group_id,
            new_group_id,
            old_user_id,
            new_user_id
        ))

        mapeos_creados += 1
        if mapeos_creados % 500 == 0:
            new_conn.commit()

    new_conn.commit()

except Exception:
    print("[!] Error durante la migración.")
    new_conn.rollback()
    raise

finally:

    old_cur.close()
    new_cur.close()

    old_conn.close()
    new_conn.close()

print()
print(f"[+] Grupos creados: {grupos_creados}")
print(f"[+] Grupos existentes: {grupos_existentes}")
print(f"[+] Mapeos creados: {mapeos_creados}")

print("[+] Finalizado.")
