import os 
from dotenv import load_dotenv 
from mini_crew import Agent, Task, Crew, Process, LLM 
load_dotenv() 
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")
llm = LLM(model=model_name, api_key=api_key, temperature=0.2, 
max_tokens=2000) 
product_owner = Agent( 
role="Senior IT Product Owner", 
goal="Redactar un PRD ultra-conciso y sin ambigüedades para TalentCore API.",
    backstory=( 
        "Especialista en ingeniería de requerimientos ágiles. Escribes "
        "especificaciones directas al grano, sin introducciones ni texto "
        "de relleno, optimizadas para que arquitectos y desarrolladores "
        "las implementen sin dudas."
    ), 
    verbose=True, 
    llm=llm, 
) 
 
tarea_prd = Task( 
    description="""Analiza la necesidad de RRHH para 'TalentCore API': 
'Necesitamos un microservicio para registrar empleados, consultar su saldo 
de vacaciones según sus años de antigüedad y solicitar días libres. Su jefe 
directo (MANAGER) debe aprobar o rechazar la solicitud. Nadie puede pedir 
más días de su saldo disponible.' 
 
Genera el documento PRD con estas 4 secciones exactas: 
1. ROLES DEL SISTEMA: 
   - EMPLEADO: Consulta su saldo y solicita vacaciones para sí mismo. 
   - MANAGER: Aprueba o rechaza solicitudes ÚNICAMENTE de sus subordinados 
directos (donde empleado.manager_id == manager.id). 
   - ADMIN_RRHH: Crea empleados en el sistema. 
2. REGLA DE SALDO DE VACACIONES: 
   - Fórmula según años de antigüedad (anios_antiguedad >= 1): dias_totales 
= min(12 + 2 * (anios_antiguedad - 1), 20). Si anios_antiguedad < 1, le 
corresponden 12 días. 
   - Saldo disponible = dias_totales - suma(dias_solicitados en estado 
APPROVED). 
3. MÁQUINA DE ESTADOS DE SOLICITUD: 
   - Estados válidos: PENDING (inicial al crear), APPROVED (descuenta 
saldo), REJECTED (no descuenta saldo). 
   - Solo se pueden revisar solicitudes que estén en estado PENDING. 
4. CRITERIOS DE ACEPTACIÓN (Gherkin compacto): 
   - AC-01: Solicitud válida con saldo suficiente -> HTTP 201 Created, 
estado PENDING. 
   - AC-02: Solicitud rechazada por saldo insuficiente -> HTTP 400 Bad 
Request, detail: "Insufficient vacation balance". 
   - AC-03: Manager intenta revisar solicitud de un empleado que NO es su 
subordinado directo -> HTTP 403 Forbidden, detail: "Unauthorized: Not the 
direct manager".""", 
    expected_output=( 
        "Documento Markdown compacto (máximo 350 palabras) con las 4 "
        "secciones numeradas. PROHIBIDO incluir saludos, despedidas o notas "
        "adicionales fuera de las 4 secciones."
    ), 
    agent=product_owner, 
    output_file="PRD.md", 
) 
 
crew = Crew(agents=[product_owner], tasks=[tarea_prd], 
process=Process.sequential, verbose=True) 
 
if __name__ == "__main__": 
    print("\n" + "=" * 70) 
    print("   EJECUTANDO AGENTE 1: PRODUCT OWNER (PRD COMPACTO)") 
    print("=" * 70) 
    crew.kickoff() 
    print("\n[OK] PRD.md generado exitosamente.") 