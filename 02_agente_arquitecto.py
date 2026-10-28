import os 
from dotenv import load_dotenv 
from mini_crew import Agent, Task, Crew, Process, LLM 
 
load_dotenv() 
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")
 
if not os.path.exists("PRD.md"): 
    print("[ERROR] No existe PRD.md. Ejecuta primero 01_agente_product_owner.py")
    raise SystemExit(1)
 
with open("PRD.md", "r", encoding="utf-8") as f: 
    contenido_prd = f.read() 
 
llm = LLM(model=model_name, api_key=api_key, temperature=0.1, 
max_tokens=2500) 
 
software_architect = Agent( 
    role="Lead Software Architect", 
    goal=(
        "Diseñar una especificación técnica minimalista, exacta y libre de "
        "ambigüedades en FastAPI y SQLite."
    ),
    backstory=( 
        "Arquitecto experto en microservicios Python. Diseñas contratos de "
        "base de datos y API ultra-limpios. Nunca agregas complejidad "
        "innecesaria ni tablas no solicitadas."
    ), 
    verbose=True, 
    llm=llm, 
) 
 
tarea_arquitectura = Task( 
    description=f"""Basado en el siguiente PRD: 
=== PRD === 
{contenido_prd} 
=== FIN PRD === 
 
Genera el documento ARCHITECTURE.md definiendo EXACTAMENTE esta arquitectura 
esbelta (sin agregar más tablas ni JWT): 
 
## 1. MODELO DE DATOS (SQLite / SQLAlchemy) 
Usa exclusivamente estas 2 tablas con estos nombres exactos de columnas: - Tabla `empleados`: 
  - `id`: Integer, Primary Key, autoincrement 
  - `nombre`: String, not null 
  - `email`: String, unique, not null 
  - `rol`: String, not null (Valores: 'EMPLEADO', 'MANAGER', 'ADMIN_RRHH') 
  - `anios_antiguedad`: Integer, not null, default 1 
  - `manager_id`: Integer, ForeignKey('empleados.id'), nullable=True 
 - Tabla `solicitudes_vacaciones`: 
  - `id`: Integer, Primary Key, autoincrement 
  - `empleado_id`: Integer, ForeignKey('empleados.id'), not null 
  - `dias_solicitados`: Integer, not null (> 0) 
  - `motivo`: String, nullable=True 
  - `estado`: String, not null, default 'PENDING' (Valores: 'PENDING', 
'APPROVED', 'REJECTED') 
  - `revisado_por_id`: Integer, ForeignKey('empleados.id'), nullable=True 
 
## 2. ESQUEMAS PYDANTIC V2 
Define las clases exactas: - `EmpleadoCreate`: nombre (str), email (str), rol (str), anios_antiguedad 
(int), manager_id (Optional[int] = None) 
- `EmpleadoResponse`: igual que Create + id (int), con `model_config = 
ConfigDict(from_attributes=True)` - `SaldoResponse`: empleado_id (int), dias_totales (int), dias_aprobados 
(int), saldo_disponible (int) - `SolicitudCreate`: empleado_id (int), dias_solicitados (int), motivo 
(Optional[str] = None) - `RevisionRequest`: accion (str: 'APPROVE' o 'REJECT') - `SolicitudResponse`: id (int), empleado_id (int), dias_solicitados (int), 
motivo (Optional[str]), estado (str), revisado_por_id (Optional[int]), con 
`model_config = ConfigDict(from_attributes=True)` 
## 3. ENDPOINTS REST Y RBAC (Autenticación por Header `X-User-Id: int`) 
Todos los endpoints reciben el header `X-User-Id: int = Header(...)` que 
identifica al usuario que hace la petición (si el usuario no existe en BD -> 
404): 
1. `GET /health` -> Público (sin header). Devuelve `200 OK` `{{"status": 
"ok"}}`. 
2. `POST /api/v1/empleados` -> Crea empleado (`201 Created`). Regla RBAC: Si 
la tabla `empleados` está vacía, permite crear el primer `ADMIN_RRHH` sin 
validar rol; si ya hay empleados, el usuario en `X-User-Id` debe tener rol 
`ADMIN_RRHH` (si no -> `403 Forbidden`). 
3. `GET /api/v1/vacaciones/saldo/{{empleado_id}}` -> Devuelve 
`SaldoResponse` (`200 OK`). Calcula `dias_totales = min(12 + 2 * 
max(anios_antiguedad - 1, 0), 20)`. 
4. `POST /api/v1/vacaciones/solicitar` -> Crea solicitud en `PENDING` (`201 
Created`). Regla: `dias_solicitados` debe ser <= `saldo_disponible` actual; 
si excede el saldo -> `400 Bad Request` con `detail="Insufficient vacation 
balance"`. 
5. `POST /api/v1/vacaciones/{{solicitud_id}}/revisar` -> Recibe 
`RevisionRequest`. Regla RBAC: El usuario `X-User-Id` debe tener rol 
`MANAGER` y ser el jefe directo del empleado de la solicitud 
(`empleado.manager_id == x_user_id`); si no lo es -> `403 Forbidden` con 
`detail="Unauthorized: Not the direct manager"`. Si la solicitud no está en 
`PENDING` -> `400 Bad Request`. Si `accion == 'APPROVE'` pasa a `APPROVED`, 
si `accion == 'REJECT'` pasa a `REJECTED`, guardando `revisado_por_id = 
x_user_id` (`200 OK`).""", 
expected_output=( 
"Documento Markdown técnico, limpio y estructurado exactamente en "
"las 3 secciones solicitadas (máximo 500 palabras). "
"Sin introducciones ni despedidas."
), 
agent=software_architect, 
output_file="ARCHITECTURE.md", 
) 
crew = Crew(agents=[software_architect], tasks=[tarea_arquitectura], 
process=Process.sequential, verbose=True) 
if __name__ == "__main__": 
 print("\n" + "=" * 70)
 print("   EJECUTANDO AGENTE 2: SOFTWARE ARCHITECT (ARQUITECTURA ESBELTA)")
 print("=" * 70)
 crew.kickoff()
 print("\n[OK] ARCHITECTURE.md generado exitosamente.")