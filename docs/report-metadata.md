# Metadata Mongo de boletines

El pipeline registra metadata en MongoDB por cada boletín PDF generado. Este registro permite que
otros servicios encuentren los boletines disponibles por campo, período y tipo.

## Configuración

La configuración operativa vive fuera del repositorio:

```text
/home/uoh/cerezas_web_server/config/climate-reporting/pipeline.yaml
```

Bloque esperado:

```yaml
report_metadata:
  enabled: true
  database: FIC_CEREZAS_HORAS_FRIO
  zone: ""
  timezone: America/Santiago
```

- `enabled`: activa o desactiva la escritura de metadata después de generar PDF.
- `database`: base Mongo destino.
- `zone`: cuartel. Por ahora puede quedar vacío.
- `timezone`: zona usada para convertir fechas calendario a Unix timestamp.

El repositorio contiene una plantilla en `config/pipeline.yaml`, pero el contenedor usa el archivo
externo montado en `/app/config/pipeline.yaml`.

## Documento insertado

Cada colección tiene el mismo nombre que el `site_id` del beneficiario. Por ejemplo:

```text
FIC_CEREZAS_HORAS_FRIO.fic2-graneros-agrofurore
```

Ejemplo de documento:

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

Campos:

- `data-field`: código del campo, igual al `site_id`.
- `zone`: cuartel; actualmente vacío.
- `in-date`: inicio del período del boletín como Unix timestamp.
- `out-date`: fin del período del boletín como Unix timestamp.
- `name`: correlativo por colección, calculado como `max(name) + 1`.
- `kind`: tipo de boletín: `daily`, `weekly` o `monthly`.

## Períodos usados

- `daily`: `in-date` y `out-date` son la fecha reportada.
- `weekly`: `in-date` es seis días antes de la fecha reportada; `out-date` es la fecha reportada.
- `monthly`: `in-date` es el primer día del mes reportado; `out-date` es el último día reportado.

## Idempotencia

Antes de insertar, el pipeline busca si ya existe un documento con:

```text
data-field + zone + in-date + out-date + kind
```

Si existe, no inserta un duplicado. Esto permite regenerar PDFs o correr backfills sin multiplicar
metadata para el mismo boletín.

## Backfill de PDFs existentes

Para previsualizar la metadata que se insertaría para todos los PDFs disponibles de 2026:

```bash
cd /home/uoh/cerezas_web_server/services/climate-reporting
docker compose run --rm climate-reporting metadata-backfill --year 2026 --dry-run
```

Para insertar realmente:

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026
```

Filtrar por tipo:

```bash
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind daily
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind weekly
docker compose run --rm climate-reporting metadata-backfill --year 2026 --kind monthly
```

## Verificar contenido en Mongo

Listar colecciones:

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
print(db.list_collection_names())
client.close()
'
```

Contar documentos por colección y tipo:

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

Ver últimos documentos de un campo:

```bash
docker compose run --rm --entrypoint python climate-reporting -c '
from pymongo import MongoClient, DESCENDING
import os
from urllib.parse import quote_plus

site = "fic1-rengo-agritorre"

uri = os.getenv("MONGO_URI")
if not uri:
    user = quote_plus(os.getenv("MONGO_USER"))
    password = quote_plus(os.getenv("MONGO_PASSWORD"))
    uri = f"mongodb://{user}:{password}@127.0.0.1:27017/?authSource=admin"

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
col = client["FIC_CEREZAS_HORAS_FRIO"][site]

for doc in col.find({}, {"_id": 0}).sort("_id", DESCENDING).limit(10):
    print(doc)

client.close()
'
```

## Notas operativas

- Mongo crea automáticamente una colección si no existe.
- La metadata solo se escribe automáticamente cuando el PDF se genera correctamente.
- El resultado de metadata queda registrado dentro del stage `pdf` del `manifest.json`.
- Para cambiar el cuartel en el futuro, actualizar `report_metadata.zone` o extender la
  configuración por `site_id`.
