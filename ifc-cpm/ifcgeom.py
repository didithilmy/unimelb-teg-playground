import ifcopenshell
import ifcopenshell.geom as geom

settings = geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

f = ifcopenshell.open('house.ifc')
for obj in f.by_type('IfcProduct'):
    shape = ifcopenshell.geom.create_shape(settings, obj)
    geo = shape.geometry

    print(geo.verts)
    print(geo.edges)
    print(geo.faces)