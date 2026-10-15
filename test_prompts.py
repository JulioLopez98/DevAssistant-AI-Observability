from dotenv import load_dotenv
from langfuse import get_client
from langsmith import Client


# 1. Cargar las variables de entorno
load_dotenv()

# 2. Conectar con Langfuse
langfuse = get_client()

# 3. Recuperar las dos versiones del prompt
prompt_v1 = langfuse.get_prompt(
    "devassistant-system",
    version=1
)

prompt_v2 = langfuse.get_prompt(
    "devassistant-system",
    version=2
)

# 4. Mostrar los resultados
print("\n========== PROMPT V1 ==========")
print(prompt_v1.prompt)

print("\n========== PROMPT V2 ==========")
print(prompt_v2.prompt)

print("\n¡Ambas versiones recuperadas correctamente!")

#5. Recuperamos prompts desde langsmith
client_langsmith = Client()

COMMIT_V1 = "5d4b482b"
COMMIT_V2 = "0b6de0a2"

#Recuperamos las dos versiones
smith_v1 = client_langsmith.pull_prompt(
    f"devassistant-system:{COMMIT_V1}"
)

smith_v2 = client_langsmith.pull_prompt(
    f"devassistant-system:{COMMIT_V2}"
)

# Mostramos las instrucciones del mensaje System
print("\n========== LANGSMITH V1 ==========")
print(smith_v1.messages[0].prompt.template)

print("\n========== LANGSMITH V2 ==========")
print(smith_v2.messages[0].prompt.template)

print("\n¡Prompts de LangSmith recuperados correctamente!")