#!/usr/bin/env python3
"""
06_1_normalizar_usuarios.py
Genera migration_user_map sin modificar datos.
"""
import csv
import mysql.connector
from config import OLD_DB, NEW_DB

old_conn=mysql.connector.connect(**OLD_DB)
new_conn=mysql.connector.connect(**NEW_DB)
old=old_conn.cursor(dictionary=True)
new=new_conn.cursor(dictionary=True)

new.execute("""
CREATE TABLE IF NOT EXISTS migration_user_map(
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
new.execute("TRUNCATE TABLE migration_user_map")
new_conn.commit()

old.execute("""
SELECT u.user_id,u.username,COUNT(c.contact_id) contactos
FROM users u
LEFT JOIN contacts c ON c.user_id=u.user_id
GROUP BY u.user_id,u.username
ORDER BY LOWER(u.username),contactos DESC,u.user_id
""")

rows=old.fetchall()
grupos={}
for r in rows:
    grupos.setdefault(r["username"].lower(),[]).append(r)

with open("migration_user_map.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["old_user_id","new_user_id","username_original","username_normalizado","es_principal"])
    total=0
    dup=0
    for uname,lst in grupos.items():
        p=sorted(lst,key=lambda x:(-x["contactos"],x["user_id"]))[0]
        if len(lst)>1:
            dup+=1
        for r in lst:
            es=1 if r["user_id"]==p["user_id"] else 0
            new.execute("""INSERT INTO migration_user_map
            (old_user_id,new_user_id,username_original,username_normalizado,es_principal)
            VALUES(%s,%s,%s,%s,%s)""",
            (r["user_id"],p["user_id"],r["username"],uname,es))
            w.writerow([r["user_id"],p["user_id"],r["username"],uname,es])
            total+=1
new_conn.commit()
print(f"Usuarios:{total} Normalizados:{len(grupos)} Duplicados:{dup}")
old.close();new.close();old_conn.close();new_conn.close()
print("OK")
