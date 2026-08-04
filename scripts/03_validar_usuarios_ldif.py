#!/usr/bin/env python3
"""
03_validar_usuarios_ldif.py

Valida el archivo usuarios.ldif antes de generar el CSV para iRedMail.

Verificaciones realizadas:

- Usuarios sin atributo mail
- Correos duplicados
- employeeNumber duplicados
- Registros de prueba (cn conocidos)
- Registros sin uid
- Registros sin cn
- Registros sin givenName o sn

No modifica el archivo.
Sólo genera un informe por pantalla.
"""

from collections import defaultdict
import csv

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config import DOMINIOS_INSTITUCIONALES

ARCHIVO = "usuarios.ldif"

usuarios = []
actual = {}

with open(ARCHIVO, encoding="utf-8") as f:

    for linea in f:

        linea = linea.rstrip()

        if not linea:

            if actual:
                usuarios.append(actual)
                actual = {}

            continue

        if ": " not in linea:
            continue

        clave, valor = linea.split(": ", 1)

        if clave not in actual:
            actual[clave] = valor

if actual:
    usuarios.append(actual)

print("=" * 70)
print("VALIDACIÓN DEL LDIF")
print("=" * 70)
print()

print(f"Usuarios encontrados: {len(usuarios)}")
print()

# ----------------------------------------------------
# Correos duplicados
# ----------------------------------------------------

mails = defaultdict(list)

for u in usuarios:

    mail = u.get("mail", "").lower()

    if mail:
        mails[mail].append(u)

duplicados = {k: v for k, v in mails.items() if len(v) > 1}

print(f"Correos duplicados: {len(duplicados)}")

for mail, regs in sorted(duplicados.items()):

    print(f"\n{mail}")

    for r in regs:
        print(
            f"   uid={r.get('uid','')} "
            f"employeeNumber={r.get('employeeNumber','')} "
            f"cn={r.get('cn','')}"
        )

print()

# ----------------------------------------------------
# employeeNumber duplicados
# ----------------------------------------------------

emp = defaultdict(list)

for u in usuarios:

    e = u.get("employeeNumber", "")

    if e:
        emp[e].append(u)

emp_dup = {k: v for k, v in emp.items() if len(v) > 1}

print(f"employeeNumber duplicados: {len(emp_dup)}")

for e, regs in sorted(emp_dup.items()):

    print(f"\n{e}")

    for r in regs:
        print(
            f"   uid={r.get('uid','')} "
            f"mail={r.get('mail','')}"
        )

print()

# ----------------------------------------------------
# Usuarios sin mail
# ----------------------------------------------------

sin_mail = [u for u in usuarios if not u.get("mail")]

print(f"Usuarios sin mail: {len(sin_mail)}")

for u in sin_mail:

    print(f"   uid={u.get('uid','')} cn={u.get('cn','')}")

print()

# ----------------------------------------------------
# Usuarios sin uid
# ----------------------------------------------------

sin_uid = [u for u in usuarios if not u.get("uid")]

print(f"Usuarios sin uid: {len(sin_uid)}")

for u in sin_uid:

    print(f"   mail={u.get('mail','')}")

print()

# ----------------------------------------------------
# Usuarios sin nombre
# ----------------------------------------------------

sin_cn = [u for u in usuarios if not u.get("cn")]

print(f"Usuarios sin cn: {len(sin_cn)}")

for u in sin_cn:

    print(
        f"   uid={u.get('uid','')} "
        f"mail={u.get('mail','')}"
    )

print()

# ----------------------------------------------------
# givenName o sn faltantes
# ----------------------------------------------------

sin_nombre = [
    u for u in usuarios
    if not u.get("givenName") or not u.get("sn")
]

print(f"Usuarios con nombre incompleto: {len(sin_nombre)}")

for u in sin_nombre:

    print(
        f"   {u.get('mail','')} "
        f"givenName='{u.get('givenName','')}' "
        f"sn='{u.get('sn','')}'"
    )

print()

# ----------------------------------------------------
# Cuentas de prueba conocidas
# ----------------------------------------------------

PRUEBA_CN = {
    "probando",
    "yeti",
}

prueba = []

for u in usuarios:

    cn = u.get("cn", "").strip().lower()

    if cn in PRUEBA_CN:
        prueba.append(u)

print(f"Registros de prueba conocidos: {len(prueba)} - {PRUEBA_CN}")

for u in prueba:

    print(
        f"   uid={u.get('uid','')} "
        f"mail={u.get('mail','')}"
    )

print()


# ----------------------------------------------------
# Usuarios con dominios no institucionales
# ----------------------------------------------------

no_institucionales = []

for u in usuarios:

    mail = u.get("mail", "").strip().lower()

    if not mail or "@" not in mail:
        continue

    dominio = mail.rsplit("@", 1)[1]

    if dominio not in DOMINIOS_INSTITUCIONALES:

        no_institucionales.append({
            "uid": u.get("uid", ""),
            "mail": mail,
            "dominio": dominio,
            "cn": u.get("cn", "")
        })

print(f"Usuarios con dominios no institucionales: {len(no_institucionales)}")

for u in no_institucionales:
    print(f"   {u['mail']}")

if no_institucionales:

    with open(
        "usuarios_dominios_no_institucionales.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        w = csv.writer(f)

        w.writerow([
            "uid",
            "mail",
            "dominio",
            "cn"
        ])

        for u in no_institucionales:

            w.writerow([
                u["uid"],
                u["mail"],
                u["dominio"],
                u["cn"]
            ])

print()


# ----------------------------------------------------
# Resumen
# ----------------------------------------------------

print("=" * 70)
print("RESUMEN")
print("=" * 70)

print(f"Usuarios.........................: {len(usuarios)}")
print(f"Correos duplicados...............: {len(duplicados)}")
print(f"employeeNumber duplicados........: {len(emp_dup)}")
print(f"Sin mail.........................: {len(sin_mail)}")
print(f"Sin uid..........................: {len(sin_uid)}")
print(f"Sin cn...........................: {len(sin_cn)}")
print(f"Nombre incompleto............... : {len(sin_nombre)}")
print(f"Registros de prueba..............: {len(prueba)}")
print(f"Dominios no institucionales......: {len(no_institucionales)}")

print()

print("Archivos generados:")

if no_institucionales:
    print(" - usuarios_dominios_no_institucionales.csv")