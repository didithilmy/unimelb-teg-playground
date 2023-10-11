import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.shape
import ifcopenshell.util.representation
from lib.utils import find_unbounded_lines_intersection, eucledian_distance, find, filter, get_composite_verts, get_oriented_xy_bounding_box, calculate_line_angle_relative_to_north, rotate_point_around_point, truncate
from lib.ifctypes import StraightSingleRunStair
from lib.stairs import StairsWithLandingBuilder

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.CONVERT_BACK_UNITS, True)
settings.set(settings.INCLUDE_CURVES, True)

model = ifcopenshell.open("ifc/rac_advanced_sample_project.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

ifc_building = model.by_type("IfcBuilding")[0]

for storey in model.by_type("IfcBuildingStorey"):
    print(storey.Name)
    elements = ifcopenshell.util.element.get_decomposition(storey)
    stairs = [x for x in elements if x.is_a("IfcStair") and '173290' in x.Name]
    for ifc_stair in stairs:
        stair = StairsWithLandingBuilder(ifc_building, start_level_index=0, ifc_stair=ifc_stair).build()
        print("Pivot:", stair.vertex)
        print("Run length:", stair.run_length)
        print("Run width:", stair.staircase_width)
        print("Run rotation:", stair.rotation)
