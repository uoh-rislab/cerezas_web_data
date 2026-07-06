# Cerezas Web Data

Pipeline automatizado para extraer datos desde MongoDB, completar datos meteorológicos,
generar CSV de reportería y producir boletines PDF para los beneficiarios del proyecto.

La implementación original en `reporteria` se mantiene intacta y sirve como referencia para
validar resultados. Este repositorio contiene la nueva implementación desplegable en Docker.

## Programación

El servicio permanece activo todo el año, pero solamente despacha ejecuciones entre el **2 de mayo**
y el **1 de noviembre**, ambas fechas inclusive. La ejecución comienza a las **00:30 hora de Chile**
usando `America/Santiago`, por lo que se adapta automáticamente al horario de verano e invierno.
Si el cambio de hora elimina las 00:30 de un día, se ejecuta en el primer minuto local válido.

| Día | Ejecución |
|---|---|
| Lunes | weekly |
| Martes a domingo | daily |
| Día 1 de cada mes | monthly adicional a daily o weekly |

- Fuera del 2 de mayo al 1 de noviembre no se generan ejecuciones automáticas.
- Daily y weekly procesan desde el 1 de mayo hasta el día anterior.
- Monthly presenta el mes calendario inmediatamente anterior y conserva el acumulado de temporada
  desde el 1 de mayo para calcular las métricas y tablas del boletín original. Tanto FIC1 como FIC2
  comparan sus acumulaciones diarias y semanales con el mismo período del año anterior.
- Si el contenedor no estaba disponible a la hora programada, recupera las ejecuciones
  pendientes dentro de la ventana configurada.

La última ejecución automática ocurre el 1 de noviembre: procesa datos hasta el 31 de octubre y
genera el monthly de octubre, además del daily o weekly correspondiente a ese día. Los comandos
manuales continúan disponibles fuera de temporada.

## Flujo

Cada ejecución realiza estas etapas en orden:

1. Extracción MongoDB para FIC1 y FIC2.
2. Extracción de locations desde los propios documentos.
3. Descarga meteorológica horaria desde Meteostat.
4. Relleno de horas faltantes para sensores de temperatura y humedad.
5. Conversión a CSV con calendario UTC-4 fijo.
6. Cálculo de HF, PF, UF y HC.
7. Generación de un PDF por beneficiario.

Los resultados persisten en:

```text
/home/uoh/cerezas_web_server/data/climate-reporting/runs/<daily|weekly|monthly>/<report-date>/
  01_raw/
  02_locations/
  03_weather/
  04_fixed/
  05_csv/
  06_reports/
  07_pdf/{fic1,fic2}/
  manifest.json
```

## Configuración

- `config/pipeline.yaml`: MongoDB, horario, modelos y filtros de sensores.
- `config/sites.yaml`: beneficiarios, grupo FIC, ciudad y nombres de salida.
- `config/stations.yaml`: coordenadas usadas para Meteostat.
- `config/email.yaml`: horario, remitente, destinatarios y copias de los boletines.
- Los logos originales se versionan en `assets/` y se incorporan automáticamente a la imagen.

Locations y filtros están desacoplados del procesamiento. Los filtros aceptan IDs exactos o
expresiones regulares en `sensor_filters`, por lo que no se requiere cambiar código para excluir
sensores ruidosos.

## Desarrollo local

Requiere Python 3.9 o superior:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Ver la planificación sin conectarse a MongoDB:

```bash
cerezas-pipeline plan --scheduled-date 2026-07-01
```

Ejecutar manualmente:

```bash
cerezas-pipeline run --kind daily --scheduled-date 2026-06-30
cerezas-pipeline dispatch --scheduled-date 2026-07-01
```

Regenerar solamente los PDF de una ejecución ya procesada:

```bash
cerezas-pipeline pdf --kind daily --scheduled-date 2026-06-30
```

`scheduled-date` es la fecha en que habría corrido el scheduler; el reporte corresponde al día
anterior.

## Docker

La estructura recomendada en el servidor separa código, datos persistentes y configuración:

```text
/home/uoh/cerezas_web_server/
├── services/
│   └── climate-reporting/
├── data/
│   └── climate-reporting/
└── config/
    └── climate-reporting/
```

Desde `/home/uoh/cerezas_web_server/services/climate-reporting`, preparar los directorios,
la configuración y los secretos:

```bash
mkdir -p /home/uoh/cerezas_web_server/data/climate-reporting
mkdir -p /home/uoh/cerezas_web_server/config/climate-reporting
cp -a config/. /home/uoh/cerezas_web_server/config/climate-reporting/
cp .env.example .env
# editar .env
docker compose build
docker compose up -d
docker compose logs -f climate-reporting
```

Se debe configurar `MAPBOX_ACCESS_TOKEN` en `.env`; el mapa satelital original depende de ese
token. Actualizar `.env.example` no modifica un `.env` real creado anteriormente.

Las rutas del host se configuran en `.env`:

```env
CEREZAS_DATA_HOST_PATH=/home/uoh/cerezas_web_server/data/climate-reporting
CEREZAS_CONFIG_HOST_PATH=/home/uoh/cerezas_web_server/config/climate-reporting
```

El contenedor usa `/data`, pero ese directorio está enlazado con
`/home/uoh/cerezas_web_server/data/climate-reporting` en el host. Los datos sobreviven al
reemplazo o reconstrucción del contenedor y a las actualizaciones del repositorio.

El Compose usa `network_mode: host` porque MongoDB escucha solamente en `127.0.0.1` del servidor.
Esta opción está pensada para Docker sobre Linux.

Para que el contenedor vuelva después de reiniciar el servidor, Docker debe estar habilitado:

```bash
sudo systemctl enable --now docker
```

La política `restart: unless-stopped` se encarga de reiniciar el contenedor si el proceso termina.

Para abrir una shell dentro del contenedor:

```bash
docker compose exec climate-reporting sh
```

La imagen incluye `sh`; Bash no es necesario para operar o diagnosticar el servicio.

## Validación en el servidor

El procedimiento completo de instalación, pruebas, activación y troubleshooting está disponible
en [docs/server-deployment.md](docs/server-deployment.md).

La integración opcional con Gmail, deshabilitada por defecto, se documenta en
[docs/email-delivery.md](docs/email-delivery.md). Está preparada para enviar cada PDF a sus
destinatarios a las 04:00 hora de Chile, respetando automáticamente horario de verano e invierno.

Antes de activar el scheduler en producción:

```bash
docker compose run --rm climate-reporting plan --scheduled-date 2026-07-01
docker compose run --rm climate-reporting run --kind daily --scheduled-date 2026-06-30
```

Se deben comparar conteos, CSV y PDFs con las ejecuciones históricas `2026-06-29` (daily) y
`2026-06-28` (weekly). Solo después de esa comparación se inicia el servicio permanente.

## Seguridad

Las credenciales se obtienen desde `MONGO_URI` o desde `MONGO_USER` y `MONGO_PASSWORD`. El archivo
`.env` está ignorado por Git. Como la credencial anterior estuvo versionada, debe rotarse antes del
despliegue; eliminarla del archivo actual no la elimina del historial Git.
