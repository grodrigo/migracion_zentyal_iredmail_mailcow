#!/usr/bin/env python3
"""
06_1_normalizar_usuarios_v3.py

Genera migration_user_map a partir de roundcube_old.
No modifica datos funcionales; únicamente construye el mapa de
normalización de usuarios.
"""

import csv
import mysql.connector
from config import OLD_DB, NEW_DB

print("[*] Conectando...")

old_conn = mysql.connector.connect(**OLD_DB)
new_conn = mysql.connector.connect(**NEW_DB)

old = old_conn.cursor(dictionary=True)
new = new_conn.cursor(dictionary=True)

print("[*] Recreando migration_user_map...")

new.execute("DROP TABLE IF EXISTS migration_user_map")

new.execute("""
CREATE TABLE migration_user_map (
    old_user_id INT UNSIGNED PRIMARY KEY,
    new_user_id INT UNSIGNED NOT NULL,
    username_original VARCHAR(255) NOT NULL,
    username_normalizado VARCHAR(255) NOT NULL,
    es_principal TINYINT(1) NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX(new_user_id),
    INDEX(username_normalizado)
)
""")

new_conn.commit()

print("[*] Analizando usuarios...")

old.execute("""
SELECT
    u.user_id,
    u.username,
    COUNT(c.contact_id) AS contactos
FROM users u
LEFT JOIN contacts c
    ON c.user_id=u.user_id
GROUP BY u.user_id,u.username
ORDER BY LOWER(u.username), contactos DESC, u.user_id
""")

rows = old.fetchall()

grupos = {}
for r in rows:
    grupos.setdefault(r["username"].lower(), []).append(r)

resumen = []

with open("migration_user_map.csv", "w", newline="", encoding="utf-8") as f:

    w = csv.writer(f)
    w.writerow([
        "old_user_id",
        "new_user_id",
        "username_original",
        "username_normalizado",
        "es_principal"
    ])

    total = 0
    principales = 0
    duplicados = 0

    for usuario, lista in grupos.items():

        lista = sorted(lista, key=lambda x: (-x["contactos"], x["user_id"]))
        principal = lista[0]

        if len(lista) > 1:
            duplicados += 1
            resumen.append((usuario, principal, lista[1:]))

        for r in lista:

            es_principal = int(r["user_id"] == principal["user_id"])

            if es_principal:
                principales += 1

            new.execute("""
                INSERT INTO migration_user_map
                (
                    old_user_id,
                    new_user_id,
                    username_original,
                    username_normalizado,
                    es_principal
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                r["user_id"],
                principal["user_id"],
                r["username"],
                usuario,
                es_principal
            ))

            w.writerow([
                r["user_id"],
                principal["user_id"],
                r["username"],
                usuario,
                es_principal
            ])

            total += 1

new_conn.commit()

print()
print(f"[+] Usuarios analizados    : {total}")
print(f"[+] Usuarios normalizados  : {len(grupos)}")
print(f"[+] Usuarios principales   : {principales}")
print(f"[+] Correos duplicados     : {duplicados}")
print("[+] CSV generado           : migration_user_map.csv")

if resumen:
    print()
    print("=" * 70)
    print("Duplicados encontrados")
    print("=" * 70)

    for usuario, principal, secundarios in resumen:

        print(usuario)
        print()
        print(f"    principal : {principal['user_id']} ({principal['contactos']} contactos)")

        if secundarios:
            print("    secundarios")
            for s in secundarios:
                print(f"        {s['user_id']} ({s['contactos']} contactos)")

        print()

old.close()
new.close()
old_conn.close()
new_conn.close()

print("[+] Finalizado.")
