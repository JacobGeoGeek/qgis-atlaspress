# qgis-atlaspress

QGIS plugin for AtlasPress layout export and publishing workflows.

## UI Design

Open Qt Designer with:

```bash
make designer
```

The `Makefile` uses `DESIGNER=/opt/homebrew/bin/designer` by default. Developers with a different installation path can override it per command:

```bash
make designer DESIGNER=/path/to/designer
```

## Resources

This plugin uses a Qt resource file at [resources.qrc](/resources.qrc). When icons are added or renamed, regenerate [`resources.py`](/resources.py) with:

```bash
make resources
```

The `Makefile` expects `rcc` to be available on your shell `PATH`. If your binary lives elsewhere, override it for a single run:

```bash
make resources RCC=/path/to/rcc
```

## Packaging

Build the plugin zip with:

```bash
make package
```

This target regenerates `resources.py` before creating the plugin archive in `dist/`.

## Product Previews

Opening product selection exports a snapshot of the layout and uploads it once.
Choose a product and size to generate its preview. Changing sizes reuses that
upload; restart the order flow to include subsequent map edits.

Preview generation is optional: once the map is uploaded and a size is selected,
Continue to Shipping works even if the preview is still generating or failed.
Retry is available for recoverable preview failures. Back from shipping preserves
the uploaded asset and selection.

The backend must support create, status, and retry under
`/functions/v1/mockups`. Local Printful testing requires a publicly accessible
source-image URL, such as your ngrok-backed storage URL.
