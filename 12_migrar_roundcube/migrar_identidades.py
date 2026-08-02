#!/usr/bin/env python3
# migrar_identidades.py

import mysql.connector
from config import OLD_DB, NEW_DB, MODO_POC, USUARIOS_POC

print("[*] Conectando a bases de datos...")

old_conn = mysql.connector.connect(**OLD_DB)
new_conn = mysql.connector.connect(**NEW_DB)

old_cur = old_conn.cursor(dictionary=True, buffered=True)
new_cur = new_conn.cursor(dictionary=True, buffered=True)

identidades_creadas = 0
identidades_existentes = 0

print("[*] Cargando usuarios destino...")

new_cur.execute("""
SELECT
    user_id,
    LOWER(username) AS username
FROM users
""")

usuarios_destino = {}

for row in new_cur.fetchall():
    usuarios_destino[row["username"]] = row["user_id"]

print(f"[+] Usuarios destino: {len(usuarios_destino)}")

print("[*] Migrando identidades...")

old_cur.execute("""
SELECT
    i.identity_id,
    i.changed,
    i.del,
    i.standard,
    i.name,
    i.organization,
    i.email,
    i.`reply-to`,
    i.bcc,
    i.signature,
    i.html_signature,
    u.user_id,
    LOWER(u.username) AS username
FROM roundcube_old.identities i
JOIN roundcube_old.users u
    ON u.user_id=i.user_id
WHERE i.del=0
ORDER BY
    LOWER(u.username),
    i.standard DESC,
    i.identity_id
""")

try:

    for row in old_cur.fetchall():

        username = row["username"]
        old_user_id = row["user_id"]

        if MODO_POC and username not in USUARIOS_POC:
            continue

        if username not in usuarios_destino:
            continue

        new_user_id = usuarios_destino[username]

        #
        # Ya existe exactamente la misma identidad?
        #

        new_cur.execute("""
        SELECT identity_id
        FROM identities
        WHERE user_id=%s
          AND LOWER(email)=LOWER(%s)
          AND standard=%s
        """,
        (
            new_user_id,
            row["email"],
            row["standard"]
        ))

        existing = new_cur.fetchone()

        if existing:
            identidades_existentes += 1
            continue

        #
        # Insertar identidad
        #

        new_cur.execute("""
        INSERT INTO identities
        (
            user_id,
            changed,
            del,
            standard,
            name,
            organization,
            email,
            `reply-to`,
            bcc,
            signature,
            html_signature
        )
        VALUES
        (
            %s,
            %s,
            0,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            new_user_id,
            row["changed"],
            row["standard"],
            row["name"],
            row["organization"],
            row["email"],
            row["reply-to"],
            row["bcc"],
            row["signature"],
            row["html_signature"]
        ))

        identidades_creadas += 1

        if identidades_creadas % 500 == 0:
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
print(f"[+] Identidades creadas: {identidades_creadas}")
print(f"[+] Identidades existentes: {identidades_existentes}")
print("[+] Finalizado.")