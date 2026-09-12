"""Spanish/English UI messages, selected from the operating system UI language."""
from __future__ import annotations

from functools import lru_cache

from PyQt5.QtCore import QLibraryInfo, QLocale, QTranslator

from renderhuman.resources import resource_path

_preference = "system"


def set_language(preference: str) -> None:
    global _preference
    if preference not in {"system", "es", "en"}:
        raise ValueError(f"Unsupported language preference: {preference}")
    _preference = preference
    get_language.cache_clear()


@lru_cache(maxsize=1)
def get_language() -> str:
    if _preference != "system":
        return _preference
    locale = QLocale.system()
    languages = locale.uiLanguages()
    primary = languages[0] if languages else locale.name()
    return "es" if primary.replace("_", "-").split("-")[0].lower() == "es" else "en"


class LocalizedText(str):
    """A string that retains its message and values for live retranslation."""

    def __new__(cls, source: str, **values: object):
        instance = super().__new__(cls, cls._render(source, values))
        instance.source = source
        instance.values = values
        return instance

    @staticmethod
    def _render(source: str, values: dict[str, object]) -> str:
        template = source if get_language() == "es" else ENGLISH[source]
        return template.format(**{
            key: render_text(value) if isinstance(value, LocalizedText) else value
            for key, value in values.items()
        }) if values else template

    def render(self) -> str:
        return self._render(self.source, self.values)


def render_text(text: str) -> str:
    return text.render() if isinstance(text, LocalizedText) else str(text)


def tr(source: str, **values: object) -> LocalizedText:
    return LocalizedText(source, **values)


def describe_error(error: Exception) -> LocalizedText:
    message = error.args[0] if len(error.args) == 1 and isinstance(error.args[0], LocalizedText) else str(error)
    return tr("{kind}: {message}", kind=type(error).__name__, message=message)


def apply_language(preference: str, app) -> None:
    set_language(preference)
    previous = getattr(app, "qt_translator", None)
    if previous is not None:
        app.removeTranslator(previous)
        previous.deleteLater()
    app.qt_translator = install_qt_translations(app)


def install_qt_translations(app) -> QTranslator | None:
    """Translate Qt's standard buttons and menus; retain the returned translator."""
    if get_language() != "es":
        return None
    translator = QTranslator(app)
    bundled = resource_path("translations/qtbase_es.qm")
    if translator.load(str(bundled)) or translator.load(
        "qtbase_es", QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    ):
        app.installTranslator(translator)
        return translator
    return None


# Spanish is the source language. Named fields keep paths and user data intact.
ENGLISH = {
    "Idioma": "Language",
    "Sistema": "System",
    "Cambiar el idioma de la interfaz sin reiniciar la aplicación.": "Change the interface language without restarting the application.",
    "{title} · {filename}": "{title} · {filename}",
    "{message} {filename}": "{message} {filename}",
    "{kind}: {message}": "{kind}: {message}",
    "Convierte personajes de renders 3D en personas fotorrealistas": "Turn 3D render characters into photorealistic people",
    "La clave se guarda en el almacén seguro de credenciales de tu sistema.": "The key is saved in your system's secure credential store.",
    "Imágenes de entrada": "Input images",
    "0 imágenes": "0 images",
    "Arrastra aquí imágenes o carpetas. También puedes usar los botones inferiores.": "Drop images or folders here, or use the buttons below.",
    "Añadir imágenes": "Add images",
    "Añadir carpeta": "Add folder",
    "Quitar selección": "Remove selected",
    "Limpiar": "Clear",
    "ARCHIVO": "FILE",
    "TAMAÑO": "SIZE",
    "ESTADO": "STATUS",
    "DETALLE": "DETAILS",
    "Directorio de salida": "Output directory",
    "Selecciona dónde guardar los resultados": "Choose where to save the results",
    "Seleccionar": "Browse",
    "Abrir": "Open",
    "Guardar junto a cada imagen de entrada": "Save next to each input image",
    "Cada resultado se guarda en la carpeta de su original, aunque las imágenes del lote estén en carpetas distintas.": "Save each result in its original image's folder, even when the batch contains images from different folders.",
    "Modelo de imagen": "Image model",
    "Modelo utilizado para editar todas las imágenes del lote.": "Model used to edit every image in the batch.",
    "Ajustes avanzados": "Advanced settings",
    " imágenes": " images",
    "Número de renders enviados simultáneamente al modelo seleccionado.": "Number of renders sent to the selected model at the same time.",
    "Imágenes simultáneas": "Concurrent images",
    "Cada render se envía completo al modelo seleccionado en una sola llamada. No se ejecutan detectores ni se generan máscaras.": "Each complete render is sent to the selected model in a single call. No detectors are run and no masks are generated.",
    "Prompt de edición · calidad alta": "Editing prompt · high quality",
    "Restaurar prompt": "Reset prompt",
    "Cancelar": "Cancel",
    "Procesar imágenes": "Process images",
    "Previsualización": "Preview",
    "Selecciona una imagen": "Select an image",
    "Selecciona una imagen de la cola": "Select an image from the queue",
    "El resultado aparecerá al completar la edición": "The result will appear when editing is complete",
    "Resultado": "Result",
    "Estado actual": "Current status",
    "Listo para procesar": "Ready to process",
    "Añade uno o varios renders para comenzar.": "Add one or more renders to get started.",
    "Imagen": "Image",
    "Lote": "Batch",
    "Ver registro": "Show log",
    "Ocultar registro": "Hide log",
    "Clave guardada de forma segura": "Key securely saved",
    "Introduce tu clave de OpenAI (sk-…)": "Enter your OpenAI key (sk-…)",
    "API configurada · Guardar cambios": "API configured · Save changes",
    "Guardar API key": "Save API key",
    "La clave ya está guardada. Introduce una nueva clave para sustituirla.": "A key is already saved. Enter a new key to replace it.",
    "Introduce una clave de OpenAI.": "Enter an OpenAI key.",
    "La clave de OpenAI no parece válida.": "The OpenAI key does not appear to be valid.",
    "Clave guardada localmente en el almacén seguro de tu sistema.": "Key saved locally in your system's secure credential store.",
    "Seleccionar renders": "Select renders",
    "Imágenes (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)": "Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)",
    "Seleccionar carpeta de renders": "Select render folder",
    "No se encontraron imágenes compatibles en la carpeta.": "No supported images were found in the folder.",
    "Seleccionar directorio de salida": "Select output directory",
    "Pendiente": "Pending",
    "Completada": "Completed",
    "Omitida": "Skipped",
    "{count} imagen": "{count} image",
    "{count} imágenes": "{count} images",
    "Ya no existe el archivo:\n{path}": "The file no longer exists:\n{path}",
    "Selecciona un directorio de salida.": "Select an output directory.",
    "Ya existen resultados para {existing} de {total} imagen(es).": "Results already exist for {existing} of {total} image(s).",
    "¿Quieres volver a procesarlas? Los resultados anteriores se conservarán y los nuevos se guardarán con un sufijo como _2 o _3.": "Would you like to process them again? Previous results will be kept and new ones saved with a suffix such as _2 or _3.",
    "Reprocesar y renombrar": "Reprocess and rename",
    "Omitir las procesadas": "Skip processed images",
    "Ya procesada: se conserva {filename}.": "Already processed: keeping {filename}.",
    "Ya procesada": "Already processed",
    "En cola": "Queued",
    "No hay imágenes pendientes": "No images pending",
    "Todos los resultados existentes se han conservado sin consumir la API.": "All existing results have been kept without using the API.",
    "Introduce y guarda una clave de OpenAI antes de procesar.": "Enter and save an OpenAI key before processing.",
    "Procesando…": "Processing…",
    "Preparando el lote": "Preparing batch",
    "{count} imagen(es) en cola · hasta {parallel} simultáneas · {model}": "{count} image(s) queued · up to {parallel} concurrent · {model}",
    "Modelo del lote: {model} · calidad alta": "Batch model: {model} · high quality",
    "Salida: carpeta de cada imagen de entrada": "Output: each input image's folder",
    "Salida: {directory}": "Output: {directory}",
    "Error de procesado": "Processing error",
    "Procesado cancelado": "Processing cancelled",
    "Completadas: {succeeded} · Sin procesar/omitidas: {skipped} · Errores: {failed}": "Completed: {succeeded} · Unprocessed/skipped: {skipped} · Errors: {failed}",
    "Lote terminado con incidencias": "Batch finished with errors",
    "Completadas: {succeeded} · Omitidas/copias: {skipped} · Errores: {failed}": "Completed: {succeeded} · Skipped/copies: {skipped} · Errors: {failed}",
    "Lote completado": "Batch completed",
    "Completadas con IA: {succeeded} · Omitidas: {skipped}": "Completed with AI: {succeeded} · Skipped: {skipped}",
    "Cancelando…": "Cancelling…",
    "La cancelación se aplicará al terminar la operación activa. Una llamada a la API no puede interrumpirse a mitad.": "Cancellation will take effect when the active operation finishes. An API call cannot be interrupted midway.",
    "Hay un lote en proceso. ¿Quieres cancelarlo y cerrar cuando termine la operación activa?": "A batch is running. Cancel it and close when the active operation finishes?",
    "No se pudo cargar la previsualización": "Could not load the preview",
    "Selecciona un modelo de imagen compatible.": "Select a supported image model.",
    "El prompt no puede estar vacío.": "The prompt cannot be empty.",
    "El procesado paralelo debe estar entre 1 y 5 imágenes.": "Concurrent processing must be between 1 and 5 images.",
    "La imagen tiene dimensiones no válidas.": "The image has invalid dimensions.",
    "No se pudo adaptar la imagen a un tamaño admitido por GPT Image 2.": "Could not fit the image to a size supported by GPT Image 2.",
    "No se pudo alcanzar el tamaño mínimo requerido por GPT Image 2.": "Could not reach the minimum size required by GPT Image 2.",
    "El almacenamiento cifrado de la clave requiere Windows.": "Encrypted key storage requires Windows.",
    "Windows no pudo cifrar la clave: {error}": "Windows could not encrypt the key: {error}",
    "No se pudo descifrar la clave. Vuelve a introducirla en la aplicación.": "Could not decrypt the key. Enter it again in the application.",
    "La clave de OpenAI no puede estar vacía.": "The OpenAI key cannot be empty.",
    "No se pudo guardar la clave cifrada localmente.": "Could not save the encrypted key locally.",
    "La clave guardada está dañada. Vuelve a introducirla.": "The saved key is corrupted. Enter it again.",
    "No se pudo acceder al Llavero de macOS.": "Could not access the macOS Keychain.",
    "macOS no pudo guardar la clave en el Llavero.": "macOS could not save the key in the Keychain.",
    "No se pudo leer la clave del Llavero de macOS.": "Could not read the key from the macOS Keychain.",
    "No se pudo eliminar la clave del Llavero de macOS.": "Could not delete the key from the macOS Keychain.",
    "No hay una clave de OpenAI guardada. Introdúcela en la aplicación.": "No OpenAI key is saved. Enter it in the application.",
    "No está instalado el SDK de OpenAI. Ejecuta: pip install -r requirements.txt": "The OpenAI SDK is not installed. Run: pip install -r requirements.txt",
    "{model} no devolvió ninguna imagen.": "{model} did not return any images.",
    "{model} devolvió una respuesta sin datos de imagen.": "{model} returned a response without image data.",
    "Procesado cancelado.": "Processing cancelled.",
    "Editando imagen completa": "Editing complete image",
    "{model} · calidad alta · lienzo {size}": "{model} · high quality · canvas {size}",
    "Preparando": "Preparing",
    "Leyendo y normalizando el render": "Reading and normalizing the render",
    "Preparando edición completa": "Preparing full-image edit",
    "Conservando el render completo como referencia visual": "Keeping the complete render as a visual reference",
    "Aplicando instrucciones": "Applying instructions",
    "Una llamada; solo deben cambiar los personajes 3D": "One call; only the 3D characters should change",
    "Restaurando resolución": "Restoring resolution",
    "Recuperando el tamaño original de {width} × {height} px": "Restoring the original size of {width} × {height} px",
    "Guardando": "Saving",
    "Completada en una llamada de imagen completa.": "Completed in one full-image call.",
    "El número de filas no coincide con el número de imágenes.": "The number of rows does not match the number of images.",
    "Iniciando: {path}": "Starting: {path}",
    "Error en {filename}: {message}": "Error in {filename}: {message}",
    "El procesado no devolvió ningún resultado.": "Processing did not return a result.",
    "Error general: {message}": "General error: {message}",
}
