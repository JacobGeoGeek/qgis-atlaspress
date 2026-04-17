def classFactory(iface):
    """Load AtlasPress from file atlas_press."""
    from .atlas_press import AtlasPress

    return AtlasPress(iface)
