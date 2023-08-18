import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import OCC

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)
# settings.set(settings.USE_PYTHON_OPENCASCADE, True)
# settings.set(settings.INCLUDE_CURVES, True)

model = ifcopenshell.open('house.ifc')

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a('IfcWall')]
    print(f"There are {len(walls)} walls on storey {storey.Name}, they are:")
    for wall in walls:
        representations = wall.Representation.Representations
        axis_representation = [x for x in representations if x.RepresentationType == 'Curve2D'][0]
        shape = ifcopenshell.geom.create_shape(settings, wall)
        print(wall.Name, (axis_representation.Items[0].Points))