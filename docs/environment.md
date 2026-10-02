# Environment

- macOS arm64, Python 3.12.0 (Framework build)
- venv: `.venv/` (uv). Locked deps: `docs/requirements.lock.txt`
- Java: Homebrew `openjdk@21` at `/opt/homebrew/opt/openjdk@21` (keg-only).
  Run scripts with `export JAVA_HOME=/opt/homebrew/opt/openjdk@21`.
- `osmium-tool` 1.19.1 (Homebrew) for cropping the OSM extract.
- r5py config: `r5py.yml` (max-memory 16G, verbose).
- R5 jar auto-fetched by r5py to `~/.cache/r5py/r5-v7.5.1-r5py-all.jar`;
  the built transport network is cached there too (delete to force a rebuild).

## Key versions
geopandas==1.1.4
matplotlib==3.11.1
pandas==3.0.5
pyproj==3.7.2
r5py==1.1.7
rasterio==1.5.1
shapely==2.1.2
