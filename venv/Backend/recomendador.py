from pymongo import MongoClient

# Conexión a Mongo
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "joc_de_barris"
COL_BARRIOS = "barrios"

# Mismas variables que usaste para definir coords
VARIABLES = [
    "comunidad",
    "lujo_seguridad",
    "tranquilidad_acustica",
    "accesibilidad",
    "vida_nocturna_cultural",
    "transporte_24_7",
]

# Perfiles de clientes (se pueden tunear)
CLIENTES = {
    "daenerys": {
        "nombre": "Daenerys Targaryen",
        "prefs": {
            "comunidad": 0.95,
            "lujo_seguridad": 0.4,
            "tranquilidad_acustica": 0.6,
            "accesibilidad": 0.5,
            "vida_nocturna_cultural": 0.7,
            "transporte_24_7": 0.5,
        },
    },
    "cersei": {
        "nombre": "Cersei Lannister",
        "prefs": {
            "comunidad": 0.2,
            "lujo_seguridad": 1.0,
            "tranquilidad_acustica": 0.9,
            "accesibilidad": 0.7,
            "vida_nocturna_cultural": 0.6,
            "transporte_24_7": 0.3,
        },
    },
    "bran": {
        "nombre": "Bran Stark",
        "prefs": {
            "comunidad": 0.5,
            "lujo_seguridad": 0.6,
            "tranquilidad_acustica": 1.0,
            "accesibilidad": 1.0,
            "vida_nocturna_cultural": 0.4,
            "transporte_24_7": 0.5,
        },
    },
    "jon": {
        "nombre": "Jon Snow",
        "prefs": {
            "comunidad": 0.9,
            "lujo_seguridad": 0.3,
            "tranquilidad_acustica": 0.7,
            "accesibilidad": 0.6,
            "vida_nocturna_cultural": 0.5,
            "transporte_24_7": 0.6,
        },
    },
    "arya": {
        "nombre": "Arya Stark",
        "prefs": {
            "comunidad": 0.4,
            "lujo_seguridad": 0.4,
            "tranquilidad_acustica": 0.3,
            "accesibilidad": 0.6,
            "vida_nocturna_cultural": 0.9,
            "transporte_24_7": 1.0,
        },
    },
    "tyrion": {
        "nombre": "Tyrion Lannister",
        "prefs": {
            "comunidad": 0.7,
            "lujo_seguridad": 0.7,
            "tranquilidad_acustica": 0.4,
            "accesibilidad": 0.7,
            "vida_nocturna_cultural": 1.0,
            "transporte_24_7": 0.8,
        },
    },
}

# Conectar y cargar barrios como "hashmap"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col_barrios = db[COL_BARRIOS]

barrios_map = {
    doc["_id"]: doc
    for doc in col_barrios.find({})
}


def score_barrio_for_cliente(barrio_coords: dict, cliente_prefs: dict) -> float:
    """
    Calcula un score simple como producto punto entre
    el vector de coords del barrio y las preferencias del cliente.
    """
    score = 0.0
    for var in VARIABLES:
        score += barrio_coords.get(var, 0) * cliente_prefs.get(var, 0)
    return score


def recomendar_barrios(cliente_id: str, top_k: int = 3):
    """
    Devuelve los top_k barrios mejor puntuados para un cliente.
    """
    cliente = CLIENTES[cliente_id]
    prefs = cliente["prefs"]

    resultados = []
    for _id, barrio in barrios_map.items():
        coords = barrio["coords"]
        s = score_barrio_for_cliente(coords, prefs)
        resultados.append({
            "barrio_id": _id,
            "nombre": barrio["nombre"],
            "score": s,
            "coords": coords,
        })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:top_k]


def explicar_recomendacion(barrio: dict, cliente_id: str, top_n: int = 3) -> str:
    """
    Genera un texto que explica por qué este barrio encaja con el cliente.
    """
    cliente = CLIENTES[cliente_id]
    prefs = cliente["prefs"]
    coords = barrio["coords"]

    detalles = []
    for var in VARIABLES:
        contrib = coords.get(var, 0) * prefs.get(var, 0)
        detalles.append((var, contrib, coords.get(var, 0), prefs.get(var, 0)))

    # Ordenar por contribución (de mayor a menor)
    detalles.sort(key=lambda x: x[1], reverse=True)

    mejores = detalles[:top_n]
    peores = detalles[-top_n:]

    lineas = []
    lineas.append(f"Barrio recomendado: {barrio['nombre']}")
    lineas.append(f"Perfil del cliente: {cliente['nombre']}")
    lineas.append("")

    lineas.append("Puntos fuertes para este cliente:")
    for var, contrib, v_barrio, v_cli in mejores:
        lineas.append(
            f"- {var}: el barrio tiene {v_barrio:.2f} y el cliente lo valora {v_cli:.2f}."
        )

    lineas.append("")
    lineas.append("Aspectos menos alineados / trade-offs:")
    for var, contrib, v_barrio, v_cli in peores:
        lineas.append(
            f"- {var}: el barrio tiene {v_barrio:.2f} pero el cliente lo valora {v_cli:.2f}."
        )

    return "\n".join(lineas)


if __name__ == "__main__":
    cliente_id = "daenerys"
    print(f"Recomendaciones para {CLIENTES[cliente_id]['nombre']}:\n")

    recs = recomendar_barrios(cliente_id, top_k=3)
    for i, r in enumerate(recs, start=1):
        print(f"{i}. {r['nombre']} (score={r['score']:.3f})")

    print("\nExplicación del top 1:\n")
    top1 = recs[0]
    barrio_doc = barrios_map[top1["barrio_id"]]
    print(explicar_recomendacion(barrio_doc, cliente_id))
