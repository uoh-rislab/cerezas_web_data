# Envío programado de boletines por Gmail

La integración queda preparada, pero **deshabilitada por defecto**. No se enviará ningún correo
hasta que se configuren los destinatarios, la cuenta delegada y `enabled: true` en
`config/email.yaml`.

Cada PDF se envía en un mensaje independiente al beneficiario asociado a su `site ID`. Los tres
contactos globales configurados bajo `global_cc` se agregan en copia a todos los mensajes.

## Horario

El envío automático se intenta a las **04:00 en `America/Santiago`**. A diferencia del pipeline de
datos, este horario sigue la hora civil de Chile y, por lo tanto, se adapta automáticamente a los
cambios entre horario de verano e invierno.

El correo solo se envía cuando el pipeline correspondiente terminó correctamente y su
`manifest.json` tiene estado `complete`. Si todavía está procesando a las 04:00, el scheduler espera
y vuelve a comprobarlo. Los mensajes enviados se registran en
`/data/state/scheduler.db` para evitar duplicados después de un reinicio.

## Configurar destinatarios

Editar el archivo de configuración persistente del servidor:

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

Ejemplo para un beneficiario:

```yaml
sites:
  fic1-rengo-agritorre:
    to:
      - name: Nombre Beneficiario
        email: beneficiario@example.com
    cc:
      - name: Copia específica
        email: copia@example.com
```

- `to` contiene los destinatarios principales del PDF.
- `cc` contiene copias específicas de ese beneficiario.
- `global_cc` contiene las copias aplicadas a todos los mensajes.
- Las direcciones repetidas en CC se eliminan automáticamente.

Por ahora, YAML es la opción más simple, auditable y segura. Más adelante se puede reemplazar la
fuente de destinatarios por Google Sheets sin modificar las plantillas ni el envío. Un dashboard
conviene cuando además se necesiten permisos, validaciones, historial y una interfaz para usuarios
no técnicos.

## Preparar Google Workspace

Se recomienda una cuenta de servicio con delegación de todo el dominio. La cuenta de servicio no
envía como sí misma: suplanta exclusivamente la casilla institucional indicada en
`sender.delegated_user`.

1. Crear o seleccionar un proyecto en Google Cloud.
2. Habilitar Gmail API.
3. Crear una cuenta de servicio y habilitar la delegación de todo el dominio.
4. Descargar su clave JSON.
5. En Google Workspace Admin, autorizar el **Client ID numérico** de la cuenta de servicio con el
   único scope:

   ```text
   https://www.googleapis.com/auth/gmail.send
   ```

6. Definir en el `email.yaml` persistente la casilla institucional desde la cual se enviará:

   ```yaml
   sender:
     display_name: Universidad de O'Higgins - Proyecto FIC Cerezas
     delegated_user: remitente@uoh.cl
     service_account_file: /run/secrets/gmail-service-account.json
   ```

## Instalar el secreto en el servidor

El JSON es un secreto y no debe guardarse en Git ni dentro de la imagen:

```bash
mkdir -p /home/uoh/cerezas_web_server/secrets/climate-reporting
cp /path/to/downloaded-service-account.json \
  /home/uoh/cerezas_web_server/secrets/climate-reporting/gmail-service-account.json
chmod 700 /home/uoh/cerezas_web_server/secrets/climate-reporting
chmod 600 /home/uoh/cerezas_web_server/secrets/climate-reporting/gmail-service-account.json
```

Verificar esta ruta en `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_HOST_PATH=/home/uoh/cerezas_web_server/secrets/climate-reporting/gmail-service-account.json
```

`compose.email.yaml` monta el secreto como archivo de solo lectura. Mientras Gmail no esté
habilitado se puede seguir usando `docker compose` normalmente, sin ese override.

## Actualizar la configuración externa

Después de actualizar el repositorio, incorporar el nuevo archivo sin reemplazar otros ajustes:

```bash
cp config/email.yaml /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

Mantener inicialmente:

```yaml
enabled: false
```

## Previsualizar sin enviar

La previsualización no requiere credenciales ni destinatarios. Utiliza un PDF ya generado y
muestra asunto, To, CC y archivo adjunto:

```bash
docker compose run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre
```

Ejemplos para weekly y monthly:

```bash
docker compose run --rm climate-reporting email \
  --kind weekly --scheduled-date 2026-06-29 --site fic1-rengo-agritorre

docker compose run --rm climate-reporting email \
  --kind monthly --scheduled-date 2026-07-01 --site fic1-rengo-agritorre
```

Sin `--send` jamás se llama a Gmail API.

## Realizar un envío controlado

Primero configurar un único destinatario de prueba y cambiar a:

```yaml
enabled: true
```

Luego reconstruir la imagen y probar un solo site:

```bash
docker compose build
docker compose -f compose.yaml -f compose.email.yaml run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre \
  --send
```

El comando responde con `status: sent` y el identificador del mensaje Gmail. Un segundo intento con
la misma fecha, tipo y site responde `already sent`.

## Activar el envío programado

Una vez aprobada la prueba:

```bash
docker compose -f compose.yaml -f compose.email.yaml up -d
docker compose -f compose.yaml -f compose.email.yaml ps
docker compose -f compose.yaml -f compose.email.yaml logs --tail=100 -f climate-reporting
```

Cuando Gmail está habilitado, usar ambos archivos Compose también para futuras recreaciones del
servicio. Los cambios en `email.yaml` se aplican al reiniciar el contenedor:

```bash
docker compose -f compose.yaml -f compose.email.yaml restart climate-reporting
```

## Deshabilitar envíos

Cambiar `enabled: false` y recrear el servicio:

```bash
docker compose -f compose.yaml -f compose.email.yaml up -d --force-recreate
```

Esto no afecta la generación diaria, semanal o mensual de datos y PDF.
