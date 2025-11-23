from pymongo import MongoClient
import csv
import os
import math
import json
import difflib
import requests

# --- CONFIGURACIÓN ---
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "joc_de_barris"
COL_BARRIOS = "barrios"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COL_BARRIOS]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_FILE = os.path.join(BASE_DIR, "LA_Times_Neighborhood_Boundaries.geojson")

# --- PESOS POR DEFECTO (Para calcular el índice global inicial) ---
DEFAULT_WEIGHTS = {
    "transporte": {
        "metro": 0.37, "bus": 0.23, "taxi": 0.11, "aeropuerto": 0.29
    },
    "ocio": {
        "cine": 0.21, "gimnasio": 0.15, "bares": 0.23, "parque": 0.18, "restaurante": 0.23
    },
    "salut": {
        "aire": 0.25, "hospital": 0.34, "verde": 0.28, "sonido": 0.23
    },
    "seguridad": {
        "robos_sin": 0.07, "robos_con": 0.31, "allanamiento": 0.19,
        "asalto": 0.15, "vandalismo": 0.03, "amenaza": 0.25
    },
    "densidad_poblacion": {
        "centro": 0.45, "residencial": 0.275, "infantil": 0.275
    },
    "precio": {
        "vivienda": 0.4, "alquiler": 0.4, "prevision": 0.2
    }
}

# --- MAPEO DE COLUMNAS CSV A VARIABLES INTERNAS ---
# Asocia el nombre de la columna en tus CSVs con la clave interna
COLUMN_MAPPING = {
    # Transporte
    "num_estaciones_bus": "bus",
    "tiene_metro": "metro",
    "disponibilidad_taxi": "taxi",
    "cercania_aeropuerto": "aeropuerto",

    # Ocio
    "cines_score": "cine", "gimnasios_score": "gimnasio",
    "parques_score": "parque", "restaurantes_score": "restaurante",  "bares_score": "bares",

    # Salud
    "calidad_aire": "aire", "aire": "aire",
    "hospitales": "hospital", "hospital": "hospital",
    "zonas_verdes": "verde", "verde": "verde",
    "ruido": "sonido", "sonido": "sonido",

    # Seguridad (Asumiendo nombres del
    "robbery": "robos_sin",
    "theft": "robos_con",
    "vandalism": "vandalismo",
    "assault": "asalto",
    "battery": "amenaza",
    "tresspasing": "allanamiento",

    # Precio
    "precio_normalizado": "vivienda",
    "precio_alquiler_normalizado": "alquiler",
    "crecimiento_normalizado": "prevision",

    # Densidad
    "densidad_normalizada": "centro",
    "intensidad_residencial": "residencial",
    "indice_familia": "infantil",
}

# Archivos CSV esperados en la carpeta
CSV_FILES = {
    "transporte": "transporte_datos_final.csv",
    "ocio": "ocio_datos_final.csv",
    "salut": "salut_datos_final.csv",
    "seguridad": "seguridad_datos_final.csv",  # Asegúrate que se llame así
    "densidad_poblacion": "poblacion_datos_final.csv",
    "precio": "precio_datos_final.csv"
}

# --- GEOJSON ---
URLS_POSIBLES = [
    "https://raw.githubusercontent.com/datadesk/los-angeles-boundaries/master/geojson/neighborhoods.geojson",
]
COORDENADAS_BASE = {"Downtown": (34.0407, -118.2468)}


def generate_hexagon(lat, lon, r=1.5):
    coords = []
    for i in range(6):
        ang = math.pi / 180 * 60 * i
        d_lat = (r / 111.0) * math.cos(ang)
        d_lon = (r / (111.0 * math.cos(math.radians(lat)))) * math.sin(ang)
        coords.append([lon + d_lon, lat + d_lat])
    coords.append(coords[0])
    return [coords]


def obtener_geometrias():
    data = None
    if os.path.exists(GEOJSON_FILE):
        try:
            with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass

    if not data:
        for url in URLS_POSIBLES:
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    with open(GEOJSON_FILE, "w", encoding="utf-8") as f: json.dump(data, f)
                    break
            except:
                pass

    geos = {}
    names = []
    if data:
        for f in data.get("features", []):
            p = f.get("properties", {})
            n = p.get("name") or p.get("NAME") or p.get("slug")
            if n:
                geos[n] = f.get("geometry")
                names.append(n)
    return geos, names


def slugify(name): return name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")


# --- CARGA DE DATOS ---
def cargar_datos_completos():
    """
    Lee todos los CSVs, extrae las sub-variables y las organiza por barrio y categoría.
    """
    datos_barrios = {}  # Estructura: { "slug": { "nombre": "X", "sub_coords": {...} } }

    for categoria, filename in CSV_FILES.items():
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            print(f"⚠️ Falta archivo: {filename} (Se usarán ceros para {categoria})")
            continue

        with open(path, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Buscar nombre del barrio
                nombre_raw = row.get("nombre") or row.get("Barrio")
                if not nombre_raw: continue

                bid = slugify(nombre_raw.strip())
                if bid not in datos_barrios: datos_barrios[bid] = {"nombre": nombre_raw.strip(), "sub_coords": {}}
                if categoria not in datos_barrios[bid]["sub_coords"]: datos_barrios[bid]["sub_coords"][categoria] = {}

                # Mapear columnas del CSV a nuestras sub-variables
                for col_csv, val in row.items():
                    col_norm = col_csv.lower().strip()

                    if col_norm in COLUMN_MAPPING:
                        key_interna = COLUMN_MAPPING[col_norm]

                        # Solo guardamos si esta sub-variable pertenece a la categoría actual
                        if key_interna in DEFAULT_WEIGHTS[categoria]:
                            try:
                                v = float(val)
                                # Asumimos que el CSV YA VIENE NORMALIZADO (0 a 1)
                                # Solo protegemos contra errores muy locos
                                v = max(0.0, min(1.0, v))
                            except:
                                v = 0.0

                            datos_barrios[bid]["sub_coords"][categoria][key_interna] = v

    return datos_barrios


# --- PROCESO PRINCIPAL ---
print("--- Iniciando Carga ---")

datos = cargar_datos_completos()
geos, geo_names = obtener_geometrias()
barrios_finales = []

# Lista de barrios basada en los datos cargados
todos_ids = list(datos.keys())

if not todos_ids:
    print("❌ ERROR: No se han cargado barrios. Revisa los nombres de los CSV.")
    exit()

for bid in todos_ids:
    data = datos[bid]
    nombre = data["nombre"]

    sub_coords = data["sub_coords"]
    coords_globales = {}  # Aquí guardamos el resultado del cálculo con pesos default

    # --- CÁLCULO DE NOTA GLOBAL ---
    for cat, pesos_cat in DEFAULT_WEIGHTS.items():
        valores_reales = sub_coords.get(cat, {})

        valores = []

        for sub_key in pesos_cat.keys():
            valor = valores_reales.get(sub_key, 0.0)
            sub_coords[cat][sub_key] = valor
            valores.append(valor)

        # Si no hay valores, la categoría es 0
        if valores:
            coords_globales[cat] = round(sum(valores) / len(valores), 4)
        else:
            coords_globales[cat] = 0.0

    # --- GEOMETRÍA ---
    geo = geos.get(nombre)
    if not geo and geo_names:
        m = difflib.get_close_matches(nombre, geo_names, n=1, cutoff=0.6)
        if m: geo = geos[m[0]]

    lat, lon = 34.0522, -118.2437
    if geo:
        try:
            c = geo["coordinates"][0]
            while isinstance(c[0], list): c = c[0]
            lon = sum(p[0] for p in c) / len(c)
            lat = sum(p[1] for p in c) / len(c)
        except:
            pass
    else:
        h = sum(ord(c) for c in nombre)
        lat += (h % 100 - 50) * 0.001
        lon += (h % 100 - 50) * 0.001
        geo = {"type": "Polygon", "coordinates": generate_hexagon(lat, lon)}

    # --- DOCUMENTO FINAL ---
    doc = {
        "_id": bid,
        "nombre": nombre,
        "coords": coords_globales,  # Resultado cálculo default
        "sub_coords": sub_coords,  # Datos crudos para recalculo API
        "location": {"lat": lat, "lon": lon},
        "geometry": geo
    }
    barrios_finales.append(doc)

# GUARDAR
col.delete_many({})
if barrios_finales:
    col.insert_many(barrios_finales)
    print(f"✅ Guardados {len(barrios_finales)} barrios.")
    print("   - Se han calculado los índices globales usando los pesos por defecto.")
    print("   - Se han guardado las sub-variables para uso dinámico.")