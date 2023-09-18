import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lib.ifctypes import Wall, Gate, BuildingElement
from lib.representation_helpers import Extrusion2DVertices
from lib.utils import find

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)

model = ifcopenshell.open("ifc/WithEscalator.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    escalators = [x for x in elements if x.is_a("IfcTransportElement") and x.PredefinedType == 'ESCALATOR']

    print(storey.Name)
    for escalator in escalators:
        representations = (escalator.Representation.Representations)
        vertices = Extrusion2DVertices.infer(representations)
        transformation_matrix = ifcopenshell.util.placement.get_local_placement(
            escalator.ObjectPlacement
        )

        psets = ifcopenshell.util.element.get_psets(escalator)
        # print(psets)

        body_repr = find(representations, matcher=lambda r: r.RepresentationIdentifier == 'Body')

        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, escalator)
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
        print(vertices[:-10])

        print()
