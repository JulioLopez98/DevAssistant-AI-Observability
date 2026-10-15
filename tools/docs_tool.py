import requests
from langchain_core.tools import tool
import re
import html

# ============================================================
# HERRAMIENTA: BUSCAR DOCUMENTACIÓN TÉCNICA
# ============================================================

@tool
def buscar_documentacion(consulta: str) -> dict:
    """
    Busca preguntas tecnicas relacionadas con programacion
    utilizando la API publica de Stack Overflow
    Args:
    consulta: Pregunta o concepto técnico que queremos buscar.

    Returns:
        Diccionario con los resultados encontrados o un error.
    """

    #1. VALIDAR CONSULTA
    consulta = consulta.strip() #strip elimina espacios al principio y al final

    if not consulta:
        return{"error": "La consulta no puede estar vacía."}

    #2. PREPARAR LA PETICION A LA API
    url = "https://api.stackexchange.com/2.3/search/advanced"

    parametros = {
        "q": consulta,            # Texto que queremos buscar.
        "site": "stackoverflow",  # Buscamos únicamente en Stack Overflow.
        "sort": "relevance",      # Ordenamos por relevancia.
        "order": "desc",          # Orden descendente.
        "pagesize": 3,             # Recuperamos como máximo 3 resultados.
        "filter" : "withbody"  # Incluimos el cuerpo de la pregunta en la respuesta.
    }

    #3. CONSULTAR A LA API
    try:
        #GET envia una peticion HTTP a la API
        respuesta = requests.get(url, params=parametros, timeout=10)

        #Genera una excepcion si la respuesta HTTP indica error
        respuesta.raise_for_status()

        #json convierte la respuesta JSON en datos Python
        datos = respuesta.json()

        #4. EXTRAER LOS RESULTADOS
        resultados = []

        #get("items", []) devuelve la lista de resultados o una lista vacia si no hay resultados
        for item in datos.get("items", []):

            contenido = item.get("body", "") # Recuperamos el contenido de la pregunta (cuerpo HTML)

            contenido = re.sub(r"<[^>]+>", " ", contenido)  # Elimina etiquetas HTML

            contenido = html.unescape(contenido)  # Decodifica entidades HTML
            contenido = " ".join(contenido.split())  # Elimina espacios en blanco extra

            #Guardamos los datos y un fragmento de la regunta
            resultados.append({
                "titulo": item.get("title"),
                "enlace": item.get("link"),
                "contenido" : contenido[:800],
                "respuestas": item.get("answer_count", 0),
                "resuelta": item.get("is_answered", False)
            })

        if not resultados:
            return{
                "mensaje": "No se encontraron resultados para la consulta.",
                "resultados": []
            }

        #5. DEVOLVER LA INFORMACION
        return{
            "consulta": consulta,
            "fuente": "Stack Overflow",
            "resultados": resultados
        }

    #6. CONTROLAR ERRORES
    except requests.RequestException:
        return {"error": "No se ha podido conectar con Stack Overflow."}
    except ValueError:
        return {"error": "Respuesta de Stack Overflow no válida."}


if __name__ == "__main__":

    resultado = buscar_documentacion.invoke({
        "consulta": "LangGraph StateGraph Python"
    })

    print("\n" + "=" * 50)
    print("       BÚSQUEDA DE DOCUMENTACIÓN")
    print("=" * 50)

    for clave, valor in resultado.items():
        print(f"{clave.upper()}: {valor}")

    print("=" * 50)
