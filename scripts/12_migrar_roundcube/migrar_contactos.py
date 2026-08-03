#!/usr/bin/env python3
# migrar_contactos_v2.py

"""
Migración de contactos Roundcube.

Origen:
    roundcube_old

Destino:
    roundcubemail

Este script puede ejecutarse múltiples veces.
No duplica registros ya migrados.
Genera la tabla migration_contact_map utilizada posteriormente
por la migración de grupos y membresías.
"""

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
# Tabla de mapeo para futuras migraciones de grupos/membresias
# ------------------------------------------------------------

new_cur.execute("""
CREATE TABLE IF NOT EXISTS migration_contact_map (
    old_contact_id INT UNSIGNED PRIMARY KEY,
    new_contact_id INT UNSIGNED NOT NULL,
    old_user_id INT UNSIGNED NOT NULL,
    new_user_id INT UNSIGNED NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX(old_user_id),
    INDEX(new_contact_id),
    INDEX(new_user_id)
)
""")

new_conn.commit()

contactos_creados = 0
contactos_existentes = 0
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

print("[*] Migrando contactos...")

old_cur.execute("""
SELECT
    c.contact_id,
    c.changed,
    c.del,
    c.name,
    c.email,
    c.firstname,
    c.surname,
    c.vcard,
    u.user_id,
    u.username
FROM contacts c
JOIN users u
ON u.user_id=c.user_id
""")

try:
    for row in old_cur.fetchall():

        username = row["username"].lower()
        old_user_id = row["user_id"]
        
        if MODO_POC and username not in USUARIOS_POC:
            continue

        if username not in usuarios_destino:
            continue

        old_contact_id = row["contact_id"]
        new_user_id = usuarios_destino[username]

        # Ya existe el mapeo?
        new_cur.execute("""
            SELECT new_contact_id
            FROM migration_contact_map
            WHERE old_contact_id=%s
        """, (old_contact_id,))

        mapping = new_cur.fetchone()

        if mapping:
            continue

        # Buscar contacto existente
        new_cur.execute("""
            SELECT contact_id
            FROM contacts
            WHERE user_id=%s
            AND email=%s
            AND name=%s
        """, (
            new_user_id,
            row["email"],
            row["name"]
        ))

        existing = new_cur.fetchone()

        if existing:

            new_contact_id = existing["contact_id"]
            contactos_existentes += 1

        else:

            new_cur.execute("""
                INSERT INTO contacts
                (
                    changed,
                    del,
                    name,
                    email,
                    firstname,
                    surname,
                    vcard,
                    user_id
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s,%s
                )
            """, (
                row["changed"],
                row["del"],
                row["name"],
                row["email"],
                row["firstname"],
                row["surname"],
                row["vcard"],
                new_user_id
            ))

            new_contact_id = new_cur.lastrowid
            contactos_creados += 1

        new_cur.execute("""
            INSERT INTO migration_contact_map
            (
                old_contact_id,
                new_contact_id,
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
            old_contact_id,
            new_contact_id,
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
print(f"[+] Contactos creados: {contactos_creados}")
print(f"[+] Contactos existentes: {contactos_existentes}")
print(f"[+] Mapeos creados: {mapeos_creados}")

print("[+] Finalizado.")
