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
from .representation_helpers import XYBoundingBox, Extrusion2DVertices, WallVertices
from .preprocessors import convert_disconnected_walls_into_barricades, split_intersecting_elements, decompose_wall_with_openings, glue_connected_elements, close_wall_gaps

from .ifctypes import Barricade, WallWithOpening, Wall
from .stairs import StraightSingleRunStairBuilder
from .utils import transform_vertex, filter, get_sorted_building_storeys, truncate, get_oriented_xy_bounding_box, get_edge_from_bounding_box

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)
settings.set(settings.CONVERT_BACK_UNITS, True)

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

    def build(
        self,
        building_name: str = None,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
        round_function=None,
        close_wall_gap_metre=0
    ):
        ifc_building = self.get_ifc_building(building_name)
        return IfcToCpmConverter(
            ifc_building=ifc_building,
            unit_scale=self.unit_scale,
            dimension=dimension,
            origin=origin,
            round_function=round_function,
            close_wall_gap_metre=close_wall_gap_metre
        )


class IfcToCpmConverter:
    def __init__(
        self,
        ifc_building,
        unit_scale,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
        round_function=None,
        close_wall_gap_metre=0
    ):
        if origin is None:
            origin = (0, 0)

        self.ifc_building = ifc_building
        self.unit_scale = unit_scale
        self.crowd_environment = CrowdSimulationEnvironment(offset=origin, dimension=dimension, unit_scaler=lambda x: truncate(round(self.unit_scale * x * 100) / 100, digits=3))

        building_transformation_matrix = ifcopenshell.util.placement.get_local_placement(ifc_building.ObjectPlacement)
        self.base_transformation_matrix = np.linalg.inv(building_transformation_matrix)

        if round_function is not None:
            self.round = round_function
        else:
            self.round = lambda x: round(x * 100) / 100

        self.close_wall_gap_metre = close_wall_gap_metre
        self.storeys = get_sorted_building_storeys(ifc_building)

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
                    stair = StraightSingleRunStairBuilder(self.ifc_building, storey_id, stair_in_storey).build()
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
        elements = ifcopenshell.util.element.get_decomposition(storey)
        walls = [x for x in elements if x.is_a("IfcWall") or x.is_a("IfcCurtainWall")]
        building_elements = []
        for wall in walls:
            try:
                wall_with_opening = self._get_wall_with_opening(wall)
                building_elements.append(wall_with_opening)
            except Exception as exc:
                logger.warning(f"Skipped wall parsing: error parsing wall {wall.Name}: {exc}")
                logger.error(exc, exc_info=True)

        tolerance = self.close_wall_gap_metre / self.unit_scale

        if tolerance > 0:
            print("Glueing wall connections...")
            building_elements = glue_connected_elements(elements=building_elements, tolerance=tolerance)

        import json
        with open(f'building_elements_{storey_id}.json', 'w') as f:
            f.write(json.dumps([x.__dict__ for x in building_elements], indent=4))

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
        for stair in stairs_voiding_storey:
            if storey_id > stair.start_level_index:
                # Draw a wall where the lower gate is
                walls += [Wall(start_vertex=stair.lower_gate[0], end_vertex=stair.lower_gate[1])]

            walls += [
                Wall(start_vertex=stair.first_wall[0], end_vertex=stair.first_wall[1]),
                Wall(start_vertex=stair.second_wall[0], end_vertex=stair.second_wall[1])
            ]

            if storey_id < stair.end_level_index:
                # Draw a wall where the upper gate is
                walls += [Wall(start_vertex=stair.upper_gate[0], end_vertex=stair.upper_gate[1])]

        return walls
    
    def _get_wall_with_opening(self, ifc_wall) -> WallWithOpening:
        print("Inferring wall vertices for wall " + ifc_wall.Name)
        start_vertex, end_vertex = WallVertices.from_product(ifc_wall)

        opening_vertices = []
        openings = ifc_wall.HasOpenings
        for opening in openings:
            opening_element = opening.RelatedOpeningElement
            if opening_element.PredefinedType is None or opening_element.PredefinedType.upper() != 'RECESS':
                shape = ifcopenshell.geom.create_shape(settings, opening_element)

                opening_location_relative_to_wall = opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
                _, _, z = opening_location_relative_to_wall
                if z > 0:
                    continue

                vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)

                bbox = get_oriented_xy_bounding_box(vertices)
                v1, v2 = get_edge_from_bounding_box(bbox)

                matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
                v1 = self._transform_vertex(v1, matrix)
                v2 = self._transform_vertex(v2, matrix)

                wall_line = Line.from_points(start_vertex, end_vertex)
                x1, y1 = wall_line.project_point(v1)
                x2, y2 = wall_line.project_point(v2)

                x1, y1 = truncate(x1), truncate(y1)
                x2, y2 = truncate(x2), truncate(y2)
                opening_vertices.append(((x1, y1), (x2, y2)))

        print("Finished inferring wall " + ifc_wall.Name)

        connected_to = [(x.RelatedElement.GlobalId, x.RelatingConnectionType) for x in ifc_wall.ConnectedTo]
        return WallWithOpening(object_id=ifc_wall.GlobalId, name=ifc_wall.Name, start_vertex=start_vertex, end_vertex=end_vertex, opening_vertices=opening_vertices, connected_to=connected_to)


    def _get_storey_void_barricade_elements(self, storey):
        elements = ifcopenshell.util.element.get_decomposition(storey)
        slabs = [x for x in elements if x.is_a("IfcSlab")]
        floor_slabs = [x for x in slabs if x.PredefinedType == "FLOOR"]

        elements = []
        if len(floor_slabs) > 0:
            floor_slab = floor_slabs[0]
            floor_openings = floor_slab.HasOpenings
            for floor_opening in floor_openings:
                opening_element = floor_opening.RelatedOpeningElement
                representations = opening_element.Representation.Representations

                transformation_matrix = ifcopenshell.util.placement.get_local_placement(
                    opening_element.ObjectPlacement
                )

                edges = Extrusion2DVertices.infer(representations)

                for i in range(len(edges)):
                    v1, v2 = edges[i]
                    v1_transform = self._transform_vertex(v1, transformation_matrix)
                    v2_transform = self._transform_vertex(v2, transformation_matrix)
                    elements.append(
                        Barricade(
                            name=f"{opening_element.Name}-{i}",
                            start_vertex=v1_transform,
                            end_vertex=v2_transform,
                        )
                    )

        return elements

    def _transform_vertex(self, vertex, transformation_matrix):
        # Building location correction
        total_transformation_matrix = np.dot(self.base_transformation_matrix, transformation_matrix)
        transformed_x, transformed_y = transform_vertex(total_transformation_matrix, vertex)
        transformed_x = self.round(transformed_x)
        transformed_y = self.round(transformed_y)
        return (transformed_x, transformed_y)
