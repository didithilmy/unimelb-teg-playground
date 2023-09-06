from lib.IfcToCpmConverter import IfcToCpmConverterBuilder

# IfcToCpmConverterBuilder("ifc/house.ifc").build(origin=(5, 5)).write("cpm/house.cpm")
# IfcToCpmConverterBuilder("ifc/institute.ifc").build(round_function=lambda x:x).write("cpm/institute.cpm")
# IfcToCpmConverterBuilder("ifc/Project3.ifc").build(origin=(30, 30)).write("cpm/Project3.cpm")
# IfcToCpmConverterBuilder("ifc/ProjectTest-2x3-Coord.ifc").build().write("cpm/ProjectTest-2x3-Coord.cpm")
IfcToCpmConverterBuilder("ifc/ProjectTest-4-Arch.ifc").build().write("cpm/ProjectTest-4-Arch.cpm")
# IfcToCpmConverterBuilder("ifc/ProjectTest-4x3.ifc").build().write("cpm/ProjectTest-4x3.cpm")
