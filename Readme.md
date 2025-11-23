Para ejecutar el repositorio seguir los siguientes pasos:

1. Crear un entorno virtual (python3 -m venv path_to_venv)
2. Activar entorno virtual (source path_to_venv/bin/activate), todo lo siguiente tiene que ser en un entorno virtual
3. Instalar mongodb (sudo apt install mongodb)
4. Iniciar mongodb (sudo systemctl start mongodb)
5. Instalar con pip install las siguientes librerias: pymongo, fastapi, uvicorn, python-dotenv, requests) 
6. Exportar API key, endpoint y modelo de Abacus.AI 
(export LLM_API_KEY="s2_4035ba27497c470aa4e8f2c714e1ee21"
export LLM_ENDPOINT="https://routellm.abacus.ai/v1/chat/completions"
export LLM_MODEL="gpt-4.1-mini")
7. Arrancar el backend (uvicorn Backend.api:app --reload)
8. Abrir puerto para el frontend (python3 -m http.server 8001)
