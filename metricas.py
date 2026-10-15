
# ============================================================
# PROYECTO 6 - CONSULTA DE MÉTRICAS EN LANGSMITH
# ============================================================

import os
from dotenv import load_dotenv
from langsmith import Client

# Cargamos la configuración del proyecto.
load_dotenv()

# Conectamos con LangSmith.
cliente = Client()

# Recuperamos el nombre del proyecto desde .env.
proyecto = os.getenv("LANGSMITH_PROJECT")

print("\nCONSULTANDO EVALUACIONES EN LANGSMITH...\n")

# Recuperamos las ejecuciones principales del agente.
ejecuciones = cliente.list_runs(
    project_name=proyecto,
    is_root=True,
    filter='has(tags, "evaluacion")'
)

# Mostramos las ejecuciones encontradas.
total = 0

for ejecucion in ejecuciones:
    total += 1

    # Recuperamos los metadatos registrados.
    metadata = (ejecucion.extra or {}).get("metadata", {})

    print(
        f"{total}. "
        f"Prompt: {metadata.get('prompt_version', 'N/D')} | "
        f"Tokens: {ejecucion.total_tokens} | "
        f"Coste: {ejecucion.total_cost}"
    )

print(f"\nTotal de ejecuciones recuperadas: {total}")
