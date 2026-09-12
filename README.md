# 3D Enhancer

![3D Enhancer — conceptual transition from a 3D character to a photographic person](assets/readme-header.png)

*Read this in [Spanish / Español](README.es.md).*

Python and PyQt5 desktop application that sends complete renders to GPT Image 2 to replace their 3D characters with photographic people, preserving the scene and the composition.

## What it includes

- Multiple selection of images, folders, and drag and drop.
- A single processing method: full-image editing with `gpt-image-2` and `quality="high"`.
- Editable restrictive prompt to preserve the number, position, scale, pose, and clothing of each character, as well as architecture, text, lighting, and camera.
- Configurable processing of one to five simultaneous images.
- Detection of existing results with the option to skip or reprocess them without overwriting files.
- Per-image status, progress, cancellation, log, and original/result preview.
- Output directory and persistent settings through `QSettings`.

Each processed image makes an independent API call.

## Installation

Python 3.11 or 3.12 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The OpenAI key is entered directly in the top right of the application. It is stored with DPAPI on Windows or in the macOS Keychain, bound to the current user; no `.env` file is created and the key is never included in the project.

## Usage

```powershell
python main.py
```

On Windows you can also open `run_app.bat`.

## Building the desktop applications

The icon and the PyInstaller configuration are already included. Binaries must be built on their own operating system; PyInstaller cannot reliably create a macOS application from Windows.

Windows, from PowerShell:

```powershell
.\build_windows.ps1
```

Result: `release/windows/3D Enhancer.exe`.

macOS, from Terminal:

```bash
chmod +x build_macos.command
./build_macos.command
```

Result: `release/macos/3D Enhancer.app`. The generated application carries no Apple signature; to distribute it outside your own machine it must be signed and, normally, notarized with an Apple Developer account.

1. Enter the OpenAI key and press **Guardar API key**. This is only necessary the first time or when changing it.
2. Add images, a complete folder, or drag the renders onto the window.
3. Select the output directory. The application will remember it.
4. Optionally open **Ajustes avanzados** to change the number of simultaneous images or the prompt.
5. Press **Procesar imágenes**.

If results already exist, the application asks once whether they should be skipped or reprocessed. When reprocessing it keeps the previous ones and creates names such as `render_01_humanized_2.png`, `render_01_humanized_3.png`, and so on.

## Generated files

For `render_01.jpg` the file `render_01_humanized.png` is created. Reprocessed images use numeric suffixes and never overwrite an existing result.

## Recommended settings

- The default value processes up to five simultaneous images. Reduce it if the account hits temporary API limits.
- The default prompt avoids emphasizing faces or hair and requires preserving head size, silhouette, pose, clothing, and occlusions.
- Distant faces are requested with moderate detail to avoid oversized or invented features.
- Cancelling stops the following groups after the active calls finish.

## Verification without consuming the API

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py renderhuman tests
```

The tests use a fake client and make no external requests.

## Technical notes

The integration follows the [official OpenAI image generation and editing guide](https://developers.openai.com/api/docs/guides/image-generation). A normalized PNG copy of the complete render is sent. Preserving the scene depends on prompt adherence and is not a mathematical pixel lock.

The key is never displayed again nor stored in plain text. Windows uses DPAPI and macOS uses its Keychain. Changing user or reinstalling the system requires entering it again.

Review your project's privacy requirements and the current API terms of use before processing confidential material or distributing the application.
