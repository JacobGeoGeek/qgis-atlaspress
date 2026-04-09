def classFactory(iface):
    """Load AtlasPressPlugin from file atlas_press_plugin."""
    from .atlas_press import AtlasPress

    return AtlasPress(iface)
