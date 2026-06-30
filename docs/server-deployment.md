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

En actualizaciones posteriores, comparar antes de reemplazar configuración local:

```bash
diff -ru config /home/uoh/cerezas_web_server/config/climate-reporting
```

Los archivos activos son:

```text
/home/uoh/cerezas_web_server/config/climate-reporting/
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
```

Las comillas simples protegen caracteres como `$` y `#`. La credencial que estuvo versionada debe
rotarse antes del despliegue.

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
docker compose run --rm climate-reporting plan --scheduled-date 2026-11-01
docker compose run --rm climate-reporting plan --scheduled-date 2026-11-02
```

Resultados esperados:

- `2026-05-01`: ninguna ejecución.
- `2026-05-02`: `daily`.
- `2026-11-01`: `daily` y `monthly`.
- `2026-11-02`: ninguna ejecución.

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

## 15. Verificar salud y acceder al contenedor

```bash
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
