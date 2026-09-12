# 3D Enhancer

![3D Enhancer — ilustración conceptual de un personaje 3D transformándose en una persona fotográfica](assets/readme-header.png)

*Lee esto en [inglés / English](README.md).*

Aplicación de escritorio en Python y PyQt5 que envía renders completos a GPT Image 2 o GPT Image 2.5 (Sunburst) para sustituir sus personajes 3D por personas fotográficas, manteniendo la escena y la composición.

## Qué incluye

- Selección múltiple de imágenes, carpetas y arrastrar/soltar.
- Edición de la imagen completa con un selector de modelo: `gpt-image-2` o `gpt-image-2.5-sunburst`, ambos con `quality="high"`. Se recuerda la selección; GPT Image 2 sigue siendo el predeterminado.
- Prompt restrictivo editable para conservar número, posición, escala, pose y ropa de cada personaje, además de arquitectura, textos, iluminación y cámara.
- Procesado configurable de una a cinco imágenes simultáneas.
- Detección de resultados existentes con opción de omitirlos o reprocesarlos sin sobrescribir archivos.
- Estado por imagen, progreso, cancelación, registro y previsualización original/resultado.
- Directorio de salida y ajustes persistentes mediante `QSettings`.

Cada imagen procesada realiza una llamada independiente a la API.

## Instalación

Se recomienda Python 3.11 o 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

La clave de OpenAI se introduce directamente en la parte superior derecha de la aplicación. Se guarda con DPAPI en Windows o en el Llavero de macOS, vinculada al usuario actual; no se crea ningún archivo `.env` ni se incluye la clave en el proyecto.

## Uso

```powershell
python main.py
```

En Windows también puedes abrir `run_app.bat`.

Si utilizas la versión empaquetada para Windows, abre `release/windows/3D Enhancer.exe`.

1. Introduce la clave de OpenAI y pulsa **Guardar API key**. Solo es necesario la primera vez o al cambiarla.
2. Añade imágenes, una carpeta completa o arrastra los renders sobre la ventana.
3. Selecciona el directorio de salida.
4. Elige **GPT Image 2** o **GPT Image 2.5 (Sunburst)** en **Modelo de imagen**, justo debajo del directorio de salida.
5. Opcionalmente abre **Ajustes avanzados** para cambiar el número de imágenes simultáneas o el prompt.
6. Pulsa **Procesar imágenes**.

La interfaz utiliza etiquetas en español; los pasos anteriores mantienen los nombres que aparecen en la aplicación.

Si ya existen resultados, la aplicación pregunta una sola vez si deben omitirse o reprocesarse. Al reprocesar conserva los anteriores y crea nombres como `render_01_humanized_2.png`, `render_01_humanized_3.png`, etc.

## Elegir el modelo de imagen

| Opción en la aplicación | Identificador del modelo en la API | Predeterminado |
| --- | --- | --- |
| GPT Image 2 | `gpt-image-2` | Sí |
| GPT Image 2.5 (Sunburst) | `gpt-image-2.5-sunburst` | No |

La opción GPT Image 2.5 utiliza la variante Sunburst. Ambas opciones editan el render completo con el mismo prompt y calidad alta (`quality="high"`).

El modelo seleccionado se aplica a todas las imágenes del siguiente lote. El selector se desactiva durante el procesado y el modelo activo aparece en los detalles del progreso y en el registro del lote. La aplicación guarda la selección al iniciar el procesado o cerrar la ventana, y la recupera al volver a abrirse.

Para comparar ambos modelos con el mismo render, termina el primer lote, cambia de modelo y procesa la imagen de nuevo. Elige **Reprocesar y renombrar** cuando se pregunte por los resultados existentes. Los archivos anteriores se conservan; cambiar de modelo no reprocesa automáticamente las imágenes existentes.

## Generar las aplicaciones de escritorio

El icono y la configuración de PyInstaller ya están incluidos. Los binarios deben compilarse en su propio sistema operativo; PyInstaller no permite crear de forma fiable una aplicación de macOS desde Windows.

Windows, desde PowerShell:

```powershell
.\build_windows.ps1
```

Resultado: `release/windows/3D Enhancer.exe`.

macOS, desde Terminal:

```bash
chmod +x build_macos.command
./build_macos.command
```

Resultado: `release/macos/3D Enhancer.app`. La aplicación generada no lleva firma de Apple; para distribuirla fuera de tu equipo deberá firmarse y, normalmente, notarizarse con una cuenta de Apple Developer.

## Archivos generados

Para `render_01.jpg` se crea `render_01_humanized.png`. Los reprocesados utilizan sufijos numéricos y nunca sobrescriben un resultado existente.

## Ajustes recomendados

- El valor predeterminado procesa hasta cinco imágenes simultáneas. Redúcelo si la cuenta alcanza límites temporales de la API.
- El prompt predeterminado evita enfatizar caras o pelo y exige conservar tamaño de cabeza, silueta, pose, ropa y oclusiones.
- Las caras lejanas se piden con detalle moderado para evitar rasgos sobredimensionados o inventados.
- Cancelar detiene los siguientes grupos después de que terminen las llamadas activas.

## Verificación sin consumir la API

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py renderhuman tests
```

Las pruebas usan un cliente falso y no realizan peticiones externas. Cubren ambos modelos, el envío del modelo seleccionado a la API de imágenes, el guardado y la recuperación de la selección y la desactivación del selector durante el procesado, además del tratamiento de imágenes, las credenciales y el procesado paralelo.

## Notas técnicas

La integración sigue la [guía oficial de generación y edición de imágenes de OpenAI](https://developers.openai.com/api/docs/guides/image-generation). Se envía una copia PNG normalizada del render completo. La conservación de la escena depende del seguimiento del prompt y no constituye un bloqueo matemático de píxeles.

La clave nunca se muestra de nuevo ni se guarda en texto plano. Windows utiliza DPAPI y macOS utiliza su Llavero. Al cambiar de usuario o reinstalar el sistema será necesario volver a introducirla.

Revisa los requisitos de privacidad de tu proyecto y las condiciones vigentes de uso de la API antes de procesar material confidencial o distribuir la aplicación.
