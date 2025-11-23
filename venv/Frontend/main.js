// =========================
// CONFIGURACIÓN
// =========================
const API_URL_TEXTO = "http://127.0.0.1:8000/api/recomendar_desde_texto";
const API_URL_PREFS = "http://127.0.0.1:8000/api/recomendar_desde_prefs";

// =========================
// LOGICA "ME DA IGUAL" (EXCLUSIÓN MUTUA)
// =========================
document.addEventListener("DOMContentLoaded", () => {
    const groups = document.querySelectorAll(".var-group");
    groups.forEach(group => {
        const ignoreCheckbox = group.querySelector('input[value="ignore"]');
        const otherCheckboxes = group.querySelectorAll('input:not([value="ignore"])');
        if (ignoreCheckbox) {
            ignoreCheckbox.addEventListener('change', () => {
                if (ignoreCheckbox.checked) otherCheckboxes.forEach(cb => cb.checked = false);
            });
        }
        otherCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                if (cb.checked && ignoreCheckbox) ignoreCheckbox.checked = false;
            });
        });
    });
});

// Detectar cuando el usuario modifica un peso
document.querySelectorAll('.weight-input').forEach(inp => {
    inp.addEventListener('input', () => {
        inp.dataset.touched = "true";
    });
});


// =========================
// ESTADO
// =========================
let currentBarrios = [];
let currentIndex = 0;
let map = null;
let currentGeoJSONLayer = null;

// DOM
const divContainer = document.getElementById("carousel-container");
const divPrefsSummary = document.getElementById("user-prefs-summary");
const divCard = document.getElementById("active-card-container");
const spanCounter = document.getElementById("counter");
const btnPrev = document.getElementById("prev-btn");
const btnNext = document.getElementById("next-btn");
const divError = document.getElementById("error");
const tabTexto = document.getElementById("tab-texto");
const tabForm = document.getElementById("tab-form");

tabTexto.addEventListener("click", () => switchTab(true));
tabForm.addEventListener("click", () => switchTab(false));

function switchTab(isText) {
  tabTexto.className = isText ? "tab-button tab-active" : "tab-button";
  tabForm.className = !isText ? "tab-button tab-active" : "tab-button";
  document.getElementById("form-preferencias-texto").style.display = isText ? "block" : "none";
  document.getElementById("form-preferencias-form").style.display = !isText ? "block" : "none";
  divContainer.style.display = "none";
  divPrefsSummary.style.display = "none";
  divError.textContent = "";
}

// =========================
// CÁLCULO DE PREFERENCIAS Y MODIFICACIONES
// =========================
function calcularPrefsDesdeSubvariables() {
  const prefs = {
    salut: -1, transporte: -1, precio: -1, ocio: -1, seguridad: -1, densidad_poblacion: -1,
  };

  const modificacionesUsuario = {};

  // --- PESOS BASE (TU BASE DE DATOS DE PESOS) ---
  const defaultWeights = {
    // TRANSPORTE
    metro: 0.37, bus: 0.23, taxi: 0.11, aeropuerto: 0.29,
    // OCIO
    cine: 0.21, gimnasio: 0.15, bares: 0.23, parque: 0.18, restaurante: 0.23,
    // SALUT
    aire: 0.25, hospital: 0.34, verde: 0.28, sonido: 0.23,
    // SEGURIDAD
    robos_sin: 0.07, robos_con: 0.31, allanamiento: 0.19, asalto: 0.15, vandalismo: 0.03, amenaza: 0.25,
    // DENSIDAD
    centro: 0.45, residencial: 0.275, infantil: 0.275,
    // PRECIO
    vivienda: 0.4, alquiler: 0.4, prevision: 0.2,
    // DEFAULT
    default: 0.5
  };

  const groups = document.querySelectorAll(".var-group");

  groups.forEach((group) => {
    const varName = group.getAttribute("data-var");
    const ignoreCheckbox = group.querySelector('input[value="ignore"]');
    const otherCheckboxes = group.querySelectorAll('input:not([value="ignore"])');

    // 1. ME DA IGUAL -> -1
    if (ignoreCheckbox && ignoreCheckbox.checked) {
        prefs[varName] = -1;
        return;
    }

    let activeItemsWeights = [];

    otherCheckboxes.forEach(cb => {
        if (cb.checked) {
            let weight = 0;
            const wrapper = cb.closest('.option-wrapper');
            const inputWeight = wrapper.querySelector('.weight-input');

            // Peso base (0.0 a 1.0)
            const baseWeight = defaultWeights[cb.value] || defaultWeights.default;

            // 1. DETERMINAR PESO (Usuario vs. Predeterminado)
            const userTouched = inputWeight && inputWeight.dataset.touched === "true";

            if (userTouched) {
                // El usuario ha definido su propio peso (0-100 -> 0.0-1.0)
                let inputVal = parseFloat(inputWeight.value);
                weight = inputVal / 100.0;

                // Si el valor no es válido, usamos el base. Si es válido, guardamos modificación.
                if (isNaN(weight) || weight < 0 || weight > 1) {
                    weight = baseWeight;
                } else {
                    modificacionesUsuario[cb.value] = {
                        original: baseWeight,
                        nuevo: weight,
                        diferencia: (weight - baseWeight).toFixed(2)
                    };
                }
            } else {
                // Usamos el peso base predeterminado
                weight = baseWeight;
            }

            activeItemsWeights.push(weight);
        }
    });

    // 2. ASIGNAR VALOR FINAL AL GRUPO -> MEDIA, NO SUMA
    let finalScore = 0;

    if (activeItemsWeights.length > 0) {
        const sum = activeItemsWeights.reduce((a, b) => a + b, 0);
        finalScore = sum / activeItemsWeights.length;  // ✔ MEDIA
    }

    if (varName === "precio") prefs.precio = finalScore;
    else if (varName === "seguridad") prefs.seguridad = finalScore;
    else prefs[varName] = finalScore;
  });

  return { prefs, modificacionesUsuario };
}


// =========================
// RENDERIZADO
// =========================
function renderUserPrefs(prefs) {
  divPrefsSummary.style.display = "block";
  let html = `<h3 style="margin-top:0; margin-bottom:0.5rem; font-size:1.1rem; color:#f0f0f0; font-family:'Cinzel';">Tus Estandartes</h3>`;
  html += `<div class="prefs-grid">`;

  for (const [key, value] of Object.entries(prefs)) {
    let textoValor = "", color = "#666", border = "#444";
    if (value === -1) {
        textoValor = "-"; color = "#555"; border = "#333";
    } else {
        textoValor = (value * 100).toFixed(0) + "%";
        if (key === "precio") {
            if (value < 0.4) { color = "#50c878"; border = "#2e8b57"; }
            else { color = "#d4af37"; border = "#d4af37"; }
        } else {
            if (value > 0.6) { color = "#d4af37"; border = "#d4af37"; }
            else { color = "#a8a8a8"; border = "#444"; }
        }
    }
    let opacity = value === -1 ? 0.4 : 1;
    html += `<div class="pref-item" style="border-color:${border}; opacity: ${opacity}"><span style="text-transform: capitalize; color:#e3dac9;">${key.replaceAll("_", " ")}</span><div class="pref-value" style="color: ${color}; font-size: 1.1rem;">${textoValor}</div></div>`;
  }
  html += `</div>`; divPrefsSummary.innerHTML = html;
}

// =========================
// API & ENVÍO DE DATOS
// =========================
document.getElementById("form-preferencias-texto").addEventListener("submit", (e) => handleSearch(e, API_URL_TEXTO, getTextoBody));
document.getElementById("form-preferencias-form").addEventListener("submit", (e) => handleSearch(e, API_URL_PREFS, getFormBody));

function getTextoBody() { return { texto: document.getElementById("texto").value, top_k: 3 }; }

function getFormBody() {
    const resultado = calcularPrefsDesdeSubvariables();
    console.log("🔍 Modificaciones del usuario:", resultado.modificacionesUsuario);

    return {
        prefs: resultado.prefs,
        sub_prefs: resultado.modificacionesUsuario,
        top_k: 3
    };
}

async function handleSearch(e, url, bodyFunc) {
  e.preventDefault();
  const btn = e.target.querySelector("button");
  const originalText = btn.textContent;
  btn.disabled = true; btn.textContent = "Consultando...";
  divError.textContent = ""; divContainer.style.display = "none"; divPrefsSummary.style.display = "none";

  try {
    const res = await fetch(url, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(bodyFunc())
    });
    if (!res.ok) throw new Error(`Error HTTP: ${res.status}`);
    const data = await res.json();

    if (data.prefs) renderUserPrefs(data.prefs);
    if (data.barrios && data.barrios.length > 0) iniciarCarrusel(data.barrios);
    else divError.textContent = "No se encontraron resultados.";

  } catch (err) {
    console.error(err);
    divError.textContent = "Error de conexión.";
  } finally {
    btn.disabled = false; btn.textContent = originalText;
  }
}

function iniciarCarrusel(barrios) {
  currentBarrios = barrios;
  currentIndex = 0;
  divContainer.style.display = "block";
  if (!map) {
    map = L.map('map-container').setView([34.05, -118.24], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(map);
  }
  actualizarVista();
  divPrefsSummary.scrollIntoView({ behavior: 'smooth' });
}

function actualizarVista() {
  const barrio = currentBarrios[currentIndex];
  spanCounter.textContent = `${currentIndex + 1} / ${currentBarrios.length}`;
  divCard.innerHTML = `<div class="active-barrio-card"><div class="score-badge">Similitud: ${(barrio.score * 100).toFixed(0)}%</div><h2 style="margin: 0.5rem 0;">${barrio.nombre}</h2><p style="color:#a8a8a8;">${barrio.nombre} es tu destino.</p><div class="stats-row">${Object.entries(barrio.coords).map(([k,v]) => `<div class="stat-pill"><b>${k}:</b> ${(v*100).toFixed(0)}%</div>`).join('')}</div></div>`;
  if (currentGeoJSONLayer) map.removeLayer(currentGeoJSONLayer);
  if (barrio.geometry) {
      currentGeoJSONLayer = L.geoJSON(barrio.geometry, { style: { color: '#2E86C1', weight: 3, opacity: 0.9, fillOpacity: 0.2 } }).addTo(map);
      map.flyToBounds(currentGeoJSONLayer.getBounds(), { padding: [50, 50], duration: 1.5 });
  } else if (barrio.location) {
      currentGeoJSONLayer = L.marker([barrio.location.lat, barrio.location.lon]).addTo(map);
      map.flyTo([barrio.location.lat, barrio.location.lon], 13);
  }
  setTimeout(() => map.invalidateSize(), 200);
}

btnPrev.addEventListener("click", () => { if (currentIndex > 0) { currentIndex--; actualizarVista(); } });
btnNext.addEventListener("click", () => { if (currentIndex < currentBarrios.length - 1) { currentIndex++; actualizarVista(); } });