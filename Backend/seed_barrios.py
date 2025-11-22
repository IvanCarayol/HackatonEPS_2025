from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "joc_de_barris"
COL_BARRIOS = "barrios"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COL_BARRIOS]

barrios = [
    {
        "_id": "downtown_la",
        "nombre": "Downtown Los Angeles",
        "coords": {
            "comunidad": 0.6,
            "lujo_seguridad": 0.4,
            "tranquilidad_acustica": 0.2,
            "accesibilidad": 0.7,
            "vida_nocturna_cultural": 0.9,
            "transporte_24_7": 0.8,
        },
    },
    {
        "_id": "hollywood",
        "nombre": "Hollywood",
        "coords": {
            "comunidad": 0.5,
            "lujo_seguridad": 0.5,
            "tranquilidad_acustica": 0.3,
            "accesibilidad": 0.6,
            "vida_nocturna_cultural": 1.0,
            "transporte_24_7": 0.9,
        },
    },
    {
        "_id": "santa_monica",
        "nombre": "Santa Monica",
        "coords": {
            "comunidad": 0.8,
            "lujo_seguridad": 0.7,
            "tranquilidad_acustica": 0.7,
            "accesibilidad": 0.7,
            "vida_nocturna_cultural": 0.8,
            "transporte_24_7": 0.6,
        },
    },
    {
        "_id": "echo_park",
        "nombre": "Echo Park",
        "coords": {
            "comunidad": 0.9,
            "lujo_seguridad": 0.4,
            "tranquilidad_acustica": 0.5,
            "accesibilidad": 0.6,
            "vida_nocturna_cultural": 0.7,
            "transporte_24_7": 0.7,
        },
    },
    {
        "_id": "bel_air",
        "nombre": "Bel Air",
        "coords": {
            "comunidad": 0.4,
            "lujo_seguridad": 1.0,
            "tranquilidad_acustica": 0.9,
            "accesibilidad": 0.8,
            "vida_nocturna_cultural": 0.6,
            "transporte_24_7": 0.3,
        },
    },
]

col.delete_many({})
col.insert_many(barrios)

print("Barrios insertados correctamente:")
for b in col.find({}):
    print("-", b["nombre"])
