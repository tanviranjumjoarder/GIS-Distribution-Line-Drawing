GIS SHAPEFILE GENERATOR
=======================

WHAT IT DOES
  Takes a pole data sheet (Excel: .xls / .xlsx / .xlsm) and produces two
  shapefiles ready to merge into your master GIS layers:

    <name>_points.shp   EPSG:4326   — point layer, one feature per pole
    <name>_lines.shp    EPSG:32645  — line layer, the connecting network

  Field names, order, and types are produced to match a standard pole/line
  schema so the outputs drop straight into an existing layer.

HOW TO RUN
  1. Double-click  "Run GIS App.bat"
  2. A browser opens at  http://127.0.0.1:5000/
  3. Drag in the spreadsheet (or click "Use the latest spreadsheet from my Downloads").
  4. Click "Generate shapefiles", then download the zip(s).
  Keep the black window open while using the app; close it to stop the server.

HOW LINES ARE BUILT
  The sheet contains poles only. Lines are reconstructed from the pole numbering
  (P_Number) tree: poles linked by a trailing-integer increment form one branch
  polyline (e.g. ...-204-1 -> ...-204-2 -> ...-204-3; and a tap branch
  ...-204-2 -> ...-204-2-1 -> ...-204-2-2), each joined to its parent pole. Every
  feeder's section-head poles are connected in numbering order to form the
  backbone. Lengths are computed in metres (UTM 45N); feeder / kV / conductor are
  read from the poles.

ABOUT THE FILE COUNT
  Each output layer is a COMPLETE shapefile:
    .shp  geometry      (required)
    .shx  shape index   (required)
    .dbf  attributes    (required)
    .prj  projection    (recommended - included)
    .cpg  text encoding  (recommended - included)
    .shp.xml  metadata   (included)
  The .sbn / .sbx files you may see beside ArcGIS shapefiles are a proprietary
  ESRI spatial index that no open tool can write; ArcGIS rebuilds them by itself
  the moment the layer is opened. They are never required to read, edit, or merge
  the data.

REQUIREMENTS  (already installed on this PC)
  Python 3 with: flask, geopandas, pandas, shapely, pyproj, xlrd, openpyxl
  Fresh PC:  pip install flask geopandas xlrd openpyxl

NOTES
  - Runs entirely on your machine; nothing is uploaded to the internet.
  - Generated files are kept under  GIS_Shapefile_App\outputs\<timestamp>\
