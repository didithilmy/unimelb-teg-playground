from lib.IfcToCpmConverter import IfcToCpmConverterBuilder

# IfcToCpmConverter("institute.ifc", origin=(10, 10)).write("institute.cpm")
IfcToCpmConverterBuilder("ifc/house.ifc").build(origin=(10, 10)).write("cpm/house3.cpm")
