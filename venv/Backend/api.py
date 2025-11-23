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


# === ALGORITMO DE SIMILITUD (TARGET MATCHING) ===
def recomendar_desde_prefs(prefs: Dict[str, float], top_k: int = 3):
    resultados = []

    # Solo consideramos variables donde el valor es >= 0.0
    # Si es -1.0 (o menor), se ignora en el cálculo.
    vars_activas = [v for v in VARIABLES if prefs.get(v, -1.0) >= 0.0]

    if not vars_activas:
        return []

    for _id, barrio in barrios_map.items():
        coords = barrio["coords"]
        distancia_total = 0.0

        for var in vars_activas:
            objetivo_usuario = prefs[var]  # 0.0 (Pobre) o 1.0 (Rico)
            valor_barrio = coords.get(var, 0.5)

            # Similitud: 1.0 es idéntico, 0.0 es opuesto
            diferencia = abs(objetivo_usuario - valor_barrio)
            similitud = 1.0 - diferencia
            distancia_total += similitud

        final_score = distancia_total / len(vars_activas)

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
    print("⚠️ Usando modo palabras clave (sin IA)...")
    texto = texto.lower()

    # INICIALIZAMOS A -1.0 (IGNORAR VARIABLE)
    scores = {v: -1.0 for v in VARIABLES}

    # --- REGLAS DE PRECIO ---
    if any(w in texto for w in ["barato", "economico", "ahorro", "pobre", "asequible", "rata", "tirado"]):
        scores["precio"] = 0.0  # Objetivo: Precio Bajo

    if any(w in texto for w in ["lujo", "caro", "rico", "exclusivo", "dinero"]):
        scores["precio"] = 1.0  # Objetivo: Precio Alto
        scores["seguridad"] = 1.0

    # --- OTRAS VARIABLES ---
    if any(w in texto for w in ["parque", "aire", "verde", "arbol", "naturaleza", "silencio", "paz"]):
        scores["salut"] = 1.0

    if any(w in texto for w in ["seguro", "policia", "vigilancia"]):
        scores["seguridad"] = 1.0
    if any(w in texto for w in ["peligro", "miedo", "robo", "crimen", "inseguro"]):
        scores["seguridad"] = 0.0

    if any(w in texto for w in ["fiesta", "bares", "noche", "teatro", "cultura", "ocio"]):
        scores["ocio"] = 1.0

    if any(w in texto for w in ["metro", "bus", "transporte", "coche", "trafico"]):
        scores["transporte"] = 1.0

    if any(w in texto for w in ["gente", "centro", "vida", "tiendas", "urbano"]):
        scores["densidad_poblacion"] = 1.0

    return scores


# === LLM (INTELIGENCIA ARTIFICIAL) ===
def llamar_llm_y_mapear(texto_usuario: str) -> Dict[str, float]:
    if not LLM_API_KEY: return analisis_por_palabras_clave(texto_usuario)

    print(f"🤖 Preguntando a la IA: '{texto_usuario}'")

    system_prompt = f"""
    Eres un traductor de preferencias inmobiliarias a OBJETIVOS numéricos.
    Variables: {', '.join(VARIABLES)}.

    Debes devolver un JSON.
    - Usa 0.0 para desear nivel BAJO/MINIMO.
    - Usa 1.0 para desear nivel ALTO/MAXIMO.
    - Usa -1.0 si la variable NO SE MENCIONA (Esto es muy importante).

    REGLAS:
    1. PRECIO:
       - "Pobre", "Barato", "Ratas": Objetivo = 0.0 
       - "Rico", "Lujo", "Caro": Objetivo = 1.0 

    2. SEGURIDAD:
       - "Peligroso", "Miedo": Objetivo = 0.0 
       - "Seguro", "Tranquilo": Objetivo = 1.0 

    3. RESTO:
       - "Quiero X" -> 1.0
       - "Odio X" -> 0.0
       - No menciona X -> -1.0
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

        # Limpieza: aseguramos que lo que no venga sea -1.0
        clean_prefs = {}
        for v in VARIABLES:
            clean_prefs[v] = float(raw_prefs.get(v, -1.0))

        return clean_prefs

    except Exception as e:
        print(f"❌ Excepción LLM: {e}")
        return analisis_por_palabras_clave(texto_usuario)


# === ENDPOINTS API ===
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])


@app.post("/api/recomendar_desde_texto", response_model=RecomendacionResponse)
def api_recomendar_desde_texto(req: PreferenciasRequest):
    prefs = llamar_llm_y_mapear(req.texto)
    barrios = recomendar_desde_prefs(prefs, top_k=req.top_k)

    # CAMBIO IMPORTANTE: Enviamos prefs tal cual (con sus -1.0)
    # El frontend ya sabe pintar -1 como "Indiferente".
    return RecomendacionResponse(prefs=prefs, barrios=[BarrioOut(**b) for b in barrios])


@app.post("/api/recomendar_desde_prefs", response_model=RecomendacionResponse)
def api_recomendar_desde_prefs(req: PreferenciasDirectasRequest):
    barrios = recomendar_desde_prefs(req.prefs, top_k=req.top_k)
    return RecomendacionResponse(prefs=req.prefs, barrios=[BarrioOut(**b) for b in barrios])