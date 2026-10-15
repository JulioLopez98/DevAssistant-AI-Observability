import re
import requests

from langchain_core.tools import tool

# ============================================================
# HERRAMIENTA: CONSULTAR PAQUETE EN PYPI
# ============================================================

@tool
def consultar_paquete(nombre: str) -> dict[str, str | None]:
    """
    Consulta información actualizada de un paquete de Python
    utilizando la API pública de PyPI.

    Args:
        nombre: Nombre del paquete que queremos consultar.

    Returns:
        Diccionario con la información del paquete
        o un mensaje de error.
    """

    # 1. Validar el nombre.

    nombre = nombre.strip()
    #Solo permitimos nombres validos de paquetes Python
    if not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?",
        nombre
    ) or len(nombre) > 100:
        return {"error": "Nombre de paquete no válido."}

    # 2. Consultar PyPI.

    url = f"https://pypi.org/pypi/{nombre}/json"

    try:
        #Realizamos una peticion HTTP con tiempo limite
        respuesta = requests.get(url, timeout=10)

        #Comprobamos si el paqute existe
        if respuesta.status_code == 404:
            return {"error": "El paquete no existe."}

        #Detectamos otros errores HTTP
        respuesta.raise_for_status()
        #Convertimos la respuesta JSON en un diccionario
        datos = respuesta.json()
        #Extraemos la informacion que nos interesa
        info = datos["info"]

        return {
            "nombre": info["name"],
            "version": info["version"],
            "descripcion": info.get("summary", ""),
            "python_requerido": info.get("requires_python")
        }

    # 3. Controlar errores.
    except requests.RequestException:
        return {"error": "No se ha podido conectar con PyPI."}

    except (ValueError, KeyError, TypeError):
        return {"error": "Respuesta de PyPI no válida."}

# ============================================================
# PRUEBA INDIVIDUAL DE LA HERRAMIENTA
# ============================================================
if __name__ == "__main__":
    resultado = consultar_paquete.invoke({
        "nombre": "langgraph"
    })

    print("\n" + "=" * 50)
    print("        CONSULTA DE PAQUETE PYPI")
    print("=" * 50)

    for clave, valor in resultado.items():
        print(f"{clave.upper()}: {valor}")

    print ("=" * 50)
