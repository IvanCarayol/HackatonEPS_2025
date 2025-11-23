from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import os
import json
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Variables del sistema
VARIABLES = ["salut", "transporte", "precio", "ocio", "seguridad", "densidad_poblacion"]

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "joc_de_barris"
COL_BARRIOS = "barrios"

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "https://routellm.abacus.ai/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# === MODELOS ===
class Location(BaseModel):
    lat: float
    lon: float


class BarrioOut(BaseModel):
    barrio_id: str
    nombre: str
    score: float
    coords: Dict[str, float]
    location: Location
    geometry: Optional[Dict[str, Any]] = None


class PreferenciasRequest(BaseModel):
    texto: str
    top_k: int = 3


class PreferenciasDirectasRequest(BaseModel):
    prefs: Dict[str, float]
    top_k: int = 3


class RecomendacionResponse(BaseModel):
    prefs: Dict[str, float]
    barrios: List[BarrioOut]


# === INICIO DB ===
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
col_barrios = db[COL_BARRIOS]

# Cargar barrios
barrios_map = {}
for doc in col_barrios.find({}):
    if "coords" in doc and "crimen" in doc["coords"]:
        doc["coords"]["seguridad"] = doc["coords"].pop("crimen")
    barrios_map[doc["_id"]] = doc


# === FUNCIÓN AUXILIAR DE NORMALIZACIÓN ===
def normalizar_prefs(prefs: Dict[str, float]) -> Dict[str, float]:
    """
    Toma un diccionario de pesos y asegura que la suma sea 1.0 (100%).
    Si la suma es 0, devuelve todo a 0.
    """
    total = sum(prefs.values())
    if total > 0:
        return {k: v / total for k, v in prefs.items()}
    return prefs  # Todo ceros


# === ALGORITMO DE RECOMENDACIÓN ===
def recomendar_desde_prefs(prefs: Dict[str, float], top_k: int = 3):
    resultados = []

    # Las prefs ya vienen normalizadas, pero por seguridad recalculamos peso total
    # (En este punto la suma debería ser 1.0 si pasó por normalizar_prefs)

    for _id, barrio in barrios_map.items():
        coords = barrio["coords"]

        # Producto punto simple: CoordsBarrio * PesoUsuario
        # Como prefs suman 1.0, el score máximo teórico será 1.0
        final_score = sum(coords.get(v, 0) * prefs.get(v, 0) for v in VARIABLES)

        resultados.append({
            "barrio_id": _id,
            "nombre": barrio["nombre"],
            "score": final_score,
            "coords": coords,
            "location": barrio.get("location", {"lat": 34.05, "lon": -118.24}),
            "geometry": barrio.get("geometry")
        })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:top_k]


# === HEURÍSTICA (PALABRAS CLAVE) ===
def analisis_por_palabras_clave(texto: str) -> Dict[str, float]:
    texto = texto.lower()
    # INICIO EN 0.0: Si no se menciona, no cuenta.
    scores = {v: 0.0 for v in VARIABLES}

    if any(w in texto for w in ["parque", "aire", "verde", "arbol", "naturaleza"]):
        scores["salut"] += 1.0
    if any(w in texto for w in ["silencio", "tranquilo", "paz"]):
        scores["salut"] += 0.5

    if any(w in texto for w in ["barato", "economico", "ahorro", "pobre"]):
        scores["precio"] += 1.0

    if any(w in texto for w in ["lujo", "caro", "rico", "exclusivo"]):
        scores["precio"] += 0.2  # Penaliza precio barato (busca caro?) -> lógica compleja, simplificamos
        scores["seguridad"] += 0.5

    if any(w in texto for w in ["seguro", "policia", "miedo", "robo", "crimen", "vigilancia"]):
        scores["seguridad"] += 1.0

    if any(w in texto for w in ["fiesta", "bares", "noche", "teatro", "cultura"]):
        scores["ocio"] += 1.0

    if any(w in texto for w in ["metro", "bus", "transporte", "coche", "trafico"]):
        scores["transporte"] += 1.0

    if any(w in texto for w in ["gente", "centro", "vida", "tiendas"]):
        scores["densidad_poblacion"] += 1.0

    # NORMALIZAR PARA QUE SUMEN 100%
    return normalizar_prefs(scores)


# === LLM ===
def llamar_llm_y_mapear(texto_usuario: str) -> Dict[str, float]:
    if not LLM_API_KEY: return analisis_por_palabras_clave(texto_usuario)

    system_prompt = f"""
    Analiza el texto del usuario para encontrar qué busca en un barrio.
    Variables disponibles: {', '.join(VARIABLES)}.

    Instrucciones:
    1. Asigna una importancia de 0 a 10 a cada variable MENCIONADA.
    2. Si una variable NO se menciona o no es relevante, su valor debe ser 0.
    3. Devuelve SOLO un JSON con las claves y valores numéricos.
    """

    try:
        response = requests.post(
            LLM_ENDPOINT,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": texto_usuario}
                ],
                "temperature": 0.0
            },
            timeout=5
        )

        if response.status_code != 200:
            return analisis_por_palabras_clave(texto_usuario)

        content = response.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()

        raw_prefs = json.loads(content)

        # Limpiar y asegurar estructura (default 0.0 si no existe)
        clean_prefs = {v: float(raw_prefs.get(v, 0.0)) for v in VARIABLES}

        # NORMALIZAR EL RESULTADO DEL LLM AL 100%
        return normalizar_prefs(clean_prefs)

    except Exception as e:
        print(f"Error LLM: {e}")
        return analisis_por_palabras_clave(texto_usuario)


# === ENDPOINTS API ===
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])


@app.post("/api/recomendar_desde_texto", response_model=RecomendacionResponse)
def api_recomendar_desde_texto(req: PreferenciasRequest):
    # 1. Obtenemos preferencias normalizadas (Suma = 1.0)
    prefs = llamar_llm_y_mapear(req.texto)

    # 2. Buscamos barrios
    barrios = recomendar_desde_prefs(prefs, top_k=req.top_k)

    return RecomendacionResponse(prefs=prefs, barrios=[BarrioOut(**b) for b in barrios])


@app.post("/api/recomendar_desde_prefs", response_model=RecomendacionResponse)
def api_recomendar_desde_prefs(req: PreferenciasDirectasRequest):
    # En modo manual, también normalizamos lo que viene del front
    # para que el gráfico de "Tu Juramento" muestre % reales.
    prefs_norm = normalizar_prefs(req.prefs)

    barrios = recomendar_desde_prefs(prefs_norm, top_k=req.top_k)
    return RecomendacionResponse(prefs=prefs_norm, barrios=[BarrioOut(**b) for b in barrios])