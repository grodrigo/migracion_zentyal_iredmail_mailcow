#!/usr/bin/env python3
"""
06_1_normalizar_usuarios.py

Genera user_normalization_map dentro de roundcube_old.

La tabla se utiliza por los siguientes scripts de normalización.
No modifica datos funcionales; únicamente determina qué user_id
será el principal para cada dirección de correo.
"""

import csv
import mysql.connector
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import OLD_DB

print("[*] Conectando...")

old_conn = mysql.connector.connect(**OLD_DB)

old = old_conn.cursor(dictionary=True)

print("[*] Recreando user_normalization_map...")

old.execute("DROP TABLE IF EXISTS user_normalization_map")

old.execute("""
CREATE TABLE user_normalization_map (
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

old_conn.commit()

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

with open("./work/user_normalization_map.csv", "w", newline="", encoding="utf-8") as f:

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

            old.execute("""
                INSERT INTO user_normalization_map
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

old_conn.commit()

print()
print(f"[+] Usuarios analizados    : {total}")
print(f"[+] Usuarios normalizados  : {len(grupos)}")
print(f"[+] Usuarios principales   : {principales}")
print(f"[+] Correos duplicados     : {duplicados}")
print("[+] CSV generado           : ./work/user_normalization_map.csv")

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
old_conn.close()

print("[+] Finalizado.")
