import csv

# Configuración de rutas de archivos
archivo_csv = '/root/migration/usuarios_test.csv'
archivo_ldif_salida = '/root/migration/scripts/enriquecer_usuarios.ldif'

# Configuración del entorno LDAP e iRedMail
BASE_DN = "o=domains,dc=mp,dc=gba,dc=gov,dc=ar"
DOMINIO_POC = "testmail1.mp.gba.gov.ar"

print(f"[*] Procesando {archivo_csv} para generar modificaciones LDAP...")

with open(archivo_csv, mode='r', encoding='utf-8') as f_in, \
     open(archivo_ldif_salida, mode='w', encoding='utf-8') as f_out:
    
    lector = csv.DictReader(f_in)
    contador = 0
    
    for fila in lector:
        uid = fila['uid'].strip()
        mail = fila['mail'].strip()
        given_name = fila['givenName'].strip()
        sn = fila['sn'].strip()
        employee_number = fila['employeeNumber'].strip()
        description = fila['description'].strip()
        
        # Validación mínima de datos requeridos
        if not uid or not mail:
            continue
            
        # Extraer el dominio del correo electrónico
        dominio_user = mail.split('@')[1] if '@' in mail else 'mp.gba.gov.ar'
        
        # Construir el DN idéntico al esquema iRedMail verificado
        dn = f"mail={mail},ou=Users,domainName={dominio_user},{BASE_DN}"
        
        # Construir el shadowAddress dinámico para la POC
        shadow_address = f"{uid}@{DOMINIO_POC}"
        
        # Escribir el bloque de modificación en el archivo LDIF
        f_out.write(f"dn: {dn}\n")
        f_out.write("changetype: modify\n")
        
        # Atributo: givenName
        if given_name:
            f_out.write("replace: givenName\n")
            f_out.write(f"givenName: {given_name}\n")
            f_out.write("-\n")
            
        # Atributo: sn (Apellido)
        if sn:
            f_out.write("replace: sn\n")
            f_out.write(f"sn: {sn}\n")
            f_out.write("-\n")
            
        # Atributo: employeeNumber (Solo si contiene datos)
        if employee_number:
            f_out.write("replace: employeeNumber\n")
            f_out.write(f"employeeNumber: {employee_number}\n")
            f_out.write("-\n")
            
        # Atributo: description (Solo si contiene datos)
        if description:
            f_out.write("replace: description\n")
            f_out.write(f"description: {description}\n")
            f_out.write("-\n")
            
        # Atributo de la POC: shadowAddress
        f_out.write("replace: shadowAddress\n")
        f_out.write(f"shadowAddress: {shadow_address}\n")
        f_out.write("-\n")
        
        # Separador de registros en archivos LDIF (línea en blanco)
        f_out.write("\n")
        contador += 1

print(f"[+] Archivo LDIF generado exitosamente en: {archivo_ldif_salida}")
print(f"[+] Se prepararon modificaciones para {contador} usuarios.")
