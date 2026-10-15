# ============================================================
# PRUEBA DE FALLO CONTROLADO
# ============================================================

import uuid

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langsmith import tracing_context

import main

# ============================================================
# 1. SIMULAMOS EL FALLO DE UNA HERRAMIENTA
# ============================================================

#Guardamos temporalmente la función original de la herramienta
herramienta_original = main.consultar_paquete

def simular_error(nombre: str):
    """
    Simula que PyPI no está disponible.

    No realiza ninguna consulta real:
    provoca un error para comprobar las trazas.
    """
    raise ConnectionError("FALLO SIMULADO: PyPI no disponible")

#Sustituimos temporalmente la función interna de la herramienta
main.consultar_paquete = simular_error

# ============================================================
# 2. EJECUTAMOS UNA CONSULTA DE PRUEBA
# ============================================================

conversation_id = f"fallo-{uuid.uuid4().hex[:8]}"

config: RunnableConfig = {
    "configurable": {
        "thread_id": conversation_id
    },
    "metadata": {
        "query_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "model": main.MODEL_ID,
        "prompt_version": main.PROMPT_ID,
        "tipo_ejecucion": "prueba_fallo"
    },
    "tags": ["proyecto6", "prueba_fallo"],
    "callbacks": [main.langfuse_handler]
}

try:
    print("\nSIMULANDO FALLO DE PYPI...\n")

    with tracing_context(
        enabled=True,
        client=main.langsmith_client
    ):
        resultado = main.app.invoke(
            {
                "mensajes": [
                    HumanMessage(
                        content="Consulta en PyPI la versión actual de FastAPI."
                    )
                ],
                "llamadas_tools": 0,
                "errores": []
            },
            config=config
        )

    print("\nRespuesta:", resultado["mensajes"][-1].content)
    print("Errores registrados:", resultado["errores"])

except Exception as error:
    # Si el grafo no captura el fallo, lo mostramos igualmente.
    print(f"\nError capturado: {type(error).__name__}: {error}")

finally:
    # Restauramos la herramienta original.
    main.consultar_paquete.func = herramienta_original

    # Enviamos las trazas pendientes antes de finalizar.
    main.langfuse.flush()

    print("\nPrueba finalizada. Herramienta restaurada.")