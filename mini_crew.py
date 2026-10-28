# mini_crew.py — Motor Agéntico Puro para Gemini
 
import os 
import re 
import subprocess 
import time 
from pathlib import Path 
 
from google import genai
from google.genai import errors, types
from dotenv import load_dotenv 
 
load_dotenv() 
 
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./generated_project")) 
 
def set_workspace_dir(path: str): 
    """Cambia el directorio base donde los agentes escriben y leen 
código.""" 
    global WORKSPACE_DIR 
    WORKSPACE_DIR = Path(path) 
 
def limpiar_bloques_codigo(texto: str, extension: str = "") -> str: 
    """Elimina envoltorios Markdown (```python ... ```) si el modelo los 
incluye al escribir código.""" 
    texto = texto.strip() 
    patron = r"^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$" 
    coincidencia = re.match(patron, texto) 
    if coincidencia: 
        return coincidencia.group(1).strip() + "\n" 
    # Si solo empieza con ```python y termina con ``` 
    if texto.startswith("```") and texto.endswith("```"): 
        lineas = texto.splitlines() 
        if len(lineas) >= 2: 
            return "\n".join(lineas[1:-1]).strip() + "\n" 
    return texto 
 
class LLM: 
    def __init__(self, model: str = None, api_key: str = None, temperature: 
float = 0.2, 
                 max_tokens: int = 4096): 
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Configura GEMINI_API_KEY en el archivo .env.")
        self.model = model or os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")
        self.temperature = temperature 
        self.max_tokens = max_tokens 
        self.client = genai.Client(api_key=self.api_key)
 
# ----------------------------------------------------------------------------- 
# Sistema de Herramientas Deterministas (Tools) 
# ----------------------------------------------------------------------------- 
class Tool: 
    def __init__(self, name: str, description: str, parameters: dict, func): 
        self.name = name 
        self.description = description 
        self.parameters = parameters 
        self.func = func 
 
    def to_gemini_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.parameters,
        )
 
    def run(self, **kwargs) -> str: 
        return str(self.func(**kwargs)) 
 
def tool(name: str, description: str, parameters: dict): 
    def decorador(func): 
        return Tool(name=name, description=description, 
parameters=parameters, func=func) 
    return decorador 
 
@tool( 
    name="write_project_file", 
    description="Crea o sobrescribe un archivo completo dentro del proyecto. Pasa el código limpio sin bloques markdown (```).", 
    parameters={ 
        "type": "object", 
        "properties": { 
            "relative_path": {"type": "string", "description": "Ruta relativa, ej: app/main.py"}, 
            "content": {"type": "string", "description": "Contenido completo del archivo"}, 
        }, 
        "required": ["relative_path", "content"], 
    }, 
) 
def write_project_file(relative_path: str, content: str) -> str: 
    base = WORKSPACE_DIR.resolve() 
    destino = (base / relative_path).resolve() 
    if destino != base and base not in destino.parents: 
        return f"ERROR DE SEGURIDAD: Ruta fuera del proyecto ({relative_path})." 
     
    destino.parent.mkdir(parents=True, exist_ok=True) 
    # Limpiar bloques ``` si es un archivo de código (no Markdown) 
    if not relative_path.endswith(".md"): 
        content = limpiar_bloques_codigo(content) 
         
    destino.write_text(content, encoding="utf-8") 
    return f"OK: Archivo '{relative_path}' guardado exitosamente ({len(content)} caracteres)." 
 
@tool( 
    name="read_project_file", 
    description="Lee el contenido de un archivo existente dentro del proyecto.", 
    parameters={ 
        "type": "object", 
        "properties": { 
            "relative_path": {"type": "string", "description": "Ruta relativa, ej: app/main.py"}, 
        }, 
        "required": ["relative_path"], 
    }, 
) 
def read_project_file(relative_path: str) -> str: 
    base = WORKSPACE_DIR.resolve() 
    destino = (base / relative_path).resolve() 
    if destino != base and base not in destino.parents: 
        return "ERROR DE SEGURIDAD: Ruta fuera del proyecto." 
    if not destino.exists(): 
        return f"ERROR: El archivo '{relative_path}' no existe." 
    return destino.read_text(encoding="utf-8") 
 
@tool( 
    name="run_pytest_suite", 
    description="Ejecuta 'pytest -v' dentro del directorio del proyecto y devuelve el resultado.", 
    parameters={ 
        "type": "object", 
        "properties": { 
            "test_target": {"type": "string", "description": "Ruta de tests, por defecto 'tests/'"}, 
        }, 
        "required": [], 
    }, 
) 
def run_pytest_suite(test_target: str = "tests/") -> str: 
    try: 
        import sys 
        resultado = subprocess.run( 
            [sys.executable, "-m", "pytest", "-v", test_target], 
            cwd=str(WORKSPACE_DIR.resolve()), 
            capture_output=True, text=True, timeout=45, 
        ) 
        estado = "PASSED" if resultado.returncode == 0 else "FAILED" 
        salida = (resultado.stdout + "\n" + resultado.stderr).strip() 
        # Acotar salida a 2500 caracteres para no saturar tokens en caso de trazas largas.
        if len(salida) > 2500: 
            salida = salida[:2500] + "\n...[salida truncada]..." 
        return f"ESTADO: {estado} (código {resultado.returncode})\n{salida}" 
    except subprocess.TimeoutExpired: 
        return "ERROR: pytest superó el límite de 45 segundos." 
    except Exception as e: 
        return f"ERROR al ejecutar pytest: {type(e).__name__}: {e}" 
 
# ----------------------------------------------------------------------------- 
# Clases Principales: Agent, Task, Crew, Process 
# ----------------------------------------------------------------------------- 
class Agent: 
    def __init__(self, role: str, goal: str, backstory: str, llm: LLM = 
None, verbose: bool = True, 
                 allow_delegation: bool = False, tools: list = None, 
max_tool_iterations: int = 8): 
        self.role = role 
        self.goal = goal 
        self.backstory = backstory 
        self.llm = llm or LLM() 
        self.verbose = verbose 
        self.tools = tools or [] 
        self.max_tool_iterations = max_tool_iterations 
 
    def _llamar_modelo(self, contents: list, system_prompt: str):
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.llm.temperature,
            max_output_tokens=self.llm.max_tokens,
            tools=(
                [types.Tool(function_declarations=[
                    tool.to_gemini_declaration() for tool in self.tools
                ])]
                if self.tools else None
            ),
        )

        max_intentos = 5
        for intento in range(1, max_intentos + 1):
            try:
                response = self.llm.client.models.generate_content(
                    model=self.llm.model,
                    contents=contents,
                    config=config,
                )
                if not response.candidates:
                    raise RuntimeError("Gemini no devolvió una respuesta candidata.")
                candidate = response.candidates[0]
                if candidate.content is None:
                    raise RuntimeError(
                        f"Gemini no devolvió contenido (motivo: {candidate.finish_reason})."
                    )
                if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
                    print(
                        f"\n[!] ADVERTENCIA [{self.role}]: La respuesta alcanzó "
                        f"max_tokens={self.llm.max_tokens}."
                    )
                return response
            except errors.APIError as error:
                if error.code in (429, 503) and intento < max_intentos:
                    espera = min(5 * (2 ** (intento - 1)), 30)
                    if error.code == 429:
                        mensaje_error = "Límite de solicitudes"
                    else:
                        mensaje_error = "Gemini no disponible temporalmente"
                    print(
                        f"    [!] {mensaje_error} ({error.code}). "
                        f"Reintentando en {espera}s ({intento}/{max_intentos - 1})..."
                    )
                    time.sleep(espera)
                    continue
                raise

    def _ejecutar_tool(self, nombre: str, argumentos: dict) -> str:
        herramienta = next((t for t in self.tools if t.name == nombre), 
None) 
        if herramienta is None: 
            return f"ERROR: La herramienta '{nombre}' no está disponible." 
        try: 
            return herramienta.run(**argumentos)
        except Exception as e: 
            return f"ERROR al ejecutar '{nombre}': {type(e).__name__}: {e}" 
 
    def execute_task(self, task_description: str, context: str = "", 
expected_output: str = "") -> str: 
        system_prompt = ( 
            f"ERES: {self.role}\n" 
            f"OBJETIVO: {self.goal}\n" 
            f"CONTEXTO: {self.backstory}\n" 
            "INSTRUCCIÓN: Sé conciso, técnico y directo. No agregues "
            "saludos ni texto de relleno."
        ) 
 
        user_prompt = f"TAREA:\n{task_description}" 
        if expected_output: 
            user_prompt += f"\n\nFORMATO ESPERADO:\n{expected_output}" 
        if context: 
            user_prompt += f"\n\nCONTEXTO PREVIO:\n{context}" 
 
        if self.verbose: 
            print(f"\n[{self.role}] Procesando tarea...") 
 
        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)],
        )]
 
        for _ in range(self.max_tool_iterations): 
            response = self._llamar_modelo(contents, system_prompt)
            model_content = response.candidates[0].content
            function_calls = [
                part.function_call
                for part in (model_content.parts or [])
                if part.function_call is not None
            ]
            if not function_calls:
                respuesta = "".join(
                    part.text or ""
                    for part in (model_content.parts or [])
                    if part.text is not None
                )
                if not respuesta:
                    raise RuntimeError("Gemini respondió sin texto ni llamadas a herramientas.")
                return respuesta

            contents.append(model_content)
            for function_call in function_calls:
                if self.verbose: 
                    print(f"    [Tool] Invocando '{function_call.name}'...")
                resultado = self._ejecutar_tool(
                    function_call.name,
                    function_call.args or {},
                )
                if self.verbose: 
                    print(f"    [Tool] Resultado: {resultado[:180]}") 
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": resultado},
                    )],
                ))
 
        return "Tarea finalizada tras ejecutar las herramientas." 
 
class Task: 
    def __init__(self, description: str, expected_output: str, agent: Agent, 
output_file: str = None): 
        self.description = description 
        self.expected_output = expected_output 
        self.agent = agent 
        self.output_file = output_file 
        self.output = None 
 
class Crew: 
    def __init__(self, agents: list, tasks: list, process=None, verbose: 
bool = True): 
        self.agents = agents 
        self.tasks = tasks 
        self.verbose = verbose 
 
    def kickoff(self) -> str: 
        accumulated_context = "" 
        last_output = "" 
 
        for idx, task in enumerate(self.tasks, 1): 
            if self.verbose: 
                print(
                    f"\n--> Ejecutando Tarea {idx}/{len(self.tasks)} | "
                    f"Agente: {task.agent.role}"
                )
 
            output = task.agent.execute_task( 
                task.description, 
                context=accumulated_context, 
                expected_output=task.expected_output, 
            ) 
            task.output = output 
            last_output = output 
            accumulated_context += (
                f"\n--- Salida de {task.agent.role} ---\n{output}\n"
            )
 
            if task.output_file: 
                contenido_guardar = output 
                if not task.output_file.endswith(".md"): 
                    contenido_guardar = limpiar_bloques_codigo(output) 
                with open(task.output_file, "w", encoding="utf-8") as f: 
                    f.write(contenido_guardar) 
                if self.verbose: 
                    print(f"    [+] Entregable guardado en: {task.output_file}") 
 
        return last_output 
 
class Process: 
    sequential = "sequential"