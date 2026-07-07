# Envío programado de boletines por Gmail

La integración queda preparada, pero **deshabilitada por defecto en la plantilla del repositorio**.
No se enviará ningún correo hasta que se configure el archivo persistente del servidor y
`enabled: true`.

En producción, el contenedor lee este archivo externo:

```text
/home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

El archivo `config/email.yaml` del repositorio es una plantilla/base; no es el archivo operativo si
Compose está montando el directorio persistente de configuración.

Cada PDF se envía en un mensaje independiente al beneficiario asociado a su `site ID`. Los tres
contactos globales configurados bajo `global_cc` se agregan en copia a todos los mensajes.

Hay dos métodos de envío disponibles:

- `smtp`: Gmail SMTP con App Password. Es el método actualmente usado.
- `gmail_api`: Gmail API con Service Account y Domain-wide Delegation. Queda disponible como
  alternativa institucional si más adelante se prefiere evitar App Passwords.

## Horario

El envío automático se intenta a las **05:00 en `America/Santiago`**. A diferencia del pipeline de
datos, este horario sigue la hora civil de Chile y, por lo tanto, se adapta automáticamente a los
cambios entre horario de verano e invierno.

El correo solo se envía cuando el pipeline correspondiente terminó correctamente y su
`manifest.json` tiene estado `complete`. Si todavía está procesando a las 05:00, el scheduler espera
y vuelve a comprobarlo. Los mensajes enviados se registran en
`/data/state/scheduler.db` para evitar duplicados después de un reinicio.

## Configurar destinatarios

Editar el archivo de configuración persistente del servidor:

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

Ejemplo para un beneficiario usando direcciones simples:

```yaml
sites:
  fic1-rengo-agritorre: {to: [beneficiario@example.com, otro@example.com], cc: []}
```

También se puede usar el formato con nombre:

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
- Los destinatarios pueden escribirse como strings simples o como objetos `{name, email}`.

Por ahora, YAML es la opción más simple, auditable y segura. Más adelante se puede reemplazar la
fuente de destinatarios por Google Sheets sin modificar las plantillas ni el envío. Un dashboard
conviene cuando además se necesiten permisos, validaciones, historial y una interfaz para usuarios
no técnicos.

## Opción A: Gmail SMTP con App Password

SMTP es el método actualmente usado. Para esto no se usa el JSON de Service Account. Se necesita:

1. Una casilla Gmail/Workspace remitente, por ejemplo `cerezas@uoh.cl`.
2. Verificación en dos pasos activada en esa casilla.
3. Un **App Password** generado para esa casilla.
4. Que el administrador de Google Workspace permita el uso de App Passwords.

Configurar el archivo persistente:

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

Ejemplo, sin destinatarios sensibles:

```yaml
enabled: true
delivery_method: smtp
timezone: America/Santiago
send_hour: 5
send_minute: 0
retry_minutes: 30

sender:
  display_name: UOH Cerezas
  email: cerezas@uoh.cl
  delegated_user: ""
  service_account_file: /run/secrets/gmail-service-account.json

global_cc: []
#  - name: Daniel Casagrande
#    email: daniel.casagrande@uoh.cl
#  - name: Jaime Varas
#    email: jaime.varas@uoh.cl
#  - name: Luis Gustavo Cossio Montefinale
#    email: luis.cossio@uoh.cl

smtp:
  host: smtp.gmail.com
  port: 587
  username: cerezas@uoh.cl
  password_env: GMAIL_APP_PASSWORD
  password_file: ""
  use_starttls: true
  timeout_seconds: 30

sites:
  fic1-rengo-agritorre:
    to:
      - name: Nombre Beneficiario
        email: beneficiario@example.com
    cc: []
```

Guardar el App Password fuera de Git. La forma más simple es dejarlo en el `.env` del servicio:

```bash
nano /home/uoh/cerezas_web_server/services/climate-reporting/.env
```

```env
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

Como alternativa, se puede usar un archivo secreto y apuntarlo con `smtp.password_file`; si se usa
esa vía, el archivo debe montarse dentro del contenedor con Docker Compose.

Con SMTP no es necesario usar `compose.email.yaml` si el App Password está en `.env`, porque
`compose.yaml` ya carga ese archivo con `env_file`.

## Opción B: preparar Google Workspace para Gmail API

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
   delivery_method: gmail_api

   sender:
     display_name: Universidad de O'Higgins - Proyecto FIC Cerezas
     email: remitente@uoh.cl
     delegated_user: remitente@uoh.cl
     service_account_file: /run/secrets/gmail-service-account.json
   ```

## Instalar el secreto JSON para Gmail API

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

Después de actualizar el repositorio, no reemplazar a ciegas el archivo externo si ya contiene
destinatarios o secretos. Usar `config/email.yaml` como referencia y editar:

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml
```

Para pruebas controladas, mantener temporalmente solo un destinatario y, si se quiere evitar copias
reales, usar:

```yaml
global_cc: []
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

Sin `--send` jamás se llama a Gmail API ni a SMTP.

## Realizar un envío controlado

Primero configurar un único destinatario de prueba y cambiar a:

```yaml
enabled: true
```

Luego reconstruir la imagen y probar un solo site. Con `delivery_method: smtp` y la contraseña en
`.env`, no se necesita `compose.email.yaml`:

```bash
docker compose build
docker compose run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre \
  --send
```

Si se usa `delivery_method: gmail_api`, ejecutar el mismo comando con el override que monta el JSON:

```bash
docker compose -f compose.yaml -f compose.email.yaml run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre \
  --send
```

El comando responde con `status: sent`. Con Gmail API incluye el identificador real del mensaje; con
SMTP registra `smtp-accepted` cuando el servidor SMTP acepta el mensaje. Un segundo intento con la
misma fecha, tipo y site responde `already sent`.

## Activar el envío programado

Una vez aprobada la prueba con SMTP:

```bash
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=100 -f climate-reporting
```

Los cambios en `email.yaml` y `.env` se aplican al recrear o reiniciar el contenedor:

```bash
docker compose up -d --force-recreate
```

## Deshabilitar envíos

Cambiar `enabled: false` y recrear el servicio:

```bash
docker compose up -d --force-recreate
```

Esto no afecta la generación diaria, semanal o mensual de datos y PDF.
