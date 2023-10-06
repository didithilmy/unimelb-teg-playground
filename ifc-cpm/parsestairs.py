import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.shape
import ifcopenshell.util.representation
from lib.utils import find_unbounded_lines_intersection, eucledian_distance, find, filter, get_composite_verts, get_oriented_xy_bounding_box, calculate_line_angle_relative_to_north, rotate_point_around_point

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.CONVERT_BACK_UNITS, True)
settings.set(settings.INCLUDE_CURVES, True)

model = ifcopenshell.open("ifc/rac_advanced_sample_project.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


def parse_stair(ifc_stair):
    elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
    stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))
    # assert len(stair_flights) == 1, "There should be exactly one stair flight"

    verts = get_composite_verts(ifc_stair)
    bbox = get_oriented_xy_bounding_box(verts)
    footprint_v1, footprint_v2, footprint_v3, footprint_v4 = bbox
    edges = [
        (footprint_v1, footprint_v2),
        (footprint_v2, footprint_v3),
        (footprint_v3, footprint_v4),
        (footprint_v4, footprint_v1),
    ]

    run_edge = calculate_resultant_run_line(stair_flights)
    run_start_vertex, run_end_vertex = run_edge

    edge1, edge2, edge3, edge4 = edges
    edge1_int = find_unbounded_lines_intersection(run_edge, edge1)
    edge2_int = find_unbounded_lines_intersection(run_edge, edge2)
    edge3_int = find_unbounded_lines_intersection(run_edge, edge3)
    edge4_int = find_unbounded_lines_intersection(run_edge, edge4)

    edges_map = {
        edge1: dict(edge=edge1, intersection=edge1_int, designation="WALL"),
        edge2: dict(edge=edge2, intersection=edge2_int, designation="WALL"),
        edge3: dict(edge=edge3, intersection=edge3_int, designation="WALL"),
        edge4: dict(edge=edge4, intersection=edge4_int, designation="WALL"),
    }

    edges_with_intersection = filter(edges_map.values(), matcher=lambda x: x['intersection'] is not None)

    closest_to_run_start = min(edges_with_intersection, key=lambda x: eucledian_distance(x['intersection'], run_start_vertex))
    closest_to_run_start['designation'] = "BOTTOM_GATE"
    closest_to_run_end = min(edges_with_intersection, key=lambda x: eucledian_distance(x['intersection'], run_end_vertex))
    closest_to_run_end['designation'] = "TOP_GATE"

    lower_gate = find(edges_map.values(), lambda x: x['designation'] == 'BOTTOM_GATE')
    side_walls = filter(edges_map.values(), lambda x: x['designation'] == 'WALL')

    floor_span = 1

    run_length = eucledian_distance(run_start_vertex, run_end_vertex)
    run_rotation = int(round(calculate_line_angle_relative_to_north(run_start_vertex, run_end_vertex)))
    staircase_width = eucledian_distance(lower_gate['edge'][0], lower_gate['edge'][1])

    # Staircase origin must be to the LEFT of the run axis.
    staircase_origin = determine_origin_vertex(lower_gate, run_rotation)

    psets = ifcopenshell.util.element.get_psets(ifc_stair)
    no_of_treads = psets['Pset_StairCommon'].get("NumberOfTreads")

    print("Parsed stair", ifc_stair.Name)
    print("    Origin:", staircase_origin)
    print("    Run length:", run_length)
    print("    Run angle:", run_rotation)
    print("    Staircase width:", staircase_width)


def calculate_resultant_run_line(stair_flights):
    run_edges = []

    # TODO Need to ensure stair flights are sorted by elevation
    for stair_flight in stair_flights:
        axis_repr = ifcopenshell.util.representation.get_representation(stair_flight, "Model", "Axis")
        assert axis_repr is not None, "There should be a Axis representation"

        shape = ifcopenshell.geom.create_shape(settings, axis_repr)
        run_edge = ifcopenshell.util.shape.get_vertices(shape)
        run_edge = [(x[0], x[1]) for x in run_edge]
        run_edges.append(run_edge)

    first_edge = run_edges[0]
    last_edge = run_edges[-1]
    v1 = first_edge[0]
    v2 = last_edge[1]
    return v1, v2

def determine_origin_vertex(lower_gate, run_rotation):
        lv1, lv2 = lower_gate['edge']
        intersection = lower_gate['intersection']

        # Counter-rotate vertex around intersection
        lv1_rotated_x, _ = rotate_point_around_point(intersection, lv1, -run_rotation)
        lv2_rotated_x, _ = rotate_point_around_point(intersection, lv2, -run_rotation)

        # Determine which one is the left one
        if lv1_rotated_x < lv2_rotated_x:
            return lv1

        return lv2

def process_stair(ifc_stair):
    elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
    stair_flights = [x for x in elements if x.is_a("IfcStairFlight")]
    run_edge = calculate_resultant_run_line(stair_flights)
    print(ifc_stair.Name, run_edge)


for storey in model.by_type("IfcBuildingStorey"):
    print(storey.Name)
    elements = ifcopenshell.util.element.get_decomposition(storey)
    stairs = [x for x in elements if x.is_a("IfcStair")]
    for stair in stairs:
        parse_stair(stair)
