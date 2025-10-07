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
- `arranged_volume_light.png`
- `arranged_volume_dark.png`
- `arranged_volume_muted_light.png`
- `arranged_volume_muted_dark.png`

Each image should be a small square icon (roughly 24&times;24 px) with a
transparent background. Once the files are added, the UI will load them
automatically for the appropriate theme. The volume button uses the
`arranged_volume_*.png` pair when unmuted and the
`arranged_volume_muted_*.png` pair when muted. For backward compatibility, the
application still falls back to `arranged_<name>.png` when a light-specific
variant is not present, but supplying both variants (light/dark and muted) is
recommended.
