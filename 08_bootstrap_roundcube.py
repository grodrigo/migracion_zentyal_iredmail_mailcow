#!/usr/bin/env python3

import csv
import mysql.connector

CSV_FILE = "/root/migration/usuarios_test.csv"

DB_CONFIG = {
"host": "127.0.0.1",
"user": "YOUR_DB_USER",
"password": "YOUR_DB_PASSWORD",
"database": "roundcubemail"
}

MAIL_HOST = "127.0.0.1"
LANGUAGE = "es_AR"

print(f"[*] Leyendo usuarios desde: {CSV_FILE}")

conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()

creados = 0
existentes = 0

with open(CSV_FILE, mode="r", encoding="utf-8") as f:

    reader = csv.DictReader(f)

    for row in reader:

        mail = row["mail"].strip().lower()
        cn = row["cn"].strip()

        if not mail:
            continue

        cur.execute(
            """
            SELECT user_id
            FROM users
            WHERE username = %s
            """,
            (mail,)
        )

        result = cur.fetchone()

        if result:

            user_id = result[0]
            existentes += 1

            print(f"[SKIP] {mail} ya existe (user_id={user_id})")

        else:

            cur.execute(
                """
                INSERT INTO users
                (
                    username,
                    mail_host,
                    created,
                    language
                )
                VALUES
                (
                    %s,
                    %s,
                    NOW(),
                    %s
                )
                """,
                (
                    mail,
                    MAIL_HOST,
                    LANGUAGE
                )
            )

            user_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO identities
                (
                    user_id,
                    changed,
                    del,
                    standard,
                    name,
                    email
                )
                VALUES
                (
                    %s,
                    NOW(),
                    0,
                    1,
                    %s,
                    %s
                )
                """,
                (
                    user_id,
                    cn,
                    mail
                )
            )

            conn.commit()

            creados += 1

            print(f"[OK] {mail} creado (user_id={user_id})")

print()
print(f"[+] Usuarios creados: {creados}")
print(f"[+] Usuarios existentes: {existentes}")

cur.close()
conn.close()

print("[+] Finalizado.")
