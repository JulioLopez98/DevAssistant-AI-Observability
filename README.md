# DevAssistant AI — Observabilidad con Langfuse y LangSmith

Proyecto 6 del Máster AI Engineer. Se instrumenta un asistente de programación construido con **LangGraph** para analizar su comportamiento, comparar versiones de prompt y localizar problemas de herramientas y latencia mediante **LangSmith** y **Langfuse**.

## Objetivo

Comprobar, mediante trazas y un conjunto fijo de preguntas, cómo influyen dos versiones del prompt en la calidad de las respuestas, el uso de herramientas, la latencia y el coste estimado. Se incluyen pruebas controladas de fallo, retraso y protección de datos.

## Arquitectura

```text
Usuario
   |
   v
LangGraph (StateGraph + memoria SQLite)
   |
   v
responder (LLM: gpt-4.1-mini, temperatura 0)
   |
   +-- ¿Solicita herramienta? -- No --> Respuesta final
   |
   Sí
   v
ejecutar_herramientas
   |-- consultar_paquete (PyPI)
   `-- buscar_documentacion
   |
   v
responder --> Respuesta final

Observabilidad: LangSmith + Langfuse
Privacidad: anonimización de correos electrónicos en las trazas
```

El estado del grafo mantiene mensajes, número de llamadas a herramientas y errores. La memoria conversacional utiliza `SqliteSaver` y un identificador de conversación (`thread_id`).

## Estructura del proyecto

```text
Proyecto6_Observability/
├── main.py                 # Asistente LangGraph y observabilidad
├── evaluacion.py           # Batería de diez preguntas
├── metricas.py             # Consulta de métricas en LangSmith
├── masking.py              # Anonimización de correos
├── prueba_fallo.py         # Fallo simulado de PyPI
├── prueba_retraso.py       # Retraso artificial de 3 segundos
├── tools/
│   ├── pypi_tool.py        # Consulta de paquetes
│   └── docs_tool.py        # Búsqueda de documentación
├── EjemplosGraficos/       # Capturas del proceso
├── requirements.txt
├── .env.example            # Plantilla de configuración sin credenciales
├── .gitignore              # Archivos excluidos de Git
└── README.md
```

## Componentes y funciones principales

### `main.py` — agente y trazabilidad

- **Configuración del modelo:** lee las variables de entorno, prepara `ChatOpenAI` con `gpt-4.1-mini` y temperatura `0`, y vincula las herramientas mediante `bind_tools`.
- **Carga del prompt:** recupera la versión seleccionada de `devassistant-system` desde LangSmith o Langfuse. Se conserva el identificador de versión en los metadatos de la ejecución.
- **`Estado`:** define la información que circula por el grafo: `mensajes` (historial), `llamadas_tools` (contador) y `errores` (incidencias).
- **`responder(state)`:** envía al modelo el prompt del sistema y el historial. Devuelve una respuesta normal o una solicitud de herramienta.
- **`decidir_ruta(state)`:** inspecciona el último mensaje. Si contiene llamadas a herramientas, dirige el flujo a `ejecutar_herramientas`; en caso contrario, finaliza.
- **`ejecutar_herramientas(state)`:** localiza y ejecuta la herramienta solicitada, devuelve el resultado como `ToolMessage` y actualiza los contadores. Limita a dos las llamadas por consulta y captura excepciones para que el agente pueda informar del fallo.
- **Construcción del grafo:** conecta los nodos mediante `StateGraph` y conserva el historial con `SqliteSaver` y un `thread_id` por conversación.
- **Bloque interactivo:** lee preguntas desde la terminal, crea identificadores de consulta y conversación, adjunta metadatos y callbacks y ejecuta el grafo con `tracing_context` para LangSmith.

### `tools/` — fuentes externas

- **`consultar_paquete`:** consulta información de paquetes publicados en PyPI (por ejemplo, versión y requisitos de Python).
- **`buscar_documentacion`:** intenta localizar documentación técnica relacionada con la consulta. Si no encuentra resultados, el asistente debe reconocer esa limitación en lugar de inventar enlaces.

### `masking.py` — protección de datos

- **`ocultar_datos(texto)`:** identifica correos electrónicos mediante una expresión regular y los sustituye por `[EMAIL_OCULTO]`.
- **`mask_otel_spans(...)`:** aplica el enmascaramiento a atributos de spans antes de enviarlos a Langfuse.
- **`anonimizar_langsmith(...)`:** transforma los datos de las trazas enviadas mediante el cliente configurado de LangSmith. Su objetivo es ocultar correos en entradas y salidas compatibles con el proceso de anonimización.

### Scripts de evaluación y diagnóstico

| Archivo | Responsabilidad |
|---|---|
| `evaluacion.py` | Define las diez preguntas y sus resultados esperados; `ejecutar_pregunta(...)` lanza cada consulta con un historial independiente y mide su duración. |
| `metricas.py` | Consulta las trazas raíz en LangSmith y recupera versión de prompt, tokens y coste estimado. |
| `prueba_fallo.py` | Sustituye temporalmente la función interna de `consultar_paquete` para simular un problema de conexión. Comprueba la recuperación del agente y restaura la herramienta. |
| `prueba_retraso.py` | Introduce `time.sleep(3)` antes de ejecutar la función original y permite inspeccionar la latencia adicional. |

## Instalación y configuración

Requiere **Python 3.10 o superior**. Desde PowerShell, en la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crear un archivo `.env` a partir de `.env.example` y completar las variables de entorno con las credenciales propias. El archivo `.env` es local y no debe publicarse.

```dotenv
OPENAI_API_KEY=tu_clave
MODEL_ID=gpt-4.1-mini

LANGSMITH_API_KEY=tu_clave
LANGSMITH_PROJECT=DevAssistant-Observability
LANGSMITH_TRACING=true

LANGFUSE_PUBLIC_KEY=tu_clave_publica
LANGFUSE_SECRET_KEY=tu_clave_secreta
LANGFUSE_BASE_URL=https://cloud.langfuse.com

PROMPT_PROVIDER=langsmith
PROMPT_VERSION=1
```

> La configuración de Langfuse puede variar según la región de la cuenta. Los prompts versionados deben estar disponibles en el espacio de trabajo configurado para poder recuperarlos.

## Ejecución

```powershell
python main.py
```

El asistente permite consultar información sobre programación y utilizar herramientas para obtener datos de paquetes Python y buscar documentación.

### Observabilidad

Cada ejecución se registra en ambas plataformas, con información de identificación y contexto, como `query_id`, `conversation_id`, modelo y versión del prompt. Las trazas permiten revisar las llamadas al LLM, la ejecución de herramientas, las respuestas, los errores y la duración. LangSmith también ha registrado tokens y coste estimado.

### Versionado de prompts

Se creó el prompt `devassistant-system` con dos versiones en los gestores de prompts de **LangSmith** y **Langfuse**. Para la evaluación se utilizaron las versiones de LangSmith:

| Versión | Identificador del commit |
|---|---|
| V1 | `5d4b482b` |
| V2 | `0b6de0a2` |

Las dos versiones se probaron con el mismo modelo (`gpt-4.1-mini`), temperatura (`0`) y conjunto de diez preguntas. El prompt se selecciona al iniciar el proceso mediante `PROMPT_PROVIDER` y `PROMPT_VERSION`.

## Evaluación V1 frente a V2

La batería incluye preguntas conceptuales sobre LangGraph/LangChain, consultas a PyPI, búsqueda de documentación y comportamiento ante herramientas sin resultados. Se definieron respuestas esperadas antes de ejecutar las pruebas.

**Criterio manual:** `1` si la respuesta satisface la petición, utiliza correctamente las herramientas cuando corresponde y no inventa información; `0` en caso contrario.

| Métrica | V1 | V2 |
|---|---:|---:|
| Aciertos (evaluación manual) | 7/10 | 8/10 |
| Latencia media | 2,12 s | 2,58 s |
| Llamadas a herramientas | 9 | 6 |
| Errores técnicos registrados | 0 | 0 |
| Tokens totales | 7.218 | 8.167 |
| Tokens medios por pregunta | 721,8 | 816,7 |
| Coste total estimado (USD) | $0,0045984 | $0,0049876 |
| Coste medio estimado (USD) | $0,00045984 | $0,00049876 |

Los tokens y costes proceden de las trazas consultadas en LangSmith. Se consideraron **diez ejecuciones oficiales por versión**; se excluyó una prueba preliminar adicional de V2. Los costes son estimaciones de la plataforma, no importes facturados verificados.

**Observaciones:** ambas versiones fallaron al explicar correctamente qué es LangGraph y al distinguirlo de LangChain. V2 respondió mejor ante la ausencia de resultados, pero consumió más tokens y presentó mayor latencia media. La prueba de búsqueda de documentación se consideró correcta según el criterio previamente establecido (uso de herramienta y reconocimiento de ausencia de resultados), aunque no aportó enlaces útiles.

Para reproducir la batería, ejecutar `python evaluacion.py` una vez con `PROMPT_VERSION=1` y otra con `PROMPT_VERSION=2`, reiniciando el proceso entre ambas. `python metricas.py` consulta las métricas registradas en LangSmith. Las respuestas pueden variar entre ejecuciones incluso con temperatura 0.

## Pruebas de resiliencia y rendimiento

### Fallo controlado

```powershell
python prueba_fallo.py
```

Se simuló una caída de conexión a PyPI durante `consultar_paquete`. El error se incorporó al estado (`errores`) y el agente respondió indicando que no podía verificar la versión, sin inventar el dato. La herramienta original se restauró al terminar.

### Retraso controlado

```powershell
python prueba_retraso.py
```

Se añadió una espera artificial de **3 segundos** antes de ejecutar la función original de la herramienta. La prueba terminó sin errores y permitió observar el efecto del retraso. La versión de FastAPI devuelta en esta prueba fue distinta de la obtenida durante la evaluación; ese dato requiere comprobación adicional y **no debe utilizarse como evidencia de exactitud**. Para acreditar la latencia, revisar la duración del nodo/herramienta en las trazas.

## Privacidad

Se implementó un mecanismo de anonimización de direcciones de correo electrónico que sustituye valores detectados por `[EMAIL_OCULTO]` antes de su almacenamiento en las trazas de observabilidad. Se comprobó con un correo ficticio en las entradas registradas.

**Alcance:** el ejemplo cubre correos electrónicos; no constituye una solución general para todos los datos personales. Antes de utilizar datos reales deben revisarse todas las entradas, salidas, atributos y trazas secundarias, así como la configuración de acceso privado y la política de retención de ambas plataformas. No subir `.env`, bases de datos conversacionales ni trazas con datos sensibles al repositorio.

## Evidencias gráficas

El repositorio incluye capturas de la instrumentación, la gestión de prompts y las pruebas de diagnóstico realizadas con LangSmith y Langfuse. Todas están disponibles en la carpeta [EjemplosGraficos](./EjemplosGraficos/).

| Evidencia | Descripción |
|---|---|
| [Trazas en LangSmith](./EjemplosGraficos/LangSmith.png) | Seguimiento de las ejecuciones del agente en LangSmith. |
| [Trazas en Langfuse](./EjemplosGraficos/LangFuse.png) | Visualización de las ejecuciones en Langfuse. |
| [Gestión de prompts](./EjemplosGraficos/GetionPrompts_LangSmith.png) | Versionado de prompts en LangSmith. |
| [Metadatos de ejecución](./EjemplosGraficos/Metadatos_LangFuse.png) | Información contextual asociada a las trazas de Langfuse. |
| [Anonimización en LangSmith](./EjemplosGraficos/Masking_LangSmith.png) | Evidencia del enmascaramiento de correos en LangSmith. |
| [Anonimización en Langfuse](./EjemplosGraficos/Masking_LangFuse.png) | Evidencia del enmascaramiento de correos en Langfuse. |
| [Fallo controlado](./EjemplosGraficos/Prueba_fallo.py.png) | Ejecución de la prueba con un error simulado de herramienta. |
| [Retraso controlado](./EjemplosGraficos/Prueba_retraso.png) | Ejecución de la prueba con latencia artificial. |

Las capturas complementan las métricas y los resultados descritos en este documento. La disponibilidad de trazas interactivas en las plataformas depende de los permisos de acceso a cada proyecto.

## Lectura de las trazas

Una consulta normal genera una traza principal del grafo y operaciones hijas correspondientes al modelo y, si procede, a las herramientas. Los identificadores `query_id` y `conversation_id` ayudan a localizar una ejecución concreta; `prompt_version` permite comparar las versiones sin confundir resultados. La etiqueta `evaluacion` distingue las pruebas oficiales de las conversaciones interactivas y de las simulaciones.

En el análisis de calidad conviene separar **éxito técnico** de **respuesta correcta**: una traza puede finalizar sin excepciones y contener una explicación equivocada. Por eso, además de medir latencia, tokens y coste, se revisaron manualmente las diez respuestas de cada versión con los criterios definidos antes de las pruebas.

## Conclusión

El proyecto demuestra cómo instrumentar un agente LangGraph en dos plataformas de observabilidad y utilizar sus trazas para analizar comportamiento, coste, latencia y errores. **V2 obtuvo una mejor puntuación manual (8/10 frente a 7/10)**, aunque con mayor consumo y coste. La observabilidad también facilitó el diagnóstico de una herramienta fallida y de una ejecución artificialmente lenta.

Como mejora futura, convendría reforzar las instrucciones sobre LangGraph y la recuperación de documentación, repetir la evaluación varias veces para reducir la variabilidad y ampliar la protección de datos.
