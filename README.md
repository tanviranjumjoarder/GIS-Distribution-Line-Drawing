# GIS Distribution Line Drawing

A small app that turns a pole list (an Excel file) into map files (shapefiles) you can
open in QGIS or ArcGIS. It makes two layers: the poles as points, and the lines that
join them. You don't draw the lines by hand. The app works them out from the pole
numbers.

## How to run it

You need Python 3 installed. The first time on a PC, install the packages once.
Easiest way: double-click **`Install requirements.bat`**. Or run it yourself:

```
py -m pip install -r requirements.txt
```

Then double-click **`Run GIS App.bat`**. If the packages are missing, the launcher
installs them for you on the first run. Your browser opens at http://127.0.0.1:5000.
Drag in one or more Excel files, click **Generate**, and download the result. Keep the
small black window open while you use it.

## How the lines are drawn

Each pole number says where the pole belongs. Take `KU3-KUS-2B-249`:

- `KU3` is the substation
- `KUS` is the PBS
- `2B` is the feeder
- `249` is the pole number

From that, the app joins poles with a few simple rules:

- Poles are joined only inside the same feeder. A `2B` pole is never linked to a `3C` pole.
- Poles join in order: `249` to `250`, and a branch goes `249-1`, `249-2`, `249-3`.
- A branch ties back to its own parent pole, like `249-2-1` back to `249-2`.
- If two poles are more than 500 m apart they are not joined. Real spans are short, so a
  long jump usually means a mistake.
- If a row has a missing or wrong coordinate, the app skips it and tells you instead of
  crashing.

Whatever it skips (lone poles, long jumps, bad coordinates) is listed on screen so you
can fix it in the sheet.

## What the Excel needs

One row per pole, on the first sheet. The columns that matter most:

- `P_Number`: the pole number (this is what builds the lines)
- `Latitude` and `Longitude`: in degrees
- `F_Name`, `SS_N`, `Cond_KV`, `S_Date` and the other usual columns are copied into the
  output where they exist.

## What you get

- `*_points.shp`: the poles (EPSG:4326)
- `*_lines.shp`: the network (EPSG:32645)

Both come as a zip with all the shapefile parts, ready to merge into your master layers.

## Files

- `app.py`: the web app
- `converter.py`: builds the points and lines
- `templates/index.html`: the page you see
- `Run GIS App.bat`: the launcher

## License

MIT. See `LICENSE`.
