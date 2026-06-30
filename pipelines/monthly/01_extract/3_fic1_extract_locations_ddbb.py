#!/usr/bin/env python3
"""
Conectar a MongoDB y generar un listado único de sensores por field_id
en archivos separados llamados locations_{field_id}.txt, usando un mapeo model→sensor.
"""

from urllib.parse import quote_plus
from pymongo import MongoClient
import os
from datetime import datetime, timedelta, timezone

def fetch_and_save_sensor_locations():
    user       = os.environ.get("MONGO_USER", "uoh_cerezas")
    password   = os.environ["MONGO_PASSWORD"]
    host       = os.environ.get("MONGO_HOST", "127.0.0.1")
    port       = int(os.environ.get("MONGO_PORT", "27017"))
    auth_db    = os.environ.get("MONGO_AUTH_DATABASE", "admin")
    db_name    = os.environ.get("MONGO_DATABASE", "FIC_CEREZAS")

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

    # === Field IDs de interés ===
    field_ids = [
        "fic1-rengo-agritorre",
        "fic1-rengo-ceaf",
        "fic1-requinoa-requiagro",
        "fic1-graneros-agrofurore"
    ]

    # === Colecciones de interés ===
    collections = [
        "uoh-cerezos-ambiente",
        "uoh-cerezos-leaf",
        "uoh-cerezos-soil"
    ]

    os.makedirs("results", exist_ok=True)

    for field_id in field_ids:
        unique_sensors = {}
        
        for coll_name in collections:
            collection = db[coll_name]
            query = {"field_id": field_id}
            cursor = collection.find(query)
            for doc in cursor:
                # Extraer campos según estructura real
                sensor_device_id = doc.get("sensor_device_id", "N/A")
                static_data = doc.get("sensor_static_data", {})
                lat = static_data.get("sensor_lat", "N/A")
                lon = static_data.get("sensor_lon", "N/A")
                model = static_data.get("sensor_model", "N/A")
                sensor = model_to_sensor.get(model, "N/A")  # usa mapeo

                # Usa sensor_device_id como clave única
                if sensor_device_id not in unique_sensors:
                    unique_sensors[sensor_device_id] = {
                        "app_id": coll_name,
                        "field_id": field_id,
                        "end_device_id": sensor_device_id,
                        "latitud": lat,
                        "longitud": lon,
                        "model": model,
                        "sensor": sensor
                    }

        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        os.makedirs(f"output/data_{yesterday_str}/locations", exist_ok=True)
        output_path = os.path.join(f"output/data_{yesterday_str}/locations", f"locations_{field_id}.txt") #nombre del archivo con la fecha del ultimo dia

        with open(output_path, "w", encoding="utf-8") as f:
            # Escribir encabezado
            f.write("app_id\tfield_id\tend_device_id\tlatitud\tlongitud\tmodel\tsensor\n")
            # Escribir cada sensor único
            for sensor_info in unique_sensors.values():
                f.write(
                    f"{sensor_info['app_id']}\t{sensor_info['field_id']}\t{sensor_info['end_device_id']}\t"
                    f"{sensor_info['latitud']}\t{sensor_info['longitud']}\t{sensor_info['model']}\t{sensor_info['sensor']}\n"
                )

        print(f"{len(unique_sensors)} sensores únicos guardados en {output_path}")

    client.close()

if __name__ == "__main__":
    fetch_and_save_sensor_locations()
