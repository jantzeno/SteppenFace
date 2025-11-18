import sys
import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union, polygonize, linemerge, snap

ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

def parse_points(points_str):
    pts = []
    for item in points_str.strip().split():
        if not item:
            continue
        if ',' in item:
            x, y = item.split(',')
        else:
            x, y = item.split()
        pts.append((float(x), float(y)))
    return pts

def ring_to_d(coords):
    return "M " + " L ".join(f"{x:.6f} {y:.6f}" for x, y in coords) + " Z"

def main(in_svg, out_svg):
    tree = ET.parse(in_svg)
    root = tree.getroot()
    
    face_name = in_svg.split('/')[-1].replace('.svg', '')

    polys = root.findall('.//{http://www.w3.org/2000/svg}polyline')
    if not polys:
        polys = root.findall('.//polyline')

    if not polys:
        print("No polylines found")
        return

    lines = []
    for p in polys:
        pts = parse_points(p.get('points', ''))
        if len(pts) >= 2:
            lines.append(LineString(pts))

    if not lines:
        print("No valid polylines")
        return

    print(f"Found {len(lines)} polylines")
    
    merged = unary_union(lines)
    
    minx, miny, maxx, maxy = merged.bounds
    diag = ((maxx - minx)**2 + (maxy - miny)**2) ** 0.5
    
    polygons = []
    tols = [diag * f for f in (1e-6, 1e-4, 1e-3, 5e-3, 1e-2)]
    
    for tol in tols:
        snapped = snap(merged, merged, tol)
        snapped = linemerge(snapped)
        snapped_union = unary_union(snapped)
        polys_temp = list(polygonize(snapped_union))
        if polys_temp:
            polygons = polys_temp
            break
        buffered = snapped_union.buffer(tol / 2)
        polys_temp = list(polygonize(buffered))
        if polys_temp:
            polygons = polys_temp
            break

    if not polygons:
        print("Could not create closed polygons")
        return

    for p in polys:
        root.remove(p)

    outer_all = []
    for i, p_i in enumerate(polygons):
        contained = False
        for j, p_j in enumerate(polygons):
            if i != j and p_j.contains(p_i):
                contained = True
                break
        if not contained:
            outer_all.append(p_i)

    if not outer_all:
        print("No outer polygon found")
        return

    if len(outer_all) > 1:
        face_group = ET.Element('{http://www.w3.org/2000/svg}g', {'id': face_name})
        root.append(face_group)
        parent = face_group
    else:
        parent = root

    for idx, outer in enumerate(outer_all):
        holes = [list(p.exterior.coords) for p in polygons if p != outer and outer.contains(p)]
        d = ring_to_d(outer.exterior.coords)
        for hole_coords in holes:
            d += " " + ring_to_d(hole_coords)

        path_id = f"{face_name}_{idx}" if len(outer_all) > 1 else face_name
        
        new_el = ET.Element('{http://www.w3.org/2000/svg}path', {
            'id': path_id,
            'd': d,
            'fill': 'none',
            'stroke': 'black',
            'stroke-width': '1',
            'fill-rule': 'evenodd'
        })
        parent.append(new_el)
    
    tree.write(out_svg, encoding='utf-8', xml_declaration=True)
    print(f"Wrote {len(outer_all)} closed polygon(s) to {out_svg}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: svg_to_polygon.py input.svg output.svg")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
