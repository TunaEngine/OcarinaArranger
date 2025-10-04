# Preview toolbar icon placeholders

The redesigned preview tabs expect the following PNG assets to be available in
this package. They were intentionally removed from source control so they can
be supplied externally. Provide a light and dark variant for each icon:

- `arranged_play_light.png`
- `arranged_play_dark.png`
- `arranged_pause_light.png`
- `arranged_pause_dark.png`
- `arranged_zoom_in_light.png`
- `arranged_zoom_in_dark.png`
- `arranged_zoom_out_light.png`
- `arranged_zoom_out_dark.png`

Each image should be a small square icon (roughly 24&times;24 px) with a
transparent background. Once the files are added, the UI will load them
automatically for the appropriate theme. For backward compatibility, the
application still falls back to `arranged_<name>.png` when a light-specific
variant is not present, but supplying both variants is recommended.
