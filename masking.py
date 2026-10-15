import re
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

# Patrón para reconocer direcciones de correo electrónico
EMAIL_REGEX = (
    r"\b[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

def ocultar_datos(texto):
    """
    Sustituye direcciones de correo por [EMAIL_OCULTO]
    """
    return re.sub(EMAIL_REGEX, "[EMAIL_OCULTO]", texto)


def anonimizar_langsmith(datos):
    """
    Recorre recursivamente los datos de una traza de LangSmith
    y sustituye los correos electrónicos por [EMAIL_OCULTO].

    Permite procesar textos, diccionarios, listas y tuplas
    sin modificar los demás tipos de datos.
    """

    # Si recibimos una cadena de texto, aplicamos nuestra función
    # de masking para sustituir los correos electrónicos.
    if isinstance(datos, str):
        return ocultar_datos(datos)

    # Si recibimos un diccionario, recorremos sus claves y valores.
    # Conservamos las claves y aplicamos la función a cada valor.
    if isinstance(datos, dict):
        return {
            clave: anonimizar_langsmith(valor)
            for clave, valor in datos.items()
        }

    # Si recibimos una lista, recorremos todos sus elementos.
    # La función se ejecuta de nuevo para cada elemento.
    if isinstance(datos, list):
        return [
            anonimizar_langsmith(elemento)
            for elemento in datos
        ]

    # Si recibimos una tupla, procesamos sus elementos igual que
    # en una lista, pero conservamos el tipo de dato original.
    if isinstance(datos, tuple):
        return tuple(
            anonimizar_langsmith(elemento)
            for elemento in datos
        )

    # Si el dato es de otro tipo (número, booleano, None, etc.),
    # lo devolvemos sin modificar.
    return datos


def mask_otel_spans(*, params: MaskOtelSpansParams):
    """
    Oculta correos electrónicos en los atributos de las trazas antes de exportarlas a Langfuse
    """

    patches = {} #Creamos un diccionario vacío donde almacenaremos las modificaciones que queremos aplicar.

    #Recorremos todos los spans del lote de exportación. Cada span tiene un identificador único que utilizaremos para indicar a Langfuse cuál queremos modificar.
    for identificador, span in params.spans.items(): 
        atributos_modificados = {}

        #Recorremos los atributos de cada span. Por ejemplo, un atributo podría contener el texto de una pregunta del usuario.
        for clave, valor in span.attributes.items():
            #Comprueba si el atributo contiene una cadena de texto. Si es así, aplicamos nuestra función ocultar_datos().
            if isinstance(valor, str):
                valor_protegido = ocultar_datos(valor)
                #También comprobamos si contiene una lista o tupla, para proteger los elementos de texto que pueda incluir.
            elif isinstance(valor, (list, tuple)):
                valor_protegido = [
                    ocultar_datos(elemento)
                    if isinstance(elemento, str) else elemento
                    for elemento in valor
        ]
            else:
                continue

            #Solo almacenamos una modificación cuando realmente hemos encontrado algo que sustituir.
            if valor_protegido != valor:
                atributos_modificados[clave] = valor_protegido

        #Creamos un parche si hay datos que proteger
        if atributos_modificados:
            patches[identificador] = OtelSpanPatch(
                set_attributes = atributos_modificados #Creamos el parche que indica a Langfuse qué atributos debe sustituir.
            )

    #Devolvemos los parches. Si no hemos encontrado nada que modificar, devolvemos None, indicando que el lote puede mantenerse como estaba.
    return MaskOtelSpansResult(span_patches=patches) if patches else None



#Prueba local: solo se ejecuta al abrir este archivo directamente
if __name__ == "__main__":
    mensaje = "Mi correo es prueba@example.com"
    print("Original:", mensaje)
    print("Protegido:", ocultar_datos(mensaje))