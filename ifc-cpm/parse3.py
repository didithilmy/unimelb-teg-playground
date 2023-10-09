from lib.IfcToCpmConverter import IfcToCpmConverterBuilder

# IfcToCpmConverterBuilder("ifc/house.ifc").build(origin=(5, 5)).write("cpm/house.cpm")
# IfcToCpmConverterBuilder("ifc/institute.ifc").build(round_function=lambda x:x).write("cpm/institute.cpm")
# IfcToCpmConverterBuilder("ifc/Project3.ifc").build(origin=(30, 30)).write("cpm/Project3.cpm")
# IfcToCpmConverterBuilder("ifc/Project1-2x3-Coord.ifc").build(origin=(5, 5)).write("cpm/Project1-2x3-Coord.cpm")
# IfcToCpmConverterBuilder("ifc/Project1-4-Structural.ifc").build(origin=(5, 5), close_wall_gap_metre=0.4).write("cpm/Project1-4-Structural.cpm")
# IfcToCpmConverterBuilder("ifc/Project1-4-Arch.ifc").build(origin=(5, 5), close_wall_gap_metre=0.4).write("cpm/Project1-4-Arch.cpm")
# IfcToCpmConverterBuilder("ifc/LargeBuilding1.ifc").build(origin=(5, 5), close_wall_gap_metre=0.4).write("cpm/LargeBuilding1.cpm")
# IfcToCpmConverterBuilder("ifc/LargeBuilding2.ifc").build(origin=(5, 5), close_wall_gap_metre=0.4).write("cpm/LargeBuilding2.cpm")
IfcToCpmConverterBuilder("ifc/rac_advanced_sample_project.ifc").build(origin=(5, 5), close_wall_gap_metre=0.2, min_wall_height_metre=0.8).write("cpm/rac_advanced_sample_project.cpm")
# IfcToCpmConverterBuilder("ifc/AdvancedProject.ifc").build(origin=(0, 0), close_wall_gap_metre=0.4).write("cpm/AdvancedProject.cpm")
# IfcToCpmConverterBuilder("ifc/ProjectTest-4-Arch.ifc").build().write("cpm/ProjectTest-4-Arch.cpm")
# IfcToCpmConverterBuilder("ifc/ProjectTest-4x3.ifc").build().write("cpm/ProjectTest-4x3.cpm")
