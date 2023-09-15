import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from .utils import find, filter, find_unbounded_lines_intersection, eucledian_distance, calculate_line_angle_relative_to_north
from .ifctypes import StraightSingleRunStair


class StraightSingleRunStairBuilder:
    def __init__(self, start_level_index, ifc_stair, vertex_normalizer=lambda x: x):
        self.start_level_index = start_level_index
        self.ifc_stair = ifc_stair
        self.vertex_normalizer = vertex_normalizer

    def build(self):
        stair_type = self.ifc_stair.PredefinedType
        if stair_type == "STRAIGHT_RUN_STAIR":
            return self._build_straight_run_stair(self.ifc_stair)

        raise NotImplementedError(f"Stair type {stair_type} is not yet implemented.")

    def _build_straight_run_stair(self, ifc_stair):
        elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))
        assert len(stair_flights) == 1, "There should be exactly one stair flight"

        stair_flight = stair_flights[0]
        representations = stair_flight.Representation.Representations
        footprint_repr = find(representations, lambda x: x.RepresentationIdentifier == 'FootPrint')
        assert footprint_repr is not None, "There should be a FootPrint representation"

        ifc_geometric_set = footprint_repr.Items[0]
        ifc_indexed_poly_curve = ifc_geometric_set.Elements[0]
        ifc_cartesian_point_list_2d = ifc_indexed_poly_curve.Points
        vertices = ifc_cartesian_point_list_2d.CoordList

        edges = []
        for i in range(len(vertices)):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % len(vertices)]
            if v1 != v2:
                edges.append((v1, v2))

        axis_repr = find(representations, lambda x: x.RepresentationIdentifier == 'Axis')
        assert axis_repr is not None, "There should be a Axis representation"

        ifc_geometric_set = axis_repr.Items[0]
        ifc_indexed_poly_curve = ifc_geometric_set.Elements[0]
        ifc_cartesian_point_list_2d = ifc_indexed_poly_curve.Points
        run_vertices = ifc_cartesian_point_list_2d.CoordList
        run_start_vertex, run_end_vertex = run_vertices

        edge1, edge2, edge3, edge4 = edges
        edge1_int = find_unbounded_lines_intersection(run_vertices, edge1)
        edge2_int = find_unbounded_lines_intersection(run_vertices, edge2)
        edge3_int = find_unbounded_lines_intersection(run_vertices, edge3)
        edge4_int = find_unbounded_lines_intersection(run_vertices, edge4)

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
        upper_gate = find(edges_map.values(), lambda x: x['designation'] == 'TOP_GATE')
        side_walls = filter(edges_map.values(), lambda x: x['designation'] == 'WALL')
        first_wall = side_walls[0]
        second_wall = side_walls[1]

        floor_span = self._determine_straight_run_stair_floor_span(ifc_stair)

        run_length = eucledian_distance(run_start_vertex, run_end_vertex)
        run_rotation = int(round(calculate_line_angle_relative_to_north(run_start_vertex, run_end_vertex)))
        staircase_width = eucledian_distance(lower_gate['edge'][0], lower_gate['edge'][1])

        # FIXME determine if this is a reliable way of getting the edge (e.g., the first vertex may not be the left side of the stair)
        # A correct representation in the crowd model must use the left side of the bottom gate as the stair vertex.
        staircase_origin = lower_gate['edge'][0]

        return StraightSingleRunStair(
            object_id=ifc_stair.GlobalId,
            rotation=run_rotation,
            vertex=staircase_origin,
            staircase_width=staircase_width,
            run_length=run_length,
            start_level_index=self.start_level_index,
            end_level_index=self.start_level_index + floor_span,
        )

    def _determine_straight_run_stair_floor_span(self, ifc_stair) -> int:
        return 1  # TODO infer from level height and bounding box
