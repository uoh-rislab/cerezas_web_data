#!/usr/bin/env python3
"""
Conectar a MongoDB y generar un listado único de sensores por colección fic2,
guardando un archivo locations_{collection}.txt por colección, usando un mapeo model→sensor.
"""

from urllib.parse import quote_plus
from pymongo import MongoClient
import os
from datetime import datetime, timedelta, timezone

def fetch_and_save_fic2_sensor_locations():
    user       = "uoh_cerezas"
    password   = "UOHcerezas$"
    host       = "127.0.0.1"
    port       = 27017
    auth_db    = "admin"
    db_name    = "FIC_CEREZAS"

    uri = f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/?authSource={auth_db}"
    client = MongoClient(uri)
    db = client[db_name]

    # === Mapeo modelo → sensor ===
    model_to_sensor = {
        "LSN50v2-S31 - Temperature & Humidity Sensor": "Sensor T°-H",
        "LSE01 - Soil Moisture & EC Sensor": "Sensor Soil",
        "LSPH01 - Soil pH Sensor": "Sensor pH",
        "LLMS01 - Leaf Moisture Sensor": "Sensor Leaf"
    }

    '''
    # === Rango de fechas ISO 8601 (UTC) ===
    start_ts = "2025-05-01T04:00:00Z"
    end_ts   = "2025-07-01T03:59:59Z"
    '''

    # === Rango de fechas ISO 8601 (UTC) ===
    current_year = datetime.utcnow().year
    start_ts = f"{current_year}-03-01T04:00:00Z" #2025-05-01

    today = datetime.now(timezone.utc).date()
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).replace(hour=3, minute=59, second=59)
    end_ts = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ") #considera hasta las 23:59 del dia anterior, usando UTC0

    for coll_name in db.list_collection_names():
        if not coll_name.startswith("fic2"):
            continue

        collection = db[coll_name]
        query = {
            "time_sensor_tx": {
                "$gte": start_ts,
                "$lte": end_ts
            }
        }

        unique_sensors = {}
        cursor = collection.find(query)
        for doc in cursor:
            sensor_device_id = doc.get("sensor_device_id", "N/A")
            static_data = doc.get("sensor_static_data", {})
            lat = static_data.get("sensor_lat", "N/A")
            lon = static_data.get("sensor_lon", "N/A")
            model = static_data.get("sensor_model", "N/A")
            sensor = model_to_sensor.get(model, "N/A")  # usa mapeo, N/A si no está definido

            if sensor_device_id not in unique_sensors:
                unique_sensors[sensor_device_id] = {
                    "app_id": coll_name,
                    "field_id": doc.get("field_id", "N/A"),
                    "end_device_id": sensor_device_id,
                    "latitud": lat,
                    "longitud": lon,
                    "model": model,
                    "sensor": sensor
                }


        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        os.makedirs(f"output/data_{yesterday_str}/locations", exist_ok=True)
        output_path = os.path.join(f"output/data_{yesterday_str}/locations", f"locations_{coll_name}.txt") #nombre del archivo con la fecha del ultimo dia


        with open(output_path, "w", encoding="utf-8") as f:
            # Escribir encabezado
            f.write("app_id\tfield_id\tend_device_id\tlatitud\tlongitud\tmodel\tsensor\n")
            # Escribir cada sensor único
            for sensor_info in unique_sensors.values():
                f.write(
                    f"{sensor_info['app_id']}\t{sensor_info['field_id']}\t{sensor_info['end_device_id']}\t"
                    f"{sensor_info['latitud']}\t{sensor_info['longitud']}\t{sensor_info['model']}\t{sensor_info['sensor']}\n"
                )

        print(f"{coll_name}: {len(unique_sensors)} sensores únicos guardados en {output_path}")

    client.close()

if __name__ == "__main__":
    fetch_and_save_fic2_sensor_locations()

