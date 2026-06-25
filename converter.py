"""GIS Base sheet  ->  points + lines shapefiles.

Points : one feature per Excel row, EPSG:4326, EXACT schema of
         All_Poles_kushtia_PBS_11kv_6.35kv_June_2026.shp (38 fields).
Lines  : derived from the P_Number numbering tree, EPSG:32645, EXACT schema of
         All_line_kushtia_PBS_11kv_6.35kv_June_2026.shp (19 fields).
         A line = a maximal run of poles linked by trailing-integer increment
         (one branch), prepended with its tap/parent pole so branches connect.
"""
import re
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from pyproj import Transformer

# ---- exact target schemas ---------------------------------------------------
POLE_COLS = ['PBS_N', 'Grid_N', 'Grid_Cap', 'SS_N', 'SS_Capacit', 'Vill_Mouza',
             'Area_N', 'Sheet_No', 'Surveyor', 'WSL_No', 'F_Name', 'P_Number',
             'Latitude', 'Longitude', 'P_Size', 'P_Material', 'P_Type',
             'P_Fittings', 'P_EnvT', 'Cond_Size', 'Cond_PhasS', 'Cond_KV',
             'TX_Cap', 'TX_SL', 'TX_PhasCon', 'ConsR_N', 'ConsR_AcN', 'ConsR_Cat',
             'ConsR_Load', 'Guy_Unit', 'Jump_Size', 'Device_1', 'Device_2',
             'Landmarks', 'Remarks', 'SS_Cap', 'Cond_PhaSq', 'S_Date']
POLE_FLOAT = {'WSL_No', 'Latitude', 'Longitude'}
# shapefile fields that are NOT in the Excel sheet (left empty, as in the source)
POLE_NOT_IN_EXCEL = {'SS_Capacit', 'Cond_PhasS'}

LINE_COLS = ['PBS_Name', 'Surv_Date', 'Proc_Date', 'Contd_Grid', 'Contd_SS',
             'Feeder_N', 'Feeder_Typ', 'Circuit', 'Con_KV', 'Con_Size',
             'Spn_Len_M', 'Length_M', 'Mileage_KM', 'Legend', 'Assigned', 'FY',
             'Remarks', 'Shape_Leng', 'Shape_Le_1']

T_4326_32645 = Transformer.from_crs('EPSG:4326', 'EPSG:32645', always_xy=True)

# A real pole-to-pole span is short (~40-50 m). Never draw a connection longer
# than this - it would mean two poles that are not actually neighbours.
MAX_SPAN_M = 500.0


# ---- helpers ----------------------------------------------------------------
def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    s = str(v).strip()
    return s if s != '' else None


def _yyyymmdd(v):
    """pole S_Date format e.g. 20250801"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return pd.to_datetime(v).strftime('%Y%m%d')
    except Exception:
        return _clean(v)


def _iso_date(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return pd.to_datetime(v).strftime('%Y-%m-%d')
    except Exception:
        return _clean(v)


def _fiscal_year(v):
    """Bangladesh FY (Jul-Jun) e.g. Aug-2025 -> '2025-26'"""
    try:
        d = pd.to_datetime(v)
        y = d.year if d.month >= 7 else d.year - 1
        return f'{y}-{str(y + 1)[-2:]}'
    except Exception:
        return None


def _dec(pn):
    """decrement the trailing integer (returns None if it would drop below 1)"""
    m = list(re.finditer(r'\d+', pn))
    if not m:
        return None
    last = m[-1]
    v = int(last.group()) - 1
    if v < 1:
        return None
    return pn[:last.start()] + str(v) + pn[last.end():]


def _strip_seg(pn):
    """remove the last '-segment' (go one level up the numbering tree)"""
    i = pn.rfind('-')
    return pn[:i] if i > 0 else None


def _mode(series):
    s = series.dropna()
    return s.mode().iloc[0] if len(s) else None


def _valid_coords(df):
    """Numeric, finite, in-range Latitude/Longitude. Anything else (blank, text,
    inf, out of -90..90 / -180..180) is treated as invalid and auto-skipped so it
    never reaches a geometry (which would crash the shapefile writer)."""
    n = len(df)
    if 'Latitude' not in df.columns or 'Longitude' not in df.columns:
        nan = pd.Series([np.nan] * n, index=df.index)
        return nan, nan, pd.Series([False] * n, index=df.index)
    lat = pd.to_numeric(df['Latitude'], errors='coerce').replace([np.inf, -np.inf], np.nan)
    lon = pd.to_numeric(df['Longitude'], errors='coerce').replace([np.inf, -np.inf], np.nan)
    valid = lat.notna() & lon.notna() & lat.between(-90, 90) & lon.between(-180, 180)
    return lat, lon, valid


# ---- main conversion --------------------------------------------------------
def read_sheet(xls_path, sheet=None):
    xls = pd.ExcelFile(xls_path)
    sn = sheet or xls.sheet_names[0]
    df = pd.read_excel(xls_path, sheet_name=sn)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def build_points(df):
    lat, lon, valid = _valid_coords(df)
    df = df[valid.values].reset_index(drop=True)            # drop invalid-coord rows
    lon = lon[valid.values].reset_index(drop=True)
    lat = lat[valid.values].reset_index(drop=True)
    n = len(df)
    data = {}
    for col in POLE_COLS:
        if col in POLE_NOT_IN_EXCEL or col not in df.columns:
            data[col] = [None] * n
        elif col == 'S_Date':
            data[col] = [_yyyymmdd(v) for v in df[col]]
        elif col in POLE_FLOAT:
            data[col] = pd.to_numeric(df[col], errors='coerce').replace([np.inf, -np.inf], np.nan).astype('float64')
        else:
            data[col] = [_clean(v) for v in df[col]]
    geom = [Point(x, y) for x, y in zip(lon, lat)]
    gdf = gpd.GeoDataFrame(pd.DataFrame(data)[POLE_COLS], geometry=geom,
                           crs='EPSG:4326')
    return gdf


def feeder_prefix(pn):
    """Feeder identity = the P_Number up to (not incl.) the first pure-number
    segment.  e.g. KU3-KUS-2B-249 and KU3-KUS-2B-249-1 -> 'KU3-KUS-2B'.
    Lines are NEVER drawn between poles whose feeder prefix differs."""
    parts = str(pn).split('-')
    for i, p in enumerate(parts):
        if p.strip().isdigit():
            return '-'.join(parts[:i])
    return str(pn)


def build_lines(df):
    from collections import defaultdict
    import math
    df = df.copy()
    df['P_Number'] = df['P_Number'].map(_clean)
    df = df[df['P_Number'].notna()]
    lat, lon, valid = _valid_coords(df)
    df = df[valid.values]
    by_pn = {pn: row for pn, row in zip(df['P_Number'], df.to_dict('records'))}
    coord = {}
    for pn, r in by_pn.items():
        x, y = T_4326_32645.transform(float(r['Longitude']), float(r['Latitude']))
        if math.isfinite(x) and math.isfinite(y):
            coord[pn] = (x, y)
    by_pn = {pn: by_pn[pn] for pn in coord}     # keep only finite-coordinate poles

    def line_attrs(members, length_m, feeder_typ=None):
        ss = _clean(_mode(members.get('SS_N', pd.Series(dtype=object))))
        feeder = _clean(_mode(members.get('F_Name', pd.Series(dtype=object))))
        sdate = (members['S_Date'].dropna().iloc[0]
                 if 'S_Date' in members and members['S_Date'].notna().any() else None)
        return {
            'PBS_Name': _clean(_mode(members.get('PBS_N', pd.Series(dtype=object)))),
            'Surv_Date': _iso_date(sdate), 'Proc_Date': _iso_date(sdate),
            'Contd_Grid': _clean(_mode(members.get('Grid_N', pd.Series(dtype=object)))),
            'Contd_SS': ss, 'Feeder_N': feeder, 'Feeder_Typ': feeder_typ, 'Circuit': '1',
            'Con_KV': _clean(_mode(members.get('Cond_KV', pd.Series(dtype=object)))),
            'Con_Size': _clean(_mode(members.get('Cond_Size', pd.Series(dtype=object)))),
            'Spn_Len_M': 0.0, 'Length_M': length_m, 'Mileage_KM': length_m / 1000.0,
            'Legend': f'{ss}-{feeder}' if ss and feeder else None,
            'Assigned': 'GIS, BREB', 'FY': _fiscal_year(sdate), 'Remarks': None,
            'Shape_Leng': length_m, 'Shape_Le_1': length_m,
        }

    # ---- group poles by feeder; ALL connections are confined to one feeder ----
    feeders = defaultdict(set)
    for pn in by_pn:
        feeders[feeder_prefix(pn)].add(pn)

    def _seg(a, b):                              # span length (metres) between 2 poles
        (x1, y1), (x2, y2) = coord[a], coord[b]
        return math.hypot(x2 - x1, y2 - y1)

    rows, geoms = [], []
    skipped = 0
    for fp, poles in feeders.items():
        # predecessor within this feeder only (trailing-int decrement = same branch)
        seq_pred = {pn: (_dec(pn) if (_dec(pn) in poles) else None) for pn in poles}
        seq_succ = {}
        for pn, sp in seq_pred.items():
            if sp is not None:
                seq_succ[sp] = pn

        def tap_of(pn):                          # ONLY the direct parent (one level up)
            s = _strip_seg(pn)
            return s if (s is not None and s in poles) else None

        def emit(run):
            if len(run) < 2:
                return
            line = LineString([coord[p] for p in run])
            members = pd.DataFrame([by_pn[p] for p in run])
            rows.append(line_attrs(members, line.length))
            geoms.append(line)

        # one polyline per branch: a run of poles linked by trailing-integer
        # increment (220-1 -> 220-2 -> 220-3), joined to its DIRECT parent
        # (249-2-1 -> 249-2). Only serial poles are joined; unrelated structures
        # (220-1 vs 234-1) are never joined; and any span > MAX_SPAN_M is cut so
        # there are no long lines across the map.
        for h in [pn for pn in poles if seq_pred[pn] is None]:
            chain = [h]; cur = h
            while cur in seq_succ:
                cur = seq_succ[cur]; chain.append(cur)
            tap = tap_of(h)
            seq = ([tap] + chain) if tap is not None else chain
            run = [seq[0]]
            for a, b in zip(seq, seq[1:]):
                if _seg(a, b) <= MAX_SPAN_M:
                    run.append(b)
                else:
                    skipped += 1
                    emit(run)
                    run = [b]
            emit(run)

    gdf = gpd.GeoDataFrame(pd.DataFrame(rows, columns=LINE_COLS), geometry=geoms,
                           crs='EPSG:32645')
    gdf.attrs['skipped_spans'] = skipped
    return gdf


def _write_metadata(shp_path, title, geom, n):
    """Write an ESRI-style .shp.xml metadata sidecar."""
    import time
    d = time.strftime('%Y%m%d'); t = time.strftime('%H%M%S') + '00'
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<metadata xml:lang="en">\n'
           f'  <Esri><CreaDate>{d}</CreaDate><CreaTime>{t}</CreaTime>'
           '<ArcGISFormat>1.0</ArcGISFormat><SyncOnce>TRUE</SyncOnce></Esri>\n'
           '  <dataIdInfo>\n'
           f'    <idCitation><resTitle>{title}</resTitle></idCitation>\n'
           f'    <idAbs>{n} {geom} feature(s) generated by GIS Shapefile Generator.</idAbs>\n'
           '  </dataIdInfo>\n'
           f'  <spatRepInfo><GeoObjCnt>{n}</GeoObjCnt></spatRepInfo>\n'
           '</metadata>\n')
    with open(shp_path + '.xml', 'w', encoding='utf-8') as f:
        f.write(xml)


def combine_sheets(sources):
    """sources: list of (path, display_name). Reads each first sheet and stacks
    them into one DataFrame so feeders that span several files connect."""
    frames, info, errors = [], [], []
    for path, name in sources:
        try:
            df = read_sheet(path)
            frames.append(df)
            info.append({'name': name, 'rows': int(len(df))})
        except Exception as e:
            errors.append(f'Could not read "{name}" ({type(e).__name__}).')
    if frames:
        combined = pd.concat(frames, ignore_index=True, sort=False)
    else:
        combined = pd.DataFrame(columns=['P_Number', 'Latitude', 'Longitude', 'F_Name'])
    return combined, info, errors


def convert(sources, out_dir, base_name, sheet=None):
    """sources may be a single path (str) or a list of (path, display_name)."""
    import os
    from shapely.ops import unary_union
    if isinstance(sources, str):
        sources = [(sources, os.path.basename(sources))]

    combined, files_info, errors = combine_sheets(sources)

    # de-duplicate poles by P_Number across all files (keep the first occurrence)
    pnser = combined['P_Number'].map(_clean) if 'P_Number' in combined else pd.Series(dtype=object)
    dupmask = pnser.notna() & pnser.duplicated(keep='first')
    dropped = int(dupmask.sum())
    if dropped:
        combined = combined[~dupmask.values].reset_index(drop=True)

    pts = build_points(combined)
    lns = build_lines(combined)
    os.makedirs(out_dir, exist_ok=True)
    p_fp = os.path.join(out_dir, base_name + '_points.shp')
    l_fp = os.path.join(out_dir, base_name + '_lines.shp')
    pts.to_file(p_fp, driver='ESRI Shapefile', encoding='utf-8')
    lns.to_file(l_fp, driver='ESRI Shapefile', encoding='utf-8')
    _write_metadata(p_fp, base_name + ' points', 'point', len(pts))
    _write_metadata(l_fp, base_name + ' lines', 'curve', len(lns))

    # ---- data-quality warnings ----
    pn = pts['P_Number'].astype('string').str.strip()
    warnings = list(errors)
    if dropped:
        warnings.append(f'{dropped} duplicate pole(s) across files were removed (kept the first).')
    _, _, vmask = _valid_coords(combined)
    miss = int((~vmask.values).sum())
    bad_ids = (combined.loc[~vmask.values, 'P_Number'].map(_clean).dropna().tolist()
               if 'P_Number' in combined else [])
    blank = int((pn.isna() | (pn == '')).sum())
    if miss:
        eg = f' (e.g. {", ".join(map(str, bad_ids[:4]))})' if bad_ids else ''
        warnings.append(f'{miss} row(s) had blank, non-numeric, infinite or out-of-range '
                        f'coordinates - auto-corrected by skipping them{eg}.')
    if blank:
        warnings.append(f'{blank} pole(s) have a blank P_Number.')
    off = 0
    if len(lns):
        u = unary_union(lns.geometry.values)
        pm = pts.to_crs('EPSG:32645')
        off = int((pm.geometry.apply(lambda g: g.distance(u) if g is not None else 0) >= 0.01).sum())
    if off:
        warnings.append(f'{off} pole(s) have no serial neighbour in the data, so they are '
                        f'points only (no line) - usually tap points off the main feeder.')
    skipped = int(lns.attrs.get('skipped_spans', 0))
    if skipped:
        warnings.append(f'{skipped} over-length connection(s) (> {int(MAX_SPAN_M)} m) were skipped - '
                        f'those poles are too far apart to be a real span (check their coordinates / numbering).')

    feeders = sorted(set(str(x).strip() for x in pts['F_Name'].dropna()))
    return {
        'rows': int(len(combined)),
        'file_count': len(files_info),
        'files': files_info,
        'points': int(len(pts)),
        'points_with_geom': int(pts.geometry.notna().sum()),
        'lines': int(len(lns)),
        'feeder_count': len(feeders),
        'line_km': round(float(lns['Length_M'].sum()) / 1000.0, 3) if len(lns) else 0.0,
        'feeders': feeders,
        'warnings': warnings,
        'points_path': p_fp,
        'lines_path': l_fp,
    }


if __name__ == '__main__':
    import sys, json
    args = sys.argv[1:] or ['GIS Base sheet.xls']
    srcs = [(p, p.split('/')[-1].split('\\')[-1]) for p in args]
    print(json.dumps(convert(srcs, 'outputs', 'merged_data'), indent=2))
