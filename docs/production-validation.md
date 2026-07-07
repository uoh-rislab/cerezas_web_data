# Checklist de validación en producción

Esta guía sirve para validar que el contenedor quedó listo para generar reportes, registrar metadata
y enviar correos antes de dejarlo operando en producción.

Todos los comandos se ejecutan en el servidor:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
```

## 1. Actualizar, construir y levantar

```bash
git pull --ff-only
docker compose build
docker compose up -d --force-recreate
```

Verificar estado:

```bash
docker compose ps
docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' climate-reporting
docker compose logs --tail=100 climate-reporting
```

Esperado:

```text
running
Scheduler activo: 00:30 America/Santiago
Envío Gmail activo: 05:00 America/Santiago
```

## 2. Confirmar que se usa configuración externa

El archivo operativo de configuración no es el `config/` del repo. El contenedor usa:

```text
/home/uoh/cerezas_web_server/config/climate-reporting/
```

Validar email:

```bash
echo "== email.yaml externo en host =="
cat /home/uoh/cerezas_web_server/config/climate-reporting/email.yaml

echo
echo "== email.yaml visto por el contenedor =="
docker compose run --rm --entrypoint sh climate-reporting -c \
  'cat /app/config/email.yaml'
```

Validar pipeline:

```bash
echo "== pipeline.yaml externo en host =="
cat /home/uoh/cerezas_web_server/config/climate-reporting/pipeline.yaml

echo
echo "== pipeline.yaml visto por el contenedor =="
docker compose run --rm --entrypoint sh climate-reporting -c \
  'cat /app/config/pipeline.yaml'
```

## 3. Validar configuración clave

```bash
docker compose run --rm --entrypoint sh climate-reporting -c '
echo "== scheduler =="
grep -E "^(schedule_timezone|schedule_hour|schedule_minute|schedule_start_month|schedule_start_day|schedule_end_month|schedule_end_day):" /app/config/pipeline.yaml

echo
echo "== metadata =="
grep -A5 "^report_metadata:" /app/config/pipeline.yaml

echo
echo "== email =="
grep -E "^(enabled|delivery_method|timezone|send_hour|send_minute|retry_minutes):" /app/config/email.yaml
'
```

Esperado:

```yaml
schedule_timezone: America/Santiago
schedule_hour: 0
schedule_minute: 30
schedule_end_month: 9
schedule_end_day: 2
```

```yaml
report_metadata:
  enabled: true
  database: FIC_CEREZAS_HORAS_FRIO
```

```yaml
enabled: true
delivery_method: smtp
send_hour: 5
send_minute: 0
```

## 4. Validar planificación

```bash
docker compose run --rm climate-reporting plan --scheduled-date 2026-07-01
docker compose run --rm climate-reporting plan --scheduled-date 2026-09-02
docker compose run --rm climate-reporting plan --scheduled-date 2026-09-03
```

Esperado:

- `2026-07-01`: `daily` y `monthly`.
- `2026-09-02`: `daily`.
- `2026-09-03`: `[]`.

Regla operativa:

- Lunes: `weekly`.
- Martes a domingo: `daily`.
- Día 1: `monthly` adicional.

## 5. Validar Mongo principal

```bash
docker compose run --rm --entrypoint python climate-reporting -c '
from pymongo import MongoClient
import os
from urllib.parse import quote_plus

uri = os.getenv("MONGO_URI")
if not uri:
    user = quote_plus(os.getenv("MONGO_USER"))
    password = quote_plus(os.getenv("MONGO_PASSWORD"))
    uri = f"mongodb://{user}:{password}@127.0.0.1:27017/?authSource=admin"

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
print(client.admin.command("ping"))
print(client.list_database_names())
client.close()
'
```

Esperado:

```text
{'ok': 1.0}
```

La lista debe incluir:

```text
FIC_CEREZAS
FIC_CEREZAS_HORAS_FRIO
```

## 6. Validar generación de PDF ya procesado

Para regenerar solo PDFs de una ejecución existente:

```bash
docker compose run --rm climate-reporting pdf \
  --kind daily \
  --scheduled-date 2026-06-30
```

Verificar PDFs:

```bash
find /home/uoh/cerezas_web_server/data/climate-reporting/runs/daily/2026-06-29/07_pdf \
  -type f -name "*.pdf" -size +0 | sort
```

## 7. Validar metadata con dry-run

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026 --dry-run
```

Esperado:

- `status: dry_run` para metadata que se insertaría.
- `status: exists` para metadata ya registrada.

Insertar metadata real de todos los PDFs disponibles de 2026:

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026
```

Verificar resumen por colección y tipo:

```bash
docker compose run --rm --entrypoint python climate-reporting -c '
from pymongo import MongoClient
import os
from urllib.parse import quote_plus

uri = os.getenv("MONGO_URI")
if not uri:
    user = quote_plus(os.getenv("MONGO_USER"))
    password = quote_plus(os.getenv("MONGO_PASSWORD"))
    uri = f"mongodb://{user}:{password}@127.0.0.1:27017/?authSource=admin"

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
db = client["FIC_CEREZAS_HORAS_FRIO"]

for collection_name in sorted(db.list_collection_names()):
    col = db[collection_name]
    counts = {
        kind: col.count_documents({"kind": kind})
        for kind in ["daily", "weekly", "monthly"]
    }
    total = col.count_documents({})
    print(collection_name, "total:", total, counts)

client.close()
'
```

## 8. Validar correo sin enviar

Este comando no llama a SMTP; solo arma el correo y muestra destinatarios, asunto y PDF:

```bash
docker compose run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre
```

Verificar:

- `subject` comienza con `Boletín ...`.
- `to` contiene los destinatarios esperados.
- `cc` contiene las copias globales y específicas.
- `pdf` apunta a un archivo existente.

## 9. Envío controlado de prueba

Solo si el `email.yaml` tiene un destinatario de prueba:

```bash
docker compose run --rm climate-reporting email \
  --kind daily \
  --scheduled-date 2026-06-30 \
  --site fic1-rengo-agritorre \
  --send
```

Respuestas posibles:

- `sent`: SMTP aceptó el correo.
- `already sent`: ya existe registro en `/data/state/scheduler.db` para ese `kind + date + site`.
- `skipped`: el sitio no tiene destinatarios principales.
- `waiting`: falta el PDF o el pipeline no está completo.

## 10. Limpiar registros de envíos de prueba del día actual

Revisar registros de hoy:

```bash
docker compose run --rm --entrypoint python climate-reporting -c '
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

today = datetime.now(ZoneInfo("America/Santiago")).date().isoformat()
db = "/data/state/scheduler.db"

con = sqlite3.connect(db)
rows = con.execute("""
    SELECT scheduled_date, kind, site_id, status, attempts, last_attempt, gmail_message_id, error
    FROM email_deliveries
    WHERE scheduled_date = ?
    ORDER BY kind, site_id
""", (today,)).fetchall()

print("today:", today)
for row in rows:
    print(row)

con.close()
'
```

Borrar todos los registros de envío de hoy:

```bash
docker compose run --rm --entrypoint python climate-reporting -c '
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

today = datetime.now(ZoneInfo("America/Santiago")).date().isoformat()
db = "/data/state/scheduler.db"

con = sqlite3.connect(db)
deleted = con.execute("""
    DELETE FROM email_deliveries
    WHERE scheduled_date = ?
""", (today,)).rowcount
con.commit()
con.close()

print("deleted rows:", deleted)
print("date:", today)
'
```

## 11. Activar producción

Recrear y seguir logs:

```bash
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=100 -f climate-reporting
```

Salir de logs con `Ctrl+C` no detiene el contenedor.

## 12. Señales de operación correcta

En logs debe verse:

```text
Scheduler activo: 00:30 America/Santiago
Envío Gmail activo: 05:00 America/Santiago
```

Después de una ejecución:

```text
Completado daily para YYYY-MM-DD
```

Después de correos:

```text
Email daily fic1-rengo-agritorre: sent
```

Los artefactos deben quedar en:

```text
/home/uoh/cerezas_web_server/data/climate-reporting/runs/<daily|weekly|monthly>/<report-date>/
```
