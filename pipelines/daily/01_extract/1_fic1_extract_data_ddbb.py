#!/usr/bin/env python3
"""
Conectar a MongoDB y guardar documentos de las colecciones uoh-cerezos-ambiente, uoh-cerezos-leaf, uoh-cerezos-soil
filtrados por field_id y por rango de fechas, en archivos separados por field_id.
"""

from urllib.parse import quote_plus
from pymongo import MongoClient
import os
import json
from datetime import datetime, timedelta, timezone


def fetch_and_save_by_field_id_and_date():
    user       = "uoh_cerezas"
    password   = "UOHcerezas$"
    host       = "127.0.0.1"
    port       = 27017
    auth_db    = "admin"
    db_name    = "FIC_CEREZAS"

    uri = f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/?authSource={auth_db}"
    client     = MongoClient(uri)
    db         = client[db_name]

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

    # === Rango de fechas ISO 8601 (UTC) ===
    current_year = datetime.utcnow().year
    start_ts = f"{current_year}-05-01T04:00:00Z" #2025-05-01

    today = datetime.now(timezone.utc).date()
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).replace(hour=3, minute=59, second=59)
    end_ts = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ") #considera hasta las 23:59 del dia anterior, usando UTC0

    for field_id in field_ids:
        all_docs = []

        for coll_name in collections:
            collection = db[coll_name]
            query = {
                "field_id": field_id,
                "time_sensor_tx": {
                    "$gte": start_ts,
                    "$lte": end_ts
                }
            }
            cursor = collection.find(query)
            docs = list(cursor)
            all_docs.extend(docs)

            print(f"{coll_name}: {len(docs)} documentos encontrados para field_id {field_id}")

        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        os.makedirs(f"output/data_{yesterday_str}/results", exist_ok=True)
        output_path = os.path.join(f"output/data_{yesterday_str}/results", f"daily_{yesterday_str}_{field_id}.txt") #nombre del archivo con la fecha del ultimo dia

        with open(output_path, "w", encoding="utf-8") as f:
            for doc in all_docs:
                f.write(json.dumps(doc, default=str) + "\n")

        print(f"Total {len(all_docs)} documentos guardados en {output_path}")

    client.close()

if __name__ == "__main__":
    fetch_and_save_by_field_id_and_date()