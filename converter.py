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


# ---- main conversion --------------------------------------------------------
def read_sheet(xls_path, sheet=None):
    xls = pd.ExcelFile(xls_path)
    sn = sheet or xls.sheet_names[0]
    df = pd.read_excel(xls_path, sheet_name=sn)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def build_points(df):
    n = len(df)
    data = {}
    for col in POLE_COLS:
        if col in POLE_NOT_IN_EXCEL or col not in df.columns:
            data[col] = [None] * n
        elif col == 'S_Date':
            data[col] = [_yyyymmdd(v) for v in df[col]]
        elif col in POLE_FLOAT:
            data[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
        else:
            data[col] = [_clean(v) for v in df[col]]
    lat = pd.to_numeric(df['Latitude'], errors='coerce')
    lon = pd.to_numeric(df['Longitude'], errors='coerce')
    geom = [Point(x, y) if pd.notna(x) and pd.notna(y) else None
            for x, y in zip(lon, lat)]
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
    df = df.copy()
    df['P_Number'] = df['P_Number'].map(_clean)
    df = df[df['P_Number'].notna()]
    lat = pd.to_numeric(df['Latitude'], errors='coerce')
    lon = pd.to_numeric(df['Longitude'], errors='coerce')
    df = df[lat.notna() & lon.notna()]
    by_pn = {pn: row for pn, row in zip(df['P_Number'], df.to_dict('records'))}
    coord = {pn: T_4326_32645.transform(float(r['Longitude']), float(r['Latitude']))
             for pn, r in by_pn.items()}

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

    rows, geoms = [], []
    for fp, poles in feeders.items():
        # predecessor within this feeder only (trailing-int decrement = same branch)
        seq_pred = {pn: (_dec(pn) if (_dec(pn) in poles) else None) for pn in poles}
        seq_succ = {}
        for pn, sp in seq_pred.items():
            if sp is not None:
                seq_succ[sp] = pn

        def tap_of(pn):                          # parent pole the branch taps off
            s = _strip_seg(pn)
            while s is not None and s not in poles:
                if len(s) <= len(fp):            # never strip past the feeder prefix
                    return None
                s = _strip_seg(s)
            return s

        # one polyline per branch: a run of poles linked by trailing-integer
        # increment (e.g. 220-1 -> 220-2 -> 220-3), joined to its real parent pole
        # (e.g. 249-2-1 -> 249-2).  Poles are connected ONLY when they are serial;
        # unrelated structures (220-1 vs 234-1) are never joined.
        for h in [pn for pn in poles if seq_pred[pn] is None]:
            chain = [h]; cur = h
            while cur in seq_succ:
                cur = seq_succ[cur]; chain.append(cur)
            tap = tap_of(h)
            seq = ([tap] + chain) if tap is not None else chain
            pts = [coord[p] for p in seq]
            if len(pts) < 2:
                continue                         # lone pole (tap off the main feeder)
            line = LineString(pts)
            members = pd.DataFrame([by_pn[p] for p in chain])
            rows.append(line_attrs(members, line.length))
            geoms.append(line)

    gdf = gpd.GeoDataFrame(pd.DataFrame(rows, columns=LINE_COLS), geometry=geoms,
                           crs='EPSG:32645')
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


def convert(xls_path, out_dir, base_name, sheet=None):
    import os
    from shapely.ops import unary_union
    df = read_sheet(xls_path, sheet)
    pts = build_points(df)
    lns = build_lines(df)
    os.makedirs(out_dir, exist_ok=True)
    p_fp = os.path.join(out_dir, base_name + '_points.shp')
    l_fp = os.path.join(out_dir, base_name + '_lines.shp')
    pts.to_file(p_fp, driver='ESRI Shapefile', encoding='utf-8')
    lns.to_file(l_fp, driver='ESRI Shapefile', encoding='utf-8')
    _write_metadata(p_fp, base_name + ' points', 'point', len(pts))
    _write_metadata(l_fp, base_name + ' lines', 'curve', len(lns))

    # ---- data-quality warnings ----
    pn = pts['P_Number'].astype('string').str.strip()
    warnings = []
    miss = int(pts.geometry.isna().sum())
    blank = int(pn.isna().sum() | (pn == '').sum()) if len(pn) else 0
    blank = int((pn.isna() | (pn == '')).sum())
    dup = int(pn.notna().sum() - pn.nunique(dropna=True))
    if miss:
        warnings.append(f'{miss} row(s) had no/invalid Latitude-Longitude and produced no point.')
    if blank:
        warnings.append(f'{blank} pole(s) have a blank P_Number.')
    if dup:
        warnings.append(f'{dup} duplicate P_Number value(s) in the sheet.')
    off = 0
    if len(lns):
        u = unary_union(lns.geometry.values)
        pm = pts.to_crs('EPSG:32645')
        off = int((pm.geometry.apply(lambda g: g.distance(u) if g is not None else 0) >= 0.01).sum())
    if off:
        warnings.append(f'{off} pole(s) have no serial neighbour in the sheet, so they are '
                        f'points only (no line) - usually tap points off the main feeder.')

    return {
        'rows': int(len(df)),
        'points': int(len(pts)),
        'points_with_geom': int(pts.geometry.notna().sum()),
        'lines': int(len(lns)),
        'feeder_count': len(sorted(set(str(x).strip() for x in pts['F_Name'].dropna()))),
        'line_km': round(float(lns['Length_M'].sum()) / 1000.0, 3) if len(lns) else 0.0,
        'feeders': sorted(set(str(x).strip() for x in pts['F_Name'].dropna())),
        'warnings': warnings,
        'points_path': p_fp,
        'lines_path': l_fp,
    }


if __name__ == '__main__':
    import sys, json
    inp = sys.argv[1] if len(sys.argv) > 1 else 'GIS Base sheet.xls'
    print(json.dumps(convert(inp, 'outputs', 'GIS_Base_sheet'), indent=2))
