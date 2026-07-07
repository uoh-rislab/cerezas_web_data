# Instalación y pruebas en el servidor

Esta guía instala `climate-reporting` sin mezclar el código del servicio con sus datos persistentes
o su configuración. Todos los nombres de rutas, servicios y archivos se mantienen en inglés.

## 1. Conectarse al servidor

Desde el computador local:

```bash
ssh -J ibugueno@172.16.105.104 uoh@172.16.0.76
```

## 2. Verificar los servicios base

```bash
docker --version
docker compose version
sudo systemctl enable --now docker
ss -lnt | grep 27017
```

MongoDB debe escuchar en `127.0.0.1:27017`. El contenedor usa `network_mode: host` para acceder a
esa dirección del servidor.

## 3. Crear la estructura persistente

```bash
mkdir -p /home/uoh/cerezas_web_server/services
mkdir -p /home/uoh/cerezas_web_server/data/climate-reporting
mkdir -p /home/uoh/cerezas_web_server/config/climate-reporting
```

La estructura resultante es:

```text
/home/uoh/cerezas_web_server/
├── services/climate-reporting/
├── data/climate-reporting/
└── config/climate-reporting/
```

## 4. Clonar el repositorio

```bash
cd /home/uoh/cerezas_web_server/services
git clone https://github.com/uoh-rislab/cerezas_web_data.git climate-reporting
cd climate-reporting
git checkout main
git pull --ff-only
git status
git log -1 --oneline
```

Si el repositorio ya existe:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
git pull --ff-only
```

## 5. Instalar la configuración externa

En la primera instalación:

```bash
cp -a config/. /home/uoh/cerezas_web_server/config/climate-reporting/
```

Los logos originales están versionados en `assets/fic-report-assets.zip.b64`. El build los valida,
descomprime y copia dentro de `/app/assets`; no es necesario transferirlos manualmente.

En actualizaciones posteriores, comparar antes de reemplazar configuración local:

```bash
diff -ru config /home/uoh/cerezas_web_server/config/climate-reporting
```

Los archivos activos son:

```text
/home/uoh/cerezas_web_server/config/climate-reporting/
├── email.yaml
├── pipeline.yaml
├── sites.yaml
└── stations.yaml
```

## 6. Configurar rutas y secretos

```bash
cp .env.example .env
nano .env
```

Contenido esperado:

```env
CEREZAS_DATA_HOST_PATH=/home/uoh/cerezas_web_server/data/climate-reporting
CEREZAS_CONFIG_HOST_PATH=/home/uoh/cerezas_web_server/config/climate-reporting

MONGO_USER=uoh_cerezas
MONGO_PASSWORD='REPLACE_WITH_ROTATED_PASSWORD'
MAPBOX_ACCESS_TOKEN='REPLACE_WITH_ORIGINAL_MAPBOX_PUBLIC_TOKEN'
```

Las comillas simples protegen caracteres como `$` y `#`. La credencial que estuvo versionada debe
rotarse antes del despliegue. El token Mapbox debe corresponder al utilizado por el generador
original; es necesario para reproducir el mapa satelital. Si `.env` fue creado antes de que esta
variable apareciera en `.env.example`, se debe agregar manualmente: Git nunca sobrescribe `.env`.

Proteger archivos y directorios:

```bash
chmod 600 .env
chmod 700 /home/uoh/cerezas_web_server/data/climate-reporting
chmod 700 /home/uoh/cerezas_web_server/config/climate-reporting
```

## 7. Construir la imagen sin activar el scheduler

```bash
docker compose config --services
docker compose build
```

El primer comando debe mostrar:

```text
climate-reporting
```

El mensaje sobre `COMPOSE_BAKE=true` es informativo y no representa un error.

## 8. Probar la planificación

```bash
docker compose run --rm climate-reporting plan --scheduled-date 2026-07-01
```

Debe planificar `daily` y `monthly`. Esta prueba no consulta MongoDB ni Meteostat.

Probar los límites de temporada:

```bash
docker compose run --rm climate-reporting plan --scheduled-date 2026-05-01
docker compose run --rm climate-reporting plan --scheduled-date 2026-05-02
docker compose run --rm climate-reporting plan --scheduled-date 2026-09-02
docker compose run --rm climate-reporting plan --scheduled-date 2026-09-03
```

Resultados esperados:

- `2026-05-01`: ninguna ejecución.
- `2026-05-02`: `daily`.
- `2026-09-02`: `daily`.
- `2026-09-03`: ninguna ejecución.

## 9. Ejecutar una prueba daily

```bash
docker compose run --rm climate-reporting run \
  --kind daily \
  --scheduled-date 2026-06-30
```

Esto genera el reporte `2026-06-29` y ejecuta MongoDB, Meteostat, reparación, CSV, procesamiento
climático y PDF.

## 10. Revisar la ejecución daily

```bash
cd /home/uoh/cerezas_web_server/data/climate-reporting
find runs/daily/2026-06-29 -maxdepth 3 -type f | sort
python3 -m json.tool runs/daily/2026-06-29/manifest.json
```

El manifiesto debe contener:

```json
"status": "complete"
```

Revisar conteos y PDF:

```bash
wc -l runs/daily/2026-06-29/01_raw/*.jsonl
wc -l runs/daily/2026-06-29/05_csv/*.csv
wc -l runs/daily/2026-06-29/06_reports/*.csv
find runs/daily/2026-06-29/07_pdf -type f -name '*.pdf' -size +0
```

## 11. Probar weekly

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
docker compose run --rm climate-reporting run \
  --kind weekly \
  --scheduled-date 2026-06-29
```

El resultado queda en:

```text
/home/uoh/cerezas_web_server/data/climate-reporting/runs/weekly/2026-06-28/
```

## 12. Probar monthly

Los boletines monthly de FIC1 y FIC2 comparan con el mismo período del año anterior. Deben existir
previamente los CSV procesados del año anterior bajo
`runs/monthly/<previous-report-date>/06_reports/` para cada site.

Para preparar Junio 2025 como base comparativa sin exigir a su vez los PDF de 2024:

```bash
docker compose run --rm climate-reporting run \
  --kind monthly \
  --scheduled-date 2025-07-01 \
  --skip-pdf
```

Este comando ejecuta extracción, Meteostat, reparación, CSV y procesamiento climático, pero omite
solamente los PDF. Debe ejecutarse una vez por cada mes histórico que se utilizará como comparación.

```bash
docker compose run --rm climate-reporting run \
  --kind monthly \
  --scheduled-date 2026-07-01
```

El resultado queda en:

```text
/home/uoh/cerezas_web_server/data/climate-reporting/runs/monthly/2026-06-30/
```

## 13. Comparar con el flujo original

Después de cambios exclusivamente visuales, regenerar los PDF sin repetir MongoDB, Meteostat o los
cálculos climáticos:

```bash
docker compose run --rm climate-reporting pdf \
  --kind daily \
  --scheduled-date 2026-06-30
```

Comparar las ejecuciones históricas:

- Daily: `2026-06-29`.
- Weekly: `2026-06-28`.

Revisar:

- Cantidad de documentos raw.
- Sensores incluidos.
- Cantidad de filas de los CSV.
- Valores HF, PF, UF y HC.
- Cantidad, contenido y diseño visual de los PDF.

## 14. Activar el scheduler

Solo después de aprobar las comparaciones:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
docker compose up -d
docker compose ps
docker compose logs --tail=100 -f climate-reporting
```

Si la fecha actual está dentro de temporada y ya pasó la hora programada, la primera activación
puede ejecutar inmediatamente el trabajo pendiente del día.

### Primera ejecución y recuperación

Al iniciar por primera vez, es normal observar temporalmente:

```text
running starting
```

El healthcheck tiene un período inicial y debería cambiar a `running healthy` después de
aproximadamente un minuto. Si el scheduler detecta que la fecha está dentro de temporada, que ya
pasaron las 00:30 en `America/Santiago` y que no existe una ejecución registrada para el día, comienza una
recuperación inmediatamente:

```text
Scheduler activo: 00:30 America/Santiago
Iniciando daily para fecha programada YYYY-MM-DD
```

Una ejecución manual realizada previamente con `docker compose run` no registra el trabajo en la
base del scheduler. Por eso la primera activación puede repetir esa fecha una vez. La ejecución es
idempotente y reemplaza los artefactos de la misma fecha.

Seguir el progreso sin detener el servicio:

```bash
docker compose logs -f climate-reporting
```

Salir de la vista de logs con `Ctrl+C` no detiene el contenedor. Al finalizar debe aparecer:

```text
Completado daily para YYYY-MM-DD
```

Para una ejecución concreta, revisar también su manifiesto persistente. Por ejemplo:

```bash
python3 -m json.tool \
  /home/uoh/cerezas_web_server/data/climate-reporting/runs/daily/2026-06-29/manifest.json
```

Durante el procesamiento puede mostrar `"status": "running"`; al terminar debe mostrar
`"status": "complete"`.

La agenda normal es:

- Lunes: weekly.
- Martes a domingo: daily.
- Día 1: monthly adicional a daily o weekly.
- Ventana anual: 2 de mayo al 2 de septiembre, ambas fechas inclusive.

## 15. Verificar salud y acceder al contenedor

```bash
docker compose ps
docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' climate-reporting
docker compose exec climate-reporting sh
```

Dentro del contenedor:

```sh
ls -la /data
ls -la /data/runs
exit
```

## 16. Probar el reinicio automático

```bash
docker kill climate-reporting
sleep 10
docker compose ps
docker compose logs --tail=100 climate-reporting
```

El contenedor debe volver a estado `running` por la política `restart: unless-stopped`.

## 17. Actualizar el servicio

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
git pull --ff-only
diff -ru config /home/uoh/cerezas_web_server/config/climate-reporting
docker compose build
docker compose up -d
```

Los datos permanecen fuera del repositorio en:

```text
/home/uoh/cerezas_web_server/data/climate-reporting
```

## 18. Preparar envíos Gmail

La integración está incluida pero deshabilitada por defecto, por lo que no modifica el servicio
actual. La configuración de destinatarios, la cuenta de servicio, la prueba controlada y la
activación de los envíos a las 05:00 hora de Chile se detallan en
[email-delivery.md](email-delivery.md).

## 19. Horario del scheduler

El scheduler se ejecuta a las `00:30` usando la zona IANA `America/Santiago`. Esto mantiene las
00:30 como hora civil de Chile y aplica automáticamente UTC-3 o UTC-4 según corresponda. Si el
cambio al horario de verano elimina las 00:30 de un día, la ejecución ocurre en el primer minuto
local válido posterior al salto, sin omitir el procesamiento de esa fecha.

La configuración activa vive fuera del repositorio. Después de actualizar el código, editar:

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/pipeline.yaml
```

Las primeras líneas deben ser:

```yaml
schedule_timezone: America/Santiago
schedule_hour: 0
schedule_minute: 30
```

Luego reconstruir y recrear el servicio:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
docker compose build
docker compose up -d
docker compose logs --tail=100 climate-reporting
```

El log esperado es:

```text
Scheduler activo: 00:30 America/Santiago
```

Este cambio afecta solamente la hora de inicio. Las ventanas y calendarios de los datos continúan
usando UTC-4 fijo para conservar compatibilidad con el procesamiento histórico.

## 20. Metadata Mongo de boletines

Después de generar cada PDF, el pipeline registra metadata en MongoDB si `report_metadata.enabled`
está activo en la configuración externa.

```bash
nano /home/uoh/cerezas_web_server/config/climate-reporting/pipeline.yaml
```

Bloque esperado:

```yaml
report_metadata:
  enabled: true
  database: FIC_CEREZAS_HORAS_FRIO
  zone: ""
  timezone: America/Santiago
```

Cada documento se inserta en la colección cuyo nombre coincide con el `site_id`, por ejemplo
`fic2-graneros-agrofurore`, e incluye:

```json
{
  "data-field": "fic2-graneros-agrofurore",
  "zone": "",
  "in-date": "1765422000",
  "out-date": "1765422000",
  "name": "1",
  "kind": "daily"
}
```

El campo `kind` distingue `daily`, `weekly` y `monthly`. El campo `name` se calcula buscando el
máximo existente en la colección y usando `max + 1`. Si ya existe metadata para el mismo
`data-field`, `zone`, período y `kind`, no se inserta un duplicado.

Para registrar metadata de todos los PDFs ya disponibles de 2026:

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026 --dry-run
docker compose run --rm climate-reporting metadata-backfill --year 2026
```

También se puede filtrar por tipo:

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind daily
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind weekly
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind monthly
```

El detalle del formato insertado, idempotencia y comandos de verificación está en
[report-metadata.md](report-metadata.md).

## 21. Checklist de producción

Antes de dejar el servicio en producción, ejecutar la validación paso a paso descrita en
[production-validation.md](production-validation.md). Esa guía verifica:

- configuración externa montada en el contenedor;
- scheduler y ventana de temporada;
- MongoDB;
- generación de PDFs;
- metadata;
- preview y envío controlado de correos;
- limpieza de registros de test.

## Troubleshooting

### Error `exec: "plan": executable file not found`

La imagen anterior no definía `cerezas-pipeline` como `ENTRYPOINT`. Actualizar y reconstruir:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
git pull --ff-only
docker compose build --no-cache
```

Con la imagen anterior, el comando equivalente es:

```bash
docker compose run --rm climate-reporting cerezas-pipeline plan --scheduled-date 2026-07-01
```

### Ver los logs

```bash
docker compose logs --tail=200 climate-reporting
```

### Abrir una shell sin iniciar el scheduler

```bash
docker compose run --rm --entrypoint sh climate-reporting
```

### Confirmar los mounts

```bash
docker compose run --rm --entrypoint sh climate-reporting -c 'mount | grep /data; ls -la /data'
```
