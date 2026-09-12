# 3D Enhancer

![3D Enhancer — ilustración conceptual de un personaje 3D transformándose en una persona fotográfica](assets/readme-header.png)

*Lee esto en [inglés / English](README.md).*

Aplicación de escritorio en Python y PyQt5 que envía renders completos a GPT Image 2 o GPT Image 2.5 (Sunburst) para sustituir sus personajes 3D por personas fotográficas, manteniendo la escena y la composición.

## Qué incluye

- Interfaz en español e inglés, con detección del idioma del sistema y selector superior para cambiarlo al vuelo.
- Selección múltiple de imágenes, carpetas y arrastrar/soltar.
- Edición de la imagen completa con un selector de modelo: `gpt-image-2` o `gpt-image-2.5-sunburst`, ambos con `quality="high"`. Se recuerda la selección; GPT Image 2 sigue siendo el predeterminado.
- Prompt restrictivo editable para conservar número, posición, escala, pose y ropa de cada personaje, además de arquitectura, textos, iluminación y cámara.
- Procesado configurable de una a cinco imágenes simultáneas.
- Detección de resultados existentes con opción de omitirlos o reprocesarlos sin sobrescribir archivos.
- Estado por imagen, progreso, cancelación, registro y previsualización original/resultado.
- Visor de comparación al pulsar la previsualización: antes/después con deslizador, zoom hasta el 800%, desplazamiento y pantalla completa.
- Directorio de salida y ajustes persistentes mediante `QSettings`.

Cada imagen procesada realiza una llamada independiente a la API.

## Idioma de la interfaz

El selector **Idioma**, en la parte superior, ofrece **Sistema**, **Español** y **English**. El cambio es inmediato y se recuerda para la próxima apertura, incluso si cambias de idioma mientras se procesa un lote. Se conservan las imágenes, las previsualizaciones, los ajustes y el progreso.

**Sistema** es la opción predeterminada: utiliza el idioma principal de pantalla del sistema operativo. Los sistemas en español, incluidas variantes regionales como España y México, utilizan español; los sistemas en inglés y en otros idiomas utilizan inglés. Puedes volver a esta opción para recuperar la detección automática.

Los botones, las ayudas, los diálogos, los mensajes de progreso y el registro utilizan el idioma seleccionado. El prompt de edición predeterminado permanece en inglés en ambas interfaces. Cambiar el idioma de la interfaz no traduce los prompts personalizados ni las rutas de archivos.

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
3. Selecciona un directorio de salida común o marca **Guardar junto a cada imagen de entrada**. Con la casilla marcada, cada resultado se guarda en la carpeta de su original, incluso si el lote contiene imágenes de distintas carpetas. Se desactiva el directorio común y se recuerda la preferencia; al desmarcarla se recupera el directorio común anterior.
4. Elige **GPT Image 2** o **GPT Image 2.5 (Sunburst)** en **Modelo de imagen**, justo debajo del directorio de salida.
5. Opcionalmente abre **Ajustes avanzados** para cambiar el número de imágenes simultáneas o el prompt.
6. Pulsa **Procesar imágenes**.
7. Pulsa la previsualización del original o del resultado para inspeccionar la imagen en el [visor antes y después](#visor-antes-y-después). Puedes abrirlo mientras continúa el procesado.

Estos pasos utilizan las etiquetas de la interfaz en español. Para las etiquetas en inglés, consulta el [README en inglés](README.md).

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

Con **Guardar junto a cada imagen de entrada**, los resultados existentes se comprueban en la carpeta de cada original. Las opciones de omitir o reprocesar y renombrar funcionan también en este modo.

## Visor antes y después

Pulsa una previsualización cargada o **Abrir visor** para abrir el comparador sobre la aplicación. También puedes enfocarla con el teclado y pulsar **Intro** o **Espacio**. El visor muestra el original y su resultado alineados, y permite alternar entre **Original**, **Comparar** y **Resultado**.

En el modo **Comparar**, el original aparece a la izquierda y el resultado a la derecha. El zoom y el desplazamiento mueven ambas imágenes a la vez para comparar el mismo detalle con una ampliación de hasta el **800%**.

| Acción | Control |
| --- | --- |
| Revelar el antes y el después | Arrastra la división sobre la imagen o el deslizador inferior. |
| Ajustar la comparación con el teclado | Enfoca el deslizador y usa las flechas; **Inicio** y **Fin** lo llevan a cada extremo. |
| Centrar la división | Pulsa **50 / 50**. |
| Ampliar un detalle | Usa la rueda sobre ese punto, los botones **+** y **−**, o las teclas **+** / **−**. |
| Desplazarte por la imagen ampliada | Arrastra la imagen; sobre la división, mantén **Espacio** o usa el botón central del ratón. |
| Ajustar la imagen al visor | Pulsa **Ajustar** o **0**. |
| Ver al 100% | Pulsa **100%** o **1**; el doble clic alterna entre 100% y ajustar. |
| Pantalla completa | Pulsa **Pantalla completa** o **F**. |
| Salir | **Esc** sale de pantalla completa; vuelve a pulsarlo para cerrar el visor. **Cerrar** lo cierra directamente. |

Si el resultado aún no está disponible, puedes explorar el original. Cuando termina su procesado, la comparación aparece automáticamente sin reiniciar el zoom. El visor permanece en la imagen que abriste aunque el lote continúe con otras imágenes. Abrirlo no modifica archivos ni consume la API.

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

Las pruebas de idioma también cubren la detección del idioma del sistema, las variantes regionales, el inglés como alternativa, el cambio al vuelo durante el procesado, la preferencia guardada y la traducción del progreso, los diálogos y el registro sin alterar los datos del usuario.

Las pruebas del visor cubren la división visual del antes/después, los controles sincronizados, el zoom centrado en el puntero, los límites del desplazamiento, la pantalla completa, los atajos de teclado, la orientación EXIF, los archivos ilegibles y la llegada de resultados con el visor abierto.

## Notas técnicas

La integración sigue la [guía oficial de generación y edición de imágenes de OpenAI](https://developers.openai.com/api/docs/guides/image-generation). Se envía una copia PNG normalizada del render completo. La conservación de la escena depende del seguimiento del prompt y no constituye un bloqueo matemático de píxeles.

La clave nunca se muestra de nuevo ni se guarda en texto plano. Windows utiliza DPAPI y macOS utiliza su Llavero. Al cambiar de usuario o reinstalar el sistema será necesario volver a introducirla.

Revisa los requisitos de privacidad de tu proyecto y las condiciones vigentes de uso de la API antes de procesar material confidencial o distribuir la aplicación.
