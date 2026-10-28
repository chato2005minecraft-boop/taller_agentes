import os 
from dotenv import load_dotenv 
from mini_crew import LLM 
load_dotenv() 
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")
print(f"--> Probando conexión con Gemini ({model_name})...")
 
try: 
    llm = LLM(model=model_name, api_key=api_key, temperature=0.2) 
    respuesta = llm.client.models.generate_content(
        model=llm.model,
        contents="Responde en una sola frase: ¿Qué es un agente de software?",
        config={"temperature": 0.2, "max_output_tokens": 100},
    )
    print("\n[OK] Conexión exitosa:") 
    print(f"Respuesta del modelo: {respuesta.text}")
except Exception as e: 
    print(f"\n[ERROR] Falla al conectar: {e}")