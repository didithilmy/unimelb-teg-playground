from enum import Enum
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.shape
from .utils import find, filter, find_unbounded_lines_intersection, eucledian_distance, calculate_line_angle_relative_to_north, get_sorted_building_storeys, rotate_point_around_point, get_oriented_xy_bounding_box, get_composite_verts, smallest_angle_difference
from .ifctypes import StraightSingleRunStair, DoubleRunStairWithLanding

settings = ifcopenshell.geom.settings()
settings.set(settings.CONVERT_BACK_UNITS, True)
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.INCLUDE_CURVES, True)


def _calculate_resultant_run_line(run_edges):
    first_edge = run_edges[0]
    last_edge = run_edges[-1]
    v1 = first_edge[0]
    v2 = last_edge[1]
    return v1, v2


def _get_flights_run_edges(stair_flights):
    run_edges = []

    # TODO Need to ensure stair flights are sorted by elevation
    for stair_flight in stair_flights:
        axis_repr = ifcopenshell.util.representation.get_representation(stair_flight, "Model", "Axis")
        assert axis_repr is not None, "There should be a Axis representation"

        shape = ifcopenshell.geom.create_shape(settings, axis_repr)
        run_edge = ifcopenshell.util.shape.get_vertices(shape)
        run_edge = [(x[0], x[1]) for x in run_edge]
        run_edges.append(run_edge)

    return run_edges


def _determine_stair_floor_span(ifc_building, ifc_stair) -> int:
    # return 1 # FIXME remove
    storey = ifcopenshell.util.element.get_container(ifc_stair, "IfcBuildingStorey")
    building_storeys = get_sorted_building_storeys(ifc_building)

    psets = ifcopenshell.util.element.get_psets(ifc_stair)
    pset_stair = psets['Pset_StairCommon']
    run_height = pset_stair.get("NumberOfRiser", 1) * pset_stair.get("RiserHeight", 1)

    starting_elevation = ifcopenshell.util.placement.get_storey_elevation(storey)
    ending_elevation = starting_elevation + run_height

    # Sometimes the staircase and floor elevation is slightly different due to rounding error.
    tolerance = 0.1 * run_height

    def is_storey_voided_by_stair(ifc_storey):
        elevation = ifcopenshell.util.placement.get_storey_elevation(ifc_storey)
        return elevation >= starting_elevation - tolerance and elevation <= ending_elevation + tolerance

    storeys_in_stair = filter(building_storeys, matcher=is_storey_voided_by_stair)

    return len(storeys_in_stair) - 1


class StairType(Enum):
    STRAIGHT_SINGLE_RUN = 1
    U_TURN_WITH_LANDING = 2


class StairParser:
    @staticmethod
    def from_ifc_stair(ifc_building, start_level_index, ifc_stair):
        stair_type = StairParser.infer_stair_type(ifc_stair)
        if stair_type == StairType.STRAIGHT_SINGLE_RUN:
            stair = StraightSingleRunStairBuilder(ifc_building, start_level_index, ifc_stair).build()
            if stair:
                return stair
        elif stair_type == StairType.U_TURN_WITH_LANDING:
            stair = DoubleRunStairWithLandingBuilder(ifc_building, start_level_index, ifc_stair).build()
            if stair:
                return stair

        if not stair_type:
            raise NotImplementedError(f"Cannot infer stair type from IfcProduct")

        raise NotImplementedError(f"Cannot parse stair {ifc_stair.Name}")

    @staticmethod
    def infer_stair_type(ifc_stair) -> StairType:
        stair_type = ifc_stair.PredefinedType
        if stair_type == "STRAIGHT_RUN_STAIR":
            return StairType.STRAIGHT_SINGLE_RUN

        elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))

        if len(stair_flights) >= 1:
            # TODO differentiate between U and straight
            if StairParser._is_stair_straight(ifc_stair):
                return StairType.STRAIGHT_SINGLE_RUN
            if StairParser._is_stair_u_turns(ifc_stair):
                return StairType.U_TURN_WITH_LANDING

    @staticmethod
    def _is_stair_straight(ifc_stair) -> bool:
        elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))
        run_edges = _get_flights_run_edges(stair_flights)
        resultant = _calculate_resultant_run_line(run_edges=run_edges)
        angle1 = calculate_line_angle_relative_to_north(*(run_edges[0]))
        angle2 = calculate_line_angle_relative_to_north(*resultant)

        angle_diff = abs(smallest_angle_difference(angle1, angle2))

        return angle_diff< 10  # Maximum to be considered straight is 10 degrees. TODO configure

    @staticmethod
    def _is_stair_u_turns(ifc_stair) -> bool:
        elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))
        run_edges = _get_flights_run_edges(stair_flights)
        resultant = _calculate_resultant_run_line(run_edges=run_edges)
        angle1 = calculate_line_angle_relative_to_north(*(run_edges[0]))
        angle2 = calculate_line_angle_relative_to_north(*resultant)

        angle_diff = abs(smallest_angle_difference(angle1, angle2))
        return 85 < angle_diff < 95


class StraightSingleRunStairBuilder:
    def __init__(self, ifc_building, start_level_index, ifc_stair):
        self.ifc_building = ifc_building
        self.start_level_index = start_level_index
        self.ifc_stair = ifc_stair

    def build(self):
        elements = ifcopenshell.util.element.get_decomposition(self.ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))

        verts = get_composite_verts(self.ifc_stair)
        bbox = get_oriented_xy_bounding_box(verts)
        footprint_v1, footprint_v2, footprint_v3, footprint_v4 = bbox
        edges = [
            (footprint_v1, footprint_v2),
            (footprint_v2, footprint_v3),
            (footprint_v3, footprint_v4),
            (footprint_v4, footprint_v1),
        ]

        run_edges = _get_flights_run_edges(stair_flights)
        run_edge = _calculate_resultant_run_line(run_edges)

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

        floor_span = _determine_stair_floor_span(self.ifc_building, self.ifc_stair)

        run_length = eucledian_distance(run_start_vertex, run_end_vertex)
        run_rotation = int(round(calculate_line_angle_relative_to_north(run_start_vertex, run_end_vertex)))
        staircase_width = eucledian_distance(lower_gate['edge'][0], lower_gate['edge'][1])

        # Staircase origin must be to the LEFT of the run axis.
        origin_x, origin_y = self._determine_origin_vertex(lower_gate, run_rotation)

        psets = ifcopenshell.util.element.get_psets(self.ifc_stair)
        no_of_treads = psets['Pset_StairCommon'].get("NumberOfTreads")

        return StraightSingleRunStair(
            object_id=self.ifc_stair.GlobalId,
            name=self.ifc_stair.Name,
            rotation=run_rotation,
            vertex=(origin_x, origin_y),
            staircase_width=staircase_width,
            run_length=run_length,
            no_of_treads=no_of_treads,
            start_level_index=self.start_level_index,
            end_level_index=self.start_level_index + floor_span,
        )

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


class DoubleRunStairWithLandingBuilder:
    def __init__(self, ifc_building, start_level_index, ifc_stair):
        self.ifc_building = ifc_building
        self.start_level_index = start_level_index
        self.ifc_stair = ifc_stair

    def build(self):
        elements = ifcopenshell.util.element.get_decomposition(self.ifc_stair)
        stair_flights = filter(elements, lambda x: x.is_a("IfcStairFlight"))

        verts = get_composite_verts(self.ifc_stair)
        bbox = get_oriented_xy_bounding_box(verts)
        footprint_v1, footprint_v2, footprint_v3, footprint_v4 = bbox
        edges = [
            (footprint_v1, footprint_v2),
            (footprint_v2, footprint_v3),
            (footprint_v3, footprint_v4),
            (footprint_v4, footprint_v1),
        ]

        run_edges = _get_flights_run_edges(stair_flights)
        resultant_run_edge = _calculate_resultant_run_line(run_edges)
        first_run_edge = run_edges[0]

        angle1 = calculate_line_angle_relative_to_north(*first_run_edge)
        angle2 = calculate_line_angle_relative_to_north(*resultant_run_edge)
        angle_between_resultant_and_first_run = smallest_angle_difference(angle1, angle2)
        is_clockwise = angle_between_resultant_and_first_run >= 0
        pivot, staircase_width, run_length = self._calculate_pivot_point(edges, first_run_edge, is_clockwise)
        run_angle = self._calculate_run_angle(first_run_edge, is_clockwise)

        psets = ifcopenshell.util.element.get_psets(self.ifc_stair)
        no_of_treads = psets['Pset_StairCommon'].get("NumberOfTreads")

        floor_span = _determine_stair_floor_span(self.ifc_building, self.ifc_stair)

        return DoubleRunStairWithLanding(
            object_id=self.ifc_stair.GlobalId,
            name=self.ifc_stair.Name,
            rotation=run_angle,
            vertex=pivot,
            staircase_width=staircase_width,
            run_length=run_length,
            no_of_treads=no_of_treads,
            start_level_index=self.start_level_index,
            end_level_index=self.start_level_index + floor_span,
        )

    def _calculate_pivot_point(self, footprint_edges, first_run_edge, is_clockwise):
        edges_intersections = [find_unbounded_lines_intersection(e, first_run_edge) for e in footprint_edges]

        def calc_distance_from_run_end_to_intersection(edge_and_intersection):
            edge, intersection = edge_and_intersection
            return eucledian_distance(intersection, first_run_edge[1]) if intersection else float('inf')

        closest_to_run_end, closest_to_run_end_intersection = min(zip(footprint_edges, edges_intersections), key=calc_distance_from_run_end_to_intersection)
        candidate_points = list(closest_to_run_end)
        if is_clockwise:
            # Farthest to the run end intersection
            pivot = max(candidate_points, key=lambda v: eucledian_distance(v, closest_to_run_end_intersection))
        else:
            # Closest to the run end intersection
            pivot = min(candidate_points, key=lambda v: eucledian_distance(v, closest_to_run_end_intersection))

        staircase_width = eucledian_distance(*closest_to_run_end)

        # If the wall is perfectly parallel, distance would be infinity. Otherwise, the wall with greatest intersection distance is likely to be the side wall
        farthest_to_run_end, _ = max(zip(footprint_edges, edges_intersections), key=calc_distance_from_run_end_to_intersection)
        side_wall = farthest_to_run_end
        run_length = eucledian_distance(*side_wall)
        return pivot, staircase_width, run_length

    def _calculate_run_angle(self, first_run_edge, is_clockwise):
        run_edge_angle = int(round(calculate_line_angle_relative_to_north(*first_run_edge)))
        return (run_edge_angle + 180 + 360) % 360
