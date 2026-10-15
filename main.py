import os
import sqlite3
from typing import TypedDict, cast, Annotated, cast, Any
import uuid

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage
)

from langfuse.langchain import CallbackHandler
from langfuse import get_client
from langsmith import Client
from langfuse import Langfuse
from langsmith import tracing_context
from masking import mask_otel_spans, anonimizar_langsmith

from tools.pypi_tool import consultar_paquete
from tools.docs_tool import buscar_documentacion

# ============================================================
# 0. CONFIGURACIÓN DEL MODELO
# ============================================================

#Cargamos las variables de entorno del archivo .env
load_dotenv()

# Configuramos Langfuse para proteger las trazas
langfuse = Langfuse(mask_otel_spans=mask_otel_spans)

#Conectamos Langfuse para registrar las ejecuciones
langfuse_handler = CallbackHandler()

#Crear un cliente de LangSmith con nuesra funcion para anonimizar
langsmith_client = Client(
    anonymizer=cast(Any, anonimizar_langsmith)
)

#Obtenemos el identificador del modelo
MODEL_ID = os.getenv("MODEL_ID", "gpt-4.1-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

#Creamos la conexcion con el modelo de OpenAI
modelo = ChatOpenAI(
    model = MODEL_ID,
    temperature=0
)

# ============================================================
# 1. HERRAMIENTAS DISPONIBLES
# ============================================================

#Lista de herramientas que podrá utilizar el asistente
herramientas = [consultar_paquete, buscar_documentacion]

#Vinculamos las herramientas al modelo para que pueda utilizarlas
modelo_con_tools = modelo.bind_tools(herramientas)

# ============================================================
# 2. GESTION DE PROMPTS
# ============================================================

#Elegimos la plataforma y version desde el archivo .env
PROMPT_PROVIDER = os.getenv("PROMPT_PROVIDER", "langfuse").lower()
PROMPT_VERSION = int(os.getenv("PROMPT_VERSION", "1"))

#Identificadores de los commits de LangSmith
COMMITS_LANGSMITH = {
    1: "5d4b482b",
    2: "0b6de0a2"
}

#Recuperamos las instrucciones desde la plataforma elegida
if PROMPT_PROVIDER == "langfuse":
    cliente = get_client()
    prompt = cliente.get_prompt(
        "devassistant-system",
        version=PROMPT_VERSION
    )
    INSTRUCCIONES = prompt.prompt
    PROMPT_ID = f"langfuse-v{PROMPT_VERSION}"

elif PROMPT_PROVIDER == "langsmith":
    cliente = Client()
    commit = COMMITS_LANGSMITH[PROMPT_VERSION]
    prompt = cliente.pull_prompt(
        f"devassistant-system:{commit}"
    )
    INSTRUCCIONES = prompt.messages[0].prompt.template
    PROMPT_ID = f"langsmith-{commit}"

else:
    raise ValueError("Proveedor de prompts no reconocido")

print(f"Prompt cargado: {PROMPT_ID}")


# ============================================================
# 3. ESTADO DEL GRAFO
# ============================================================

class Estado(TypedDict):
    #add_messages acumula automaticamente los mensajes
    mensajes: Annotated[list[BaseMessage], add_messages]

    #Numero de herramientas utilizadas
    llamadas_tools: int

    #Errores producidos durante la conversacion
    errores: list[str]

# ============================================================
# 4: NODO: MODELO
# ============================================================

def responder(state: Estado) -> dict:
    """
    Envia el historial al modelo.
    El modelo puede responder o solicitar la ejecucion de una herramienta
    """
    #Recuperamos los mensajes del estado
    mensajes = state["mensajes"]

    #Añadimos las instrucciones antes de la conversacion
    conversacion = [SystemMessage(content=INSTRUCCIONES)] + mensajes

    #Enviamos la conversacion al modelo
    respuesta = modelo_con_tools.invoke(conversacion)

    #Añadimos la respuesta al historial
    return {
        "mensajes": [respuesta]
    }


# ============================================================
# 5. NODO: EJECUTAR HERRAMIENTAS
# ============================================================

def ejecutar_herramientas(state: Estado) -> dict:
    """
    Ejecuta las herramientas que solicita el modelo de IA.

    Comprueba el límite de llamadas, ejecuta las herramientas
    disponibles y devuelve los resultados al estado del grafo.
    """

    # 1. RECUPERAR EL ÚLTIMO MENSAJE

    ultimo_mensaje = state["mensajes"][-1]  # [-1] obtiene el último elemento de una lista.

    # isinstance() comprueba si un objeto pertenece a una clase.
    if not isinstance(ultimo_mensaje, AIMessage):
        return {}  # Diccionario vacío: no actualizamos el estado.


    # 2. PREPARAR LOS DATOS

    resultados = []                         # Lista donde guardaremos los ToolMessage.
    llamadas = state["llamadas_tools"]      # Recuperamos el contador de llamadas.
    errores = state["errores"].copy()       # copy() crea una copia de la lista original.


    # 3. RECORRER LAS HERRAMIENTAS SOLICITADAS

    # for recorre cada solicitud que el modelo ha generado.
    for llamada in ultimo_mensaje.tool_calls:

        nombre = llamada["name"]            # Nombre de la herramienta solicitada.
        argumentos = llamada["args"]        # Parámetros necesarios para ejecutarla.
        identificador = llamada["id"]       # ID único para relacionar solicitud y resultado.

        # Comprobamos si hemos alcanzado el máximo de 2 llamadas.
        if llamadas >= 2:
            resultados.append(             # append() añade un elemento a la lista.
                ToolMessage(
                    content="Límite de herramientas alcanzado.",
                    tool_call_id=identificador
                )
            )

            continue  # Saltamos al siguiente elemento del for sin ejecutar la herramienta.

        print(f"\n🔧 TOOL CALL: {nombre}({argumentos})")


        # 4. BUSCAR Y EJECUTAR LA HERRAMIENTA

        try:  # Intentamos ejecutar este bloque; si falla, pasamos al except.

            herramienta = None  # None indica que todavía no hemos encontrado ninguna.

            # Buscamos la herramienta solicitada entre las disponibles.
            for t in herramientas:

                if t.name == nombre:   # == compara si ambos nombres son iguales.
                    herramienta = t    # Guardamos la herramienta encontrada.
                    break              # Terminamos este for porque ya la tenemos.

            # is None comprueba si la variable sigue sin contener una herramienta.
            if herramienta is None:
                raise ValueError(      # raise provoca una excepción que capturará except.
                    f"Herramienta desconocida: {nombre}"
                )

            # invoke() ejecuta la herramienta con los argumentos indicados.
            resultado = herramienta.invoke(argumentos)

            # Convertimos el resultado a texto y lo guardamos como ToolMessage.
            resultados.append(
                ToolMessage(
                    content=str(resultado),       # str() convierte el resultado a texto.
                    tool_call_id=identificador    # Relaciona el resultado con su solicitud.
                )
            )


        # 5. GESTIONAR LOS ERRORES

        except Exception as error:  # Capturamos una excepción producida dentro del try.

            mensaje_error = str(error)       # Convertimos la excepción a texto.
            errores.append(mensaje_error)    # Guardamos el error en nuestra lista.

            # Informamos al modelo de que la herramienta ha fallado.
            resultados.append(
                ToolMessage(
                    content=f"Error: {mensaje_error}",
                    tool_call_id=identificador
                )
            )

        # += 1 equivale a: llamadas = llamadas + 1
        # Contamos cada intento, tanto si funciona como si falla.
        llamadas += 1


    # 6. DEVOLVER EL ESTADO ACTUALIZADO

    return {
        "mensajes": resultados,       # Nuevos mensajes generados por las herramientas.
        "llamadas_tools": llamadas,   # Número de llamadas intentadas.
        "errores": errores            # Lista de errores actualizada.
    }


# ============================================================
# 6. DECISIÓN CONDICIONAL
# ============================================================

def decidir_ruta(state: Estado) -> str:
    """
    Decide si debemos ejecutar herramientas o finalizar
    """
    ultimo_mensaje = state["mensajes"][-1]

    #Si el modelo solicita herramientas, vamos a tools
    if (
        isinstance(ultimo_mensaje, AIMessage) and ultimo_mensaje.tool_calls
    ):
        return "tools"

    #Si responde normalmente, terminamos
    return "fin"

# ============================================================
# 7. CONSTRUCCIÓN DEL GRAFO
# ============================================================

#Creamos un grafo que utiliza nuestro estado
grafo = StateGraph(Estado)

#Anadimos el nodo que ejecutara la funcion responder
grafo.add_node("responder", responder)
grafo.add_node("tools", ejecutar_herramientas)

#Definimos el recorrido del grafo
grafo.add_edge(START, "responder")

#Decision condicial despues del modelo
grafo.add_conditional_edges(
    "responder",
    decidir_ruta,
    {
        "tools": "tools",
        "fin": END
    }
)

#Despues de ejecutar herramientas, volvemos al modelo
grafo.add_edge("tools", "responder")

#Abrimos la base de datos. Si no existe, SQLite la crea
conexion = sqlite3.connect(
    "conversacion.db",
    check_same_thread=False
)

#Creamos el sistema de memoria utilizando esa conexion
memoria = SqliteSaver(conexion)

#Compilamos el grafo con memoria persistente
app = grafo.compile(checkpointer=memoria)

# ============================================================
# 8. EJECUCIÓN DEL GRAFO
# ============================================================

#Identidicador de esta conversacion
conversation_id = f"devassistant-{uuid.uuid4().hex[:8]}"

if __name__ == "__main__":
    #Identidicador de la conversacion. Si reutilizamos este ID, recuperamos el historial guardado
    config: RunnableConfig = {
        "configurable": {
            "thread_id": conversation_id
        },
        "callbacks": [langfuse_handler],  # Registramos las ejecuciones en Langfuse
    }

    # MOSTRAR LA CONVERSACIÓN
    print("\n" + "=" * 55)
    print("                  DEVASSISTANT AI")
    print("=" * 55)
    print("Tu asistente inteligente para programación.")
    print("Escribe 'salir' para finalizar.\n")

    #Mantenemos el chatbot activo
    while True:

        #Solicitamos una pregunta al usuario
        pregunta = input("👤 TÚ: ").strip()

        #Comprobamos si quiere terminar
        if pregunta.lower() == "salir":
            print("👋 ¡Hasta luego!")
            break

        #Envitamos enviar mensajes vacíos
        if not pregunta:
            print("⚠️ Por favor, escribe una pregunta.")
            continue

        #Creamos el mensaje de usuario
        nuevo_mensaje = HumanMessage(content=pregunta)

        #Identificador unico para cada pregunta
        query_id = str(uuid.uuid4())

        #Metadatos que acompañaran a la ejecucion
        config["metadata"] = {
            "query_id": query_id,
            "conversation_id": conversation_id,
            "model": MODEL_ID,
            "promt_version": PROMPT_ID
        }

        with tracing_context(
            enabled=True,
            client=langsmith_client
        ):

            #Ejecutamos el grafo con el ID de conversacion. LangGraph recupera automaticamente el historial guardado
            estado = cast(
                Estado,
                app.invoke(
                    {
                        "mensajes": [nuevo_mensaje],
                        "llamadas_tools": 0,
                        "errores": []
                    },
                    config=config
                )
            )

            #Recuperamos la ultima respuesta del asistente
            respuesta = estado["mensajes"][-1]

            #Mostramos unicamente el contenido del mensaje
            print(f"🤖 ASISTENTE: {respuesta.content}\n")