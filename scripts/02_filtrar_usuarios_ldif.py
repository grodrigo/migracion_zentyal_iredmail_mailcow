#!/usr/bin/env python3
"""
02_filtrar_usuarios_ldif.py

Genera un LDIF simplificado a partir de la exportación completa del LDAP.

Entrada:
    ldap_usuarios_completo.ldif

Salida:
    usuarios.ldif

Se conservan únicamente los atributos necesarios para la migración a
iRedMail.

Atributos exportados:

    dn
    uid
    quota
    mail
    employeeNumber
    cn
    givenName
    sn
    description

Sólo se exportan entradas inetOrgPerson.
"""

from pathlib import Path
from migration_utils import reset_state, mark_step
reset_state()

#ENTRADA = "ldap_usuarios_completo.ldif"
ENTRADA = "zentyal-ldap.ldif"
SALIDA = "usuarios.ldif"

ATRIBUTOS = [
    "dn",
    "uid",
    "quota",
    "mail",
    "employeeNumber",
    "cn",
    "givenName",
    "sn",
    "description",
]

def escribir_usuario(fout, datos):
    for campo in ATRIBUTOS:
        if campo in datos:
            fout.write(f"{campo}: {datos[campo]}\n")
    fout.write("\n")


with open(ENTRADA, encoding="utf-8", errors="ignore") as fin, \
     open(SALIDA, "w", encoding="utf-8") as fout:

    usuario = {}
    inetorgperson = False

    for linea in fin:

        linea = linea.rstrip()

        if linea == "":

            if usuario and inetorgperson:
                escribir_usuario(fout, usuario)

            usuario = {}
            inetorgperson = False
            continue

        if linea.startswith("objectClass: inetOrgPerson"):
            inetorgperson = True
            continue

        if ": " not in linea:
            continue

        clave, valor = linea.split(": ", 1)

        if clave in ATRIBUTOS and clave not in usuario:
            usuario[clave] = valor

print(f"Archivo generado: {SALIDA}")

mark_step("02_filtrar_usuarios_ldif")