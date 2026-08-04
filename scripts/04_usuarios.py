import csv

usuarios = []
actual = {}

with open("usuarios.ldif", encoding="utf-8") as f:
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

        if clave in [
            "uid",
            "mail",
            "cn",
            "givenName",
            "sn",
            "quota",
            "employeeNumber",
            "description"
        ]:
            actual[clave] = valor

if actual:
    usuarios.append(actual)

with open("usuarios.csv", "w", newline="", encoding="utf-8") as f:
    campos = [
        "uid",
        "mail",
        "cn",
        "givenName",
        "sn",
        "quota",
        "employeeNumber",
        "description"
    ]

    w = csv.DictWriter(f, fieldnames=campos)
    w.writeheader()

    for u in usuarios:
        w.writerow(u)

print(f"{len(usuarios)} usuarios exportados a usuarios.csv")
