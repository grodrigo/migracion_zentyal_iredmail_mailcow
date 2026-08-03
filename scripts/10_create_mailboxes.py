import csv
import subprocess

archivo_csv = 'usuarios_iredmail.csv'

print(f"[*] Iniciando la creación de buzones desde {archivo_csv}...")

try:
    with open(archivo_csv, mode='r', encoding='utf-8') as f:
        lector = csv.reader(f)
        
        contador = 0
        for fila in lector:
            # Asegurarnos de que la línea no esté vacía y tenga las columnas necesarias
            if len(fila) < 2:
                continue
                
            dominio = fila[0].strip()
            usuario = fila[1].strip()
            
            if usuario and dominio:
                correo = f"{usuario}@{dominio}"
                print(f"[*] Creando estructura de buzón para: {correo}")
                
                # Ejecutamos el comando de doveadm de forma segura desde Python
                comando = ["doveadm", "mailbox", "create", "-u", correo, "INBOX"]
                resultado = subprocess.run(comando, capture_output=True, text=True)
                
                if resultado.returncode != 0:
                    print(f"[!] Error al crear buzón para {correo}: {resultado.stderr.strip()}")
                else:
                    contador += 1

    print(f"[+] ¡Proceso finalizado! Se crearon/verificaron {contador} buzones.")

except FileNotFoundError:
    print(f"[X] Error: No se encontró el archivo {archivo_csv} en este directorio.")
