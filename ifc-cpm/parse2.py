from lib.IfcToCpmConverter import IfcToCpmConverter

IfcToCpmConverter("house.ifc", origin=(10, 10)).write("house3.cpm")
