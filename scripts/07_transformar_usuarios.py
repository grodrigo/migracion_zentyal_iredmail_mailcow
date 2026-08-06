import csv

# Configuración de archivos
#archivo_origen = '../usuarios_test.csv'
archivo_origen = './work/usuarios.csv'
#archivo_destino = '../usuarios_iredmail.csv'
archivo_destino = './work/usuarios_iredmail.csv'

# Configuración por defecto para la migración
PASSWORD_POR_DEFECTO = 'YOUR_DEFAULT_PASSWORD'
DOMINIO_POR_DEFECTO = 'mp.gba.gov.ar'

print(f"[*] Iniciando la transformación de {archivo_origen}...")

with open(archivo_origen, mode='r', encoding='utf-8') as f_in, \
     open(archivo_destino, mode='w', encoding='utf-8', newline='') as f_out:
    
    lector = csv.DictReader(f_in)
    escritor = csv.writer(f_out)
    
    contados = 0
    for fila in lector:
        # 1. Extraer el nombre de usuario (uid)
        username = fila['uid'].strip()
        
        # 2. Extraer el dominio del campo mail (o usar el por defecto si falla)
        correo = fila['mail'].strip()
        if '@' in correo:
            dominio = correo.split('@')[1]
        else:
            dominio = DOMINIO_POR_DEFECTO
            
        # 3. Obtener el Common Name (cn)
        cn = fila['cn'].strip()
        
        # 4. Convertir la cuota de MB a Bytes
        cuota_origen = fila['quota'].strip()
        if cuota_origen and cuota_origen.isdigit():
            # Ejemplo: 400 MB * 1024 * 1024 = 419430400 Bytes
            cuota_bytes = int(cuota_origen) * 1024 * 1024
	    # couta_bytes mejor para la poc lo dejaremos bajo, en 100MB
            cuota_bytes = 100 * 1024 * 1024
        else:
            cuota_bytes = '' # El script de iRedMail lo tomará como 0 (unlimited)
            
        # 5. Los grupos se dejan vacíos por ahora (se pueden manejar en el Script B o D)
        grupos = ''
        
        # Escribir la línea con el formato requerido por iRedMail:
        # domain name, username, password, [common name], [quota_in_bytes], [groups]
        escritor.writerow([dominio, username, PASSWORD_POR_DEFECTO, cn, cuota_bytes, grupos])
        contados += 1

print(f"[+] ¡Transformación completada con éxito! Se procesaron {contados} usuarios.")
print(f"[+] Archivo generado listo para iRedMail: {archivo_destino}")
