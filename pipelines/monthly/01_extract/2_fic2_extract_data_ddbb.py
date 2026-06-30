#!/usr/bin/env python3
"""
Conectar a MongoDB y guardar documentos de las colecciones que comienzan con 'fic2'
de FIC_CEREZAS entre el 29 y 30 de junio de 2025 en archivos separados por colección.
"""

from urllib.parse import quote_plus
from pymongo import MongoClient
import os
import json
from datetime import datetime, timedelta, timezone

def fetch_and_save_june29_fic2_collections():
    user       = os.environ.get("MONGO_USER", "uoh_cerezas")
    password   = os.environ["MONGO_PASSWORD"]
    host       = os.environ.get("MONGO_HOST", "127.0.0.1")
    port       = int(os.environ.get("MONGO_PORT", "27017"))
    auth_db    = os.environ.get("MONGO_AUTH_DATABASE", "admin")
    db_name    = os.environ.get("MONGO_DATABASE", "FIC_CEREZAS")

    uri = f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/?authSource={auth_db}"
    client     = MongoClient(uri)
    db         = client[db_name]

    # === Rango de fechas ISO 8601 (UTC) ===
    #start_ts = "2025-05-01T04:00:00Z"
    #end_ts   = "2025-07-14T03:59:59Z"
    
    # === Rango de fechas ISO 8601 (UTC) ===
    current_year = datetime.utcnow().year
    start_ts = f"{current_year}-05-01T04:00:00Z" #2025-05-01

    today = datetime.now(timezone.utc).date()
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).replace(hour=3, minute=59, second=59)
    end_ts = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ") #considera hasta las 23:59 del dia anterior (03:59 del dia de hoy), usando UTC0

    os.makedirs("results", exist_ok=True)

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
        cursor     = collection.find(query)
        documentos = list(cursor)

        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        os.makedirs(f"output/data_{yesterday_str}/results", exist_ok=True)
        output_path = os.path.join(f"output/data_{yesterday_str}/results", f"monthly_{yesterday_str}_{coll_name}.txt")

        with open(output_path, "w", encoding="utf-8") as f:
            for doc in documentos:
                f.write(json.dumps(doc, default=str) + "\n")

        print(f"{coll_name}: {len(documentos)} documentos guardados en {output_path}")

    client.close()

if __name__ == "__main__":
    fetch_and_save_june29_fic2_collections()
