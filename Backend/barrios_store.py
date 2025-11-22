from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "joc_de_barris"
COL_BARRIOS = "barrios"

VARIABLES = [
    "comunidad",
    "lujo_seguridad",
    "tranquilidad_acustica",
    "accesibilidad",
    "vida_nocturna_cultural",
    "transporte_24_7",
]

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col_barrios = db[COL_BARRIOS]

# Hashmap de barrios: clave = _id, valor = documento completo
barrios_map = {
    doc["_id"]: doc
    for doc in col_barrios.find({})
}

if __name__ == "__main__":
    print("Barrios cargados en el hashmap:")
    for _id, barrio in barrios_map.items():
        print(f"- {_id} -> {barrio['nombre']}")

    if "downtown_la" in barrios_map:
        b = barrios_map["downtown_la"]
        print("\nEjemplo downtown_la coords:")
        print(b["coords"])
