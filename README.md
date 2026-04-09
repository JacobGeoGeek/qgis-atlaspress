# qgis-atlaspress

QGIS plugin for AtlasPress layout export and publishing workflows.

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
