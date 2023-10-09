import logging
import traceback
from typing import Tuple, List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from skspatial.objects import Line
from .cpm_writer import CrowdSimulationEnvironment, Level
from .representation_helpers import WallVertices
from .preprocessors import convert_disconnected_walls_into_barricades, split_intersecting_elements, decompose_wall_with_openings, glue_connected_elements, close_wall_gaps

from .ifctypes import Barricade, WallWithOpening, Wall
from .walls import get_walls_by_storey
from .stairs import StairParser
from .utils import filter, get_sorted_building_storeys, truncate, get_oriented_xy_bounding_box, get_edge_from_bounding_box
from .geom_settings import settings


logger = logging.getLogger("IfcToCpmConverter")


class IfcToCpmConverterBuilder:
    def __init__(self, ifc_filepath: str):
        self.model = ifcopenshell.open(ifc_filepath)
        self.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(self.model)

    def get_buildings(self):
        buildings = []
        for ifc_building in self.model.by_type("IfcBuilding"):
            buildings.append(ifc_building.Name)
        return buildings

    def get_ifc_building(self, name=None):
        for ifc_building in self.model.by_type("IfcBuilding"):
            if name is None:
                return ifc_building
            if name == ifc_building.Name:
                return ifc_building

    def build(self, building_name: str = None, dimension: Tuple[int, int] = None, origin: Tuple[int, int] = None, round_function=None, close_wall_gap_metre=0, min_wall_height_metre=0.5, wall_offset_tolerance_metre=0.1):
        ifc_building = self.get_ifc_building(building_name)
        return IfcToCpmConverter(
            ifc_building=ifc_building,
            unit_scale=self.unit_scale,
            dimension=dimension,
            origin=origin,
            round_function=round_function,
            close_wall_gap_metre=close_wall_gap_metre,
            min_wall_height_metre=min_wall_height_metre,
            wall_offset_tolerance_metre=wall_offset_tolerance_metre
        )


class IfcToCpmConverter:
    def __init__(self, ifc_building, unit_scale, dimension: Tuple[int, int] = None, origin: Tuple[int, int] = None, round_function=None, close_wall_gap_metre=0, min_wall_height_metre=0.5, wall_offset_tolerance_metre=0.1):
        if origin is None:
            origin = (0, 0)

        self.ifc_building = ifc_building
        self.unit_scale = unit_scale
        self.crowd_environment = CrowdSimulationEnvironment(offset=origin, dimension=dimension, unit_scaler=lambda x: truncate(round(self.unit_scale * x * 100) / 100, digits=3))

        if round_function is not None:
            self.round = round_function
        else:
            self.round = lambda x: round(x * 100) / 100

        self.close_wall_gap_metre = close_wall_gap_metre
        self.storeys = get_sorted_building_storeys(ifc_building)

        min_wall_height = min_wall_height_metre / self.unit_scale  # Minimum wall height to be considered as a wall
        wall_offset_tolerance = wall_offset_tolerance_metre / self.unit_scale  # Maximum gap between the wall and level to be considered as a wall
        self.walls_map = get_walls_by_storey(ifc_building, min_wall_height=min_wall_height, wall_offset_tolerance=wall_offset_tolerance)

        self._parse_stairs()
        self._parse_storeys()

    def write(self, cpm_out_filepath):
        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def _parse_stairs(self):
        self.stairs = []
        for storey_id, storey in enumerate(self.storeys):
            building_elements = ifcopenshell.util.element.get_decomposition(storey)
            stairs_in_storey = [x for x in building_elements if x.is_a("IfcStair")]
            for stair_in_storey in stairs_in_storey:
                try:
                    stair = StairParser.from_ifc_stair(self.ifc_building, storey_id, stair_in_storey)
                    self.stairs.append(stair)
                    self.crowd_environment.add_stair(stair)
                except Exception as e:
                    logger.warning(f"Skipping stair parsing: error parsing stair {stair_in_storey.Name}: {e}")
                    logger.error(e, exc_info=True)

    def _parse_storeys(self):
        for storey_id, storey in enumerate(self.storeys):
            elements = self._get_storey_elements(storey_id, storey)
            level = Level(index=storey_id, elements=elements)
            self.crowd_environment.add_level(level)
            # return

    def _get_storey_elements(self, storey_id, storey):
        print(f"Processing storey: {storey_id} {storey.Name}")
        ifc_walls = self.walls_map[storey]
        building_elements = []
        for ifc_wall in ifc_walls:
            try:
                wall_with_opening = self._get_wall_with_opening(ifc_wall=ifc_wall, ifc_building_storey=storey)
                building_elements.append(wall_with_opening)
            except Exception as exc:
                logger.warning(f"Skipped wall parsing: error parsing wall {ifc_wall.Name}: {exc}")
                logger.error(exc, exc_info=True)

        tolerance = self.close_wall_gap_metre / self.unit_scale

        if tolerance > 0:
            print("Glueing wall connections...")
            building_elements = glue_connected_elements(elements=building_elements, tolerance=tolerance)

        print("Decomposing wall openings...")
        building_elements = decompose_wall_with_openings(building_elements)

        print("Splitting intersections...")
        building_elements = split_intersecting_elements(building_elements)

        if tolerance > 0:
            print("Closing wall gaps...")
            building_elements = close_wall_gaps(building_elements, tolerance=tolerance)
        building_elements = convert_disconnected_walls_into_barricades(building_elements)
        # building_elements += self._get_storey_void_barricade_elements(storey)
        building_elements += self._get_storey_stair_border_walls(storey_id)
        return building_elements

    def _get_storey_stair_border_walls(self, storey_id):
        walls: List[Wall] = []
        stairs_voiding_storey = filter(self.stairs, lambda s: storey_id > s.start_level_index and storey_id <= s.end_level_index)
        stairs_departing_in_storey = filter(self.stairs, lambda s: s.start_level_index == storey_id)
        stairs_arriving_in_storey = filter(self.stairs, lambda s: s.end_level_index == storey_id)

        stairs_edges = set()
        for stair in stairs_departing_in_storey:
            stairs_edges.add(stair.lower_gate)
            stairs_edges.add(stair.first_wall)
            stairs_edges.add(stair.second_wall)
            stairs_edges.add(stair.upper_gate)
        for stair in stairs_arriving_in_storey:
            stairs_edges.add(stair.upper_gate)

        for stair in stairs_voiding_storey:
            if stair.lower_gate not in stairs_edges:
                # Draw a wall where the lower gate is
                # But, do NOT draw if there a gate in the position of the wall that belongs to another stair
                walls += [Wall(start_vertex=stair.lower_gate[0], end_vertex=stair.lower_gate[1])]

            if stair.first_wall not in stairs_edges:
                walls += [Wall(start_vertex=stair.first_wall[0], end_vertex=stair.first_wall[1])]

            if stair.second_wall not in stairs_edges:
                walls += [Wall(start_vertex=stair.second_wall[0], end_vertex=stair.second_wall[1])]

            if stair.upper_gate not in stairs_edges:
                # Draw a wall where the upper gate is
                walls += [Wall(start_vertex=stair.upper_gate[0], end_vertex=stair.upper_gate[1])]

        return walls

    def _get_wall_with_opening(self, ifc_wall, ifc_building_storey) -> WallWithOpening:
        print("Inferring wall vertices for wall " + ifc_wall.Name)
        start_vertex, end_vertex = WallVertices.from_product(ifc_wall)
        start_vertex = truncate(start_vertex[0]), truncate(start_vertex[1])
        end_vertex = truncate(end_vertex[0]), truncate(end_vertex[1])

        opening_geometries = []
        elevation = ifcopenshell.util.placement.get_storey_elevation(ifc_building_storey)
        tolerance = 0.02 / self.unit_scale  # Tolerance is 2cm

        # Parse openings
        openings = ifc_wall.HasOpenings
        for opening in openings:
            opening_element = opening.RelatedOpeningElement
            if opening_element.PredefinedType is None or opening_element.PredefinedType.upper() != 'RECESS':
                try:
                    shape = ifcopenshell.geom.create_shape(settings, opening_element)
                    min_z = min(shape.geometry.verts[2::3])
                    max_z = max(shape.geometry.verts[2::3])

                    opening_is_likely_a_door = min_z <= elevation + tolerance
                    if not opening_is_likely_a_door or max_z < elevation:
                        continue

                    opening_geometries.append((shape))
                except Exception as e:
                    logger.warning(f"Skipping opening parsing: error parsing opening {opening_element.Name}: {e}")
                    logger.error(e, exc_info=True)

        # Parse doors without opening
        ifc_doors = [x for x in ifcopenshell.util.element.get_decomposition(ifc_wall) if x.is_a("IfcDoor")]
        for ifc_door in ifc_doors:
            opening_container = ifcopenshell.util.element.get_container(ifc_door, "IfcOpeningElement")
            if opening_container:
                continue

            try:
                shape = ifcopenshell.geom.create_shape(settings, ifc_door)
                min_z = min(shape.geometry.verts[2::3])
                max_z = max(shape.geometry.verts[2::3])

                door_in_storey = min_z <= elevation + tolerance
                if not door_in_storey or max_z < elevation:
                    continue

                opening_geometries.append((shape))
            except Exception as e:
                logger.warning(f"Skipping door parsing: error parsing door {ifc_door.Name}: {e}")
                logger.error(e, exc_info=True)

        # Project vertices into wall for alignment
        opening_vertices = []
        for shape in opening_geometries:
            vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
            bbox = get_oriented_xy_bounding_box(vertices)
            v1, v2 = get_edge_from_bounding_box(bbox)

            wall_line = Line.from_points(start_vertex, end_vertex)
            x1, y1 = wall_line.project_point(v1)
            x2, y2 = wall_line.project_point(v2)

            x1, y1 = truncate(x1), truncate(y1)
            x2, y2 = truncate(x2), truncate(y2)
            opening_vertices.append(((x1, y1), (x2, y2)))

        print("Finished inferring wall " + ifc_wall.Name)

        connected_to = [(x.RelatedElement.GlobalId, x.RelatingConnectionType) for x in ifc_wall.ConnectedTo]
        return WallWithOpening(object_id=ifc_wall.GlobalId, name=ifc_wall.Name, start_vertex=start_vertex, end_vertex=end_vertex, opening_vertices=opening_vertices, connected_to=connected_to)
