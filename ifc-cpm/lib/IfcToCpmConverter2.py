import logging
import traceback
from typing import Tuple, List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from .cpm_writer import CrowdSimulationEnvironment, Level
from .representation_helpers import XYBoundingBox, Extrusion2DVertices, WallVertices

from .stairs import StraightSingleRunStairBuilder
from .utils import transform_vertex, filter, get_sorted_building_storeys
from .walls import WallWithOpening, get_walls_by_storey, infer_wall_connections, glue_connected_walls, decompose_wall_with_openings, convert_disconnected_walls_into_barricades
from .preprocessors import split_intersecting_elements

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)

logger = logging.getLogger("IfcToCpmConverter")


def DEFAULT_ROUND_FUNCTION(x): return round(x * 100) / 100


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

    def build(self, building_name: str = None, dimension: Tuple[int, int] = None, origin: Tuple[int, int] = (0, 0), round_function=None, close_wall_gap_metre=None):
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
    def __init__(self, ifc_building, unit_scale, dimension: Tuple[int, int] = None, origin: Tuple[int, int] = (0, 0), round_function=DEFAULT_ROUND_FUNCTION, close_wall_gap_metre=None):
        self.ifc_building = ifc_building
        self.unit_scale = unit_scale
        self.crowd_environment = CrowdSimulationEnvironment(offset=origin, dimension=dimension, unit_scaler=lambda x: round(self.unit_scale * x * 100) / 100)
        self.round = round_function

        self.close_wall_gap_metre = close_wall_gap_metre
        self.storeys = get_sorted_building_storeys(ifc_building)
        self.walls_map = get_walls_by_storey(ifc_building)
        self.stairs = self.get_stairs()

        for storey_id, storey in enumerate(self.storeys):
            elements = self.get_storey_elements(storey)
            level = Level(index=storey_id, elements=elements)
            self.crowd_environment.add_level(level)

    def write(self, cpm_out_filepath):
        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def get_stairs(self) -> List[StraightSingleRunStairBuilder]:
        stairs = []
        for storey_id, storey in enumerate(self.storeys):
            building_elements = ifcopenshell.util.element.get_decomposition(storey)
            stairs_in_storey = [x for x in building_elements if x.is_a("IfcStair")]
            for stair_in_storey in stairs_in_storey:
                try:
                    stair = StraightSingleRunStairBuilder(self.ifc_building, storey_id, stair_in_storey).build()
                    stairs.append(stair)
                except Exception as e:
                    logger.warning(f"Skipping stair parsing: error parsing stair {stair_in_storey.Name}: {e}")
                    logger.error(e, exc_info=True)
        return stairs

    def get_storey_elements(self, ifc_building_storey):
        storey_index = self.storeys.index(ifc_building_storey)
        walls = self.walls_map[ifc_building_storey]
        building_elements = []
        for (ifc_wall, wall_with_opening) in walls:
            building_elements.append(wall_with_opening)

        tolerance = None
        if self.close_wall_gap_metre is not None:
            tolerance = self.close_wall_gap_metre / self.unit_scale
            print("Inferring wall connections...")
            building_elements = infer_wall_connections(tolerance, building_elements)

        print("Glueing wall connections...")
        building_elements = glue_connected_walls(building_elements, tolerance=tolerance)

        print("Decomposing wall openings...")
        building_elements = decompose_wall_with_openings(building_elements)

        # print("Splitting intersections...")
        # building_elements = split_intersecting_elements(building_elements)
        # building_elements = convert_disconnected_walls_into_barricades(building_elements)
        # building_elements += self._get_storey_void_barricade_elements(storey)
        # building_elements += self._get_storey_stair_border_walls(storey_index)
        return building_elements
