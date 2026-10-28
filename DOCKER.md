# Ejecutar los agentes con Docker

Requisitos: Docker Desktop instalado y en ejecución, además de una clave de API
de Gemini.

1. Copia `.env.example` como `.env` y reemplaza el valor de `GEMINI_API_KEY`.
   No subas `.env` al repositorio.
2. Construye la imagen:

   ```powershell
   docker compose build
   ```

3. Ejecuta los agentes en orden. Los archivos que producen quedan guardados en
   el directorio del proyecto:

   ```powershell
   docker compose run --rm agents python 01_agente_product_owner.py
   docker compose run --rm agents python 02_agente_arquitecto.py
   docker compose run --rm agents python 03_agente_developer.py
   docker compose run --rm agents python 04_agente_qa.py
   ```

El primer agente también se ejecuta con `docker compose run --rm agents`, que
usa el comando predeterminado de la imagen. El servicio monta el proyecto en
`/workspace`; por eso `PRD.md`, `ARCHITECTURE.md` y `generated_project/`
persisten en el equipo aunque cada contenedor se elimine al terminar.
