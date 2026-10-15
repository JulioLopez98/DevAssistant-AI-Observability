import uuid
import time
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langsmith import tracing_context

# Este archivo contiene las preguntas utilizadas para
# comparar las versiones V1 y V2 de DevAssistant AI.
# Cada caso contiene:
# - id: identificador único de la prueba.
# - pregunta: consulta que recibirá DevAssistant AI.
# - esperado: criterios que debe cumplir una respuesta correcta.
# Los criterios se definen antes de ejecutar la comparación
# para evaluar ambas versiones de forma objetiva.

PREGUNTAS_EVALUACION = [
    {
        "id": 1,
        "pregunta": "¿Qué es LangGraph y para qué sirve?",
        "esperado": "Explicar que LangGraph permite construir agentes y flujos de IA con estado mediante grafos."
    },
    {
        "id": 2,
        "pregunta": "Consulta en PyPI la versión actual de FastAPI.",
        "esperado": "Utilizar consultar_paquete y devolver la versión obtenida de PyPI sin inventar datos."
    },
    {
        "id": 3,
        "pregunta": "Consulta en PyPI la versión actual de LangChain.",
        "esperado": "Utilizar consultar_paquete y mostrar la versión real del paquete LangChain."
    },
    {
        "id": 4,
        "pregunta": "Busca documentación sobre cómo crear un StateGraph con LangGraph.",
        "esperado": "Utilizar buscar_documentacion y aportar información o enlaces verificables. Si no encuentra resultados, indicarlo."
    },
    {
        "id": 5,
        "pregunta": "¿Qué diferencias hay entre LangChain y LangGraph?",
        "esperado": "Distinguir LangChain como framework de componentes y LangGraph como framework de orquestación de agentes con estado."
    },
    {
        "id": 6,
        "pregunta": "Consulta en PyPI las versiones de FastAPI y LangGraph.",
        "esperado": "Consultar ambos paquetes y devolver sus versiones correctamente, sin omitir ninguno."
    },
    {
        "id": 7,
        "pregunta": "¿Qué es un grafo de estados? Explícalo con un ejemplo sencillo.",
        "esperado": "Definir nodos, estados y transiciones, incluyendo un ejemplo comprensible."
    },
    {
        "id": 8,
        "pregunta": "¿Qué versión de Python necesita FastAPI actualmente?",
        "esperado": "Consultar los requisitos del paquete y comunicar la versión mínima de Python indicada por PyPI."
    },
    {
        "id": 9,
        "pregunta": "¿Qué ocurre si una herramienta no devuelve resultados?",
        "esperado": "Explicar que el agente debe reconocer la ausencia de resultados y evitar inventar información."
    },
    {
        "id": 10,
        "pregunta": "¿Qué ventajas tiene utilizar herramientas en un agente de IA?",
        "esperado": "Explicar ventajas como consultar datos externos, obtener información actualizada y realizar acciones."
    }
]

# ============================================================
# IMPORTACIÓN DEL AGENTE
# ============================================================

# Reutilizamos el agente y los identificadores de su configuración.
from main import (
    app,
    MODEL_ID,
    PROMPT_ID,
    langfuse_handler,
    langsmith_client
)

# ============================================================
# EJECUCIÓN DE UNA PREGUNTA DE EVALUACIÓN
# ============================================================
def ejecutar_pregunta(pregunta, caso_id):
    """
    Ejecuta una pregunta utilizando nuestro agente DevAssistant AI.

    Cada ejecución utiliza un identificador de conversación
    diferente para evitar que las respuestas anteriores
    influyan en los resultados de la evaluación.
    """

    #Creamos un identificador único para esta conversaion
    conversation_id = f"evaluacion-{uuid.uuid4().hex[:8]}"

    #Creamos un identificador unico para esta consulta
    query_id = str(uuid.uuid4())

    #Creamos la configuracion del grafo con ese identificador
    config: RunnableConfig = {
        "configurable": {
            "thread_id": conversation_id
        },
        #Informacion que permite identificar y comparar las ejecuciones registradas en LangSmith y LangFuse
        "metadata":{
            "query_id": query_id,
            "caso_id": caso_id,
            "conversation_id": conversation_id,
            "model": MODEL_ID,
            "prompt_version": PROMPT_ID,
            "tipo_ejecucion": "evaluacion"
        },

        #Etiqueta para distinguir las pruebas del uso normal
        "tags": ["proyecto6", "evaluacion"],
        # Enviamos las trazas a Langfuse.
        "callbacks": [langfuse_handler]
    }

    #Convertimos la pregunta a un mensaje de usuario
    mensaje = HumanMessage(content=pregunta)

    #Guardar el instante anterior a ejecutar el agente
    inicio = time.perf_counter()

    #Activamos el tracing de LangSmith utilizando el cliente que configuramos previamente
    with tracing_context(
        enabled=True,
        client=langsmith_client
    ):

        #Ejecutamos el agente con un historial independiente
        estado = app.invoke(
            {
                "mensajes": [mensaje],
                "llamadas_tools": 0,
                "errores": []
            },
            config=config
        )

    #Calcular cuanto ha tardado en completarse la ejecucion
    latencia = time.perf_counter() - inicio

    #Recuperamos la ultima respuesta del asistente y devolvemos unicamente el texto de la respuesta
    respuesta = estado["mensajes"][-1]
    return {
        "respuesta": respuesta.content,
        "latencia": round(latencia, 2),
        "llamadas_tools": estado["llamadas_tools"],
        "errores": estado["errores"]
    }

# Ejecutamos esta sección únicamente cuando abrimos
# evaluacion.py directamente, no cuando lo importamos.
if __name__ == "__main__":

    # Mostramos todas las preguntas para comprobar
    # que el conjunto de evaluación está bien preparado.
    print("\nPREGUNTAS DE EVALUACIÓN\n")

    for caso in PREGUNTAS_EVALUACION:
        print(f"{caso['id']}. {caso['pregunta']}")

    # Mostramos el número total de preguntas.
    print(f"\nTotal: {len(PREGUNTAS_EVALUACION)} preguntas")

    #Recorremos las diez preguntas y se ejecutan de manera independiente
    for caso in PREGUNTAS_EVALUACION:
        numero = caso["id"]
        pregunta = caso["pregunta"]

        #Mostramos que pureba estamos ejecutando
        print(f"\n{'=' * 55}")
        print(f"PRUEBA {numero}/10")
        print(f"{'=' * 55}")

        #Ejecuamos la pregunta
        resultado = ejecutar_pregunta(pregunta, numero)

        # Mostramos la respuesta generada por el agente.
        print(f"\nPregunta: {pregunta}")
        print(f"Respuesta: {resultado['respuesta']}")

        # Mostramos las métricas básicas de ejecución.
        print(f"Latencia: {resultado['latencia']} segundos")
        print(f"Herramientas utilizadas: {resultado['llamadas_tools']}")
        print(f"Errores: {resultado['errores']}")

    # Indicamos que todas las preguntas han terminado.
    print(f"\n{'=' * 55}")
    print("EVALUACIÓN FINALIZADA")
    print(f"Prompt evaluado: {PROMPT_ID}")
    print(f"Total de preguntas: {len(PREGUNTAS_EVALUACION)}")
    print(f"{'=' * 55}")


