import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from .utils import find, filter, find_unbounded_lines_intersection, eucledian_distance, calculate_line_angle_relative_to_north, get_sorted_building_storeys, rotate_point_around_point
from .ifctypes import StraightSingleRunStair


class StraightSingleRunStairBuilder:
    def __init__(self, ifc_building, start_level_index, ifc_stair):
        self.ifc_building = ifc_building
        self.start_level_index = start_level_index
        self.ifc_stair = ifc_stair

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
        psets = ifcopenshell.util.element.get_psets(stair_flight)
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

        # Staircase origin must be to the LEFT of the run axis.
        staircase_origin = self._determine_origin_vertex(lower_gate, run_rotation)

        return StraightSingleRunStair(
            object_id=ifc_stair.GlobalId,
            rotation=run_rotation,
            vertex=staircase_origin,
            staircase_width=staircase_width,
            run_length=run_length,
            no_of_treads=psets['Pset_StairFlightCommon'].get("NumberOfTreads"),
            start_level_index=self.start_level_index,
            end_level_index=self.start_level_index + floor_span,
        )

    def _determine_straight_run_stair_floor_span(self, ifc_stair) -> int:
        storey = ifcopenshell.util.element.get_container(ifc_stair)
        building_storeys = get_sorted_building_storeys(self.ifc_building)

        elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))
        assert len(stair_flights) == 1, "There should be exactly one stair flight"

        stair_flight = stair_flights[0]
        psets = ifcopenshell.util.element.get_psets(stair_flight)
        pset_stairflight = psets['Pset_StairFlightCommon']
        run_height = pset_stairflight.get("NumberOfRiser", 1) * pset_stairflight.get("RiserHeight", 1)

        starting_elevation = storey.Elevation
        ending_elevation = starting_elevation + run_height
        
        # Sometimes the staircase and floor elevation is slightly different due to rounding error. 
        tolerance = 0.005 * (ending_elevation - starting_elevation)

        # The containing storey is purposefully excluded.
        storeys_in_stair = filter(building_storeys, matcher=lambda s: s.Elevation > starting_elevation + tolerance and s.Elevation <= ending_elevation + tolerance)

        return len(storeys_in_stair)

    def _determine_origin_vertex(self, lower_gate, run_rotation):
        lv1, lv2 = lower_gate['edge']
        intersection = lower_gate['intersection']

        # Counter-rotate vertex around intersection
        lv1_rotated_x, _ = rotate_point_around_point(intersection, lv1, -run_rotation)
        lv2_rotated_x, _ = rotate_point_around_point(intersection, lv2, -run_rotation)

        # Determine which one is the left one
        if lv1_rotated_x < lv2_rotated_x:
            return lv1

        return lv2
