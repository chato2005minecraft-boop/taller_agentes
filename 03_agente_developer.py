import os 
import sys 
import subprocess 
from pathlib import Path 
from dotenv import load_dotenv 
from mini_crew import ( 
Agent, 
Task, 
Crew, 
LLM, 
set_workspace_dir, 
) 
import mini_crew 
 
# 1. Cargar configuración y validar artefactos previos 
load_dotenv() 
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")
 
for archivo in ("PRD.md", "ARCHITECTURE.md"): 
    if not os.path.exists(archivo): 
        print(
            f"[ERROR] No se encontró '{archivo}'. "
            "Ejecuta primero los agentes 01 y 02."
        )
        raise SystemExit(1)
 
with open("PRD.md", "r", encoding="utf-8") as f: 
    prd_content = f.read() 
 
with open("ARCHITECTURE.md", "r", encoding="utf-8") as f: 
    arch_content = f.read() 
 
# 2. Preparar directorio de salida (generated_project) 
set_workspace_dir(os.getenv("WORKSPACE_DIR", "./generated_project")) 
base_dir = mini_crew.WORKSPACE_DIR.resolve() 
(base_dir / "app").mkdir(parents=True, exist_ok=True) 
 
# Crear __init__.py y requirements.txt de forma determinista 
(base_dir / "app" / "__init__.py").write_text("# TalentCore API Package\n", 
encoding="utf-8") 
(base_dir / "requirements.txt").write_text( 
    "fastapi\nuvicorn[standard]\nsqlalchemy\npydantic\npytest\nhttpx\n", 
    encoding="utf-8", 
) 
print(f"--> Directorio de proyecto preparado en: {base_dir}") 
 
# 3. Configurar LLM con margen amplio de salida (max_tokens=6000) 
llm = LLM(model=model_name, api_key=api_key, temperature=0.1, 
max_tokens=6000) 
 
backend_developer = Agent( 
    role="Senior Python & FastAPI Backend Developer", 
    goal=(
        "Escribir código Python limpio, conciso y 100% funcional siguiendo "
        "exactamente ARCHITECTURE.md."
    ),
    backstory=( 
        "Desarrollador experto en FastAPI, SQLAlchemy 2.0 y Pydantic v2. " 
        "Escribes únicamente código Python válido, compacto y sin "
        "comentarios extensos innecesarios."
    ), 
    verbose=True, 
    llm=llm, 
) 
 
# 4. Tarea 1: Generar Capa de Datos y Esquemas (app/models.py) 
ruta_models = str(base_dir / "app" / "models.py") 
 
tarea_models = Task( 
    description=f"""Basado en esta especificación técnica: 
=== ARCHITECTURE.md === 
{arch_content} 
=== FIN ARCHITECTURE.md === 
 
Escribe el código Python completo para el archivo `app/models.py`. 
DEBE incluir: 
1. Configuración SQLite: `SQLALCHEMY_DATABASE_URL = 
"sqlite:///./talentcore.db"`, `engine = 
create_engine(SQLALCHEMY_DATABASE_URL, connect_args={{"check_same_thread": 
False}})`, `SessionLocal = sessionmaker(autocommit=False, autoflush=False, 
bind=engine)`, `Base` declarativa y la función generadora `get_db()`. 
2. Los 2 modelos ORM exactos: `Empleado` (`__tablename__ = "empleados"`) y 
`SolicitudVacaciones` (`__tablename__ = "solicitudes_vacaciones"`). 
3. Los 6 esquemas Pydantic v2 exactos: `EmpleadoCreate`, `EmpleadoResponse`, 
`SaldoResponse`, `SolicitudCreate`, `RevisionRequest`, `SolicitudResponse`. 
 
REGLA ESTRICTA: Devuelve ÚNICAMENTE el código Python sin explicaciones ni 
texto adicional.""", 
    expected_output="Código Python puro del archivo app/models.py.", 
    agent=backend_developer, 
    output_file=ruta_models, 
) 
 
print("\n" + "=" * 70) 
print("   EJECUTANDO AGENTE 3: BACKEND DEVELOPER (PASO 1/2: app/models.py)") 
print("=" * 70) 
Crew(agents=[backend_developer], tasks=[tarea_models], 
verbose=True).kickoff() 
 
# Leer models.py generado e incluirlo como referencia exacta para main.py.
codigo_models = Path(ruta_models).read_text(encoding="utf-8") 
# 5. Tarea 2: Generar API y Reglas de Negocio (app/main.py) 
ruta_main = str(base_dir / "app" / "main.py") 
tarea_main = Task( 
description=f"""Escribe el código Python completo para `app/main.py` 
importando los elementos desde `app.models`. 
Aquí tienes el código exacto de `app/models.py`: 
=== app/models.py === 
{codigo_models} 
=== FIN app/models.py === 
Instrucciones obligatorias para `app/main.py`: 
1. Crea `app = FastAPI(title="TalentCore API")` y ejecuta 
`Base.metadata.create_all(bind=engine)`. 
2. Crea una función auxiliar `calcular_saldo(emp: Empleado, db: Session) -> 
tuple[int, int, int]` que devuelva `(dias_totales, dias_aprobados, 
saldo_disponible)`: - `dias_totales = 12 if emp.anios_antiguedad < 1 else min(12 + 2 * 
(emp.anios_antiguedad - 1), 20)` - `dias_aprobados` = suma de `dias_solicitados` en `SolicitudVacaciones` 
donde `empleado_id == emp.id` y `estado == "APPROVED"`. - `saldo_disponible = dias_totales - dias_aprobados`. 
3. Implementa los 5 endpoints exactos de forma concisa (sin docstrings 
largos): - `GET /health` -> devuelve `{{"status": "ok"}}` (200 OK). - `POST /api/v1/empleados` (status_code=201, 
response_model=EmpleadoResponse): 
Parámetros: `payload: EmpleadoCreate`, `x_user_id: Optional[int] = 
Header(None, alias="X-User-Id")`, `db: Session = Depends(get_db)`. 
Si `db.query(Empleado).count() > 0`: si `x_user_id is None` -> 403; 
busca `admin = db.query(Empleado).filter(Empleado.id == x_user_id).first()`; 
si no existe -> 404; si `admin.rol != "ADMIN_RRHH"` -> 
`HTTPException(status_code=403, detail="Only ADMIN_RRHH can create 
employees")`. 
Crea y retorna el `Empleado`. - `GET /api/v1/vacaciones/saldo/{{empleado_id}}` 
(response_model=SaldoResponse): 
Busca empleado por `empleado_id` (si no existe -> 404). Usa 
`calcular_saldo` y retorna `SaldoResponse`. - `POST /api/v1/vacaciones/solicitar` (status_code=201, 
response_model=SolicitudResponse): 
     Busca empleado por `payload.empleado_id` (si no existe -> 404). Usa 
`calcular_saldo`: si `payload.dias_solicitados > saldo_disponible` -> 
`HTTPException(status_code=400, detail="Insufficient vacation balance")`. 
     Crea `SolicitudVacaciones` con `estado="PENDING"` y retorna. 
   - `POST /api/v1/vacaciones/{{solicitud_id}}/revisar` (status_code=200, 
response_model=SolicitudResponse): 
     Parámetros: `solicitud_id: int`, `payload: RevisionRequest`, 
`x_user_id: int = Header(..., alias="X-User-Id")`, `db: Session = 
Depends(get_db)`. 
     Busca solicitud (404 si no existe) y busca manager con `x_user_id` (404 
si no existe). 
     Busca empleado dueño de la solicitud (`solicitud.empleado_id`). 
     Si `manager.rol != "MANAGER"` o `empleado.manager_id != x_user_id` -> 
`HTTPException(status_code=403, detail="Unauthorized: Not the direct 
manager")`. 
     Si `solicitud.estado != "PENDING"` -> `HTTPException(status_code=400, 
detail="Request already processed")`. 
     Si `payload.accion == "APPROVE"` -> `solicitud.estado = "APPROVED"`; si 
`payload.accion == "REJECT"` -> `solicitud.estado = "REJECTED"`; otro valor -> 400. 
     Asigna `solicitud.revisado_por_id = x_user_id`, haz `db.commit()`, 
`db.refresh(solicitud)` y retorna. 
 
REGLA ESTRICTA: Devuelve ÚNICAMENTE el código Python puro, sin explicaciones 
antes ni después.""", 
    expected_output="Código Python puro del archivo app/main.py.", 
    agent=backend_developer, 
    output_file=ruta_main, 
) 
 
print("\n" + "=" * 70) 
print("   EJECUTANDO AGENTE 3: BACKEND DEVELOPER (PASO 2/2: app/main.py)") 
print("=" * 70) 
Crew(agents=[backend_developer], tasks=[tarea_main], verbose=True).kickoff() 
 
# 6. Verificación Determinista (Checkpoint de Sintaxis e Importación) 
print("\n" + "=" * 70) 
print("   VERIFICACIÓN DETERMINISTA DEL CÓDIGO GENERADO") 
print("=" * 70) 
 
archivos_esperados = ["app/__init__.py", "app/models.py", "app/main.py", 
"requirements.txt"] 
errores_sintaxis = 0 
 
for rel in archivos_esperados: 
    ruta = base_dir / rel 
    if not ruta.exists(): 
        print(f"  [FALTA] {rel}") 
        errores_sintaxis += 1 
        continue 
    if rel.endswith(".py"): 
        try: 
            compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec") 
            print(f"  [OK Sintaxis] {rel} ({ruta.stat().st_size} bytes)") 
        except SyntaxError as e: 
            errores_sintaxis += 1 
            print(f"  [ERROR Sintaxis] {rel}: {e}") 
    else: 
        print(f"  [OK Archivo] {rel}") 
 
if errores_sintaxis == 0: 
    r = subprocess.run( 
        [
            sys.executable,
            "-c",
            "from app.main import app; print('--> [OK] FastAPI app importada exitosamente.')",
        ],
        cwd=str(base_dir), 
        capture_output=True, 
        text=True, 
    ) 
    if r.returncode == 0: 
        print(r.stdout.strip()) 
    else: 
        print(f"--> [!] Error al importar app.main:\n{r.stderr}")