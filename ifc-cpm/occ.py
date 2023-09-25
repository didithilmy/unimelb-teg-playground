import os

import OCC.Core.gp
import OCC.Core.Geom
import OCC.Extend.TopologyUtils
import OCC.Core.Bnd
import OCC.Core.BRepBndLib
import OCC.Core.BRep
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepAlgo
import OCC.Core.TopOpeBRepTool
import OCC.Core.ShapeExtend
import OCC.Core.GProp
import OCC.Core.BRepGProp
import OCC.Core.GC
import OCC.Core.ShapeAnalysis
import OCC.Core.TopTools

from OCC.Core.ShapeAnalysis import shapeanalysis_TotCross2D
import OCC.Core.TopoDS
import OCC.Core.TopExp
import OCC.Core.TopAbs

import ifcopenshell
import ifcopenshell.geom


# Specify to return pythonOCC shapes from ifcopenshell.geom.create_shape()
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_PYTHON_OPENCASCADE, True)
settings.set(settings.INCLUDE_CURVES, True)

# Initialize a graphical display window
# occ_display = ifcopenshell.geom.utils.initialize_display()
# occ_display.View.SetBackgroundImage("white_bg.bmp")

# Open the IFC file using IfcOpenShell
ifc_file = ifcopenshell.open(os.path.join(os.path.dirname(__file__), "ifc/house.ifc"))

# The geometric elements in an IFC file are the IfcProduct elements. So these are
# opened and displayed.
products = ifc_file.by_type("IfcProduct")
product_shapes = []

# For every product a shape is created if the shape has a Representation.
for product in products:
    if not product.is_a("IfcWall"):
        continue
    if product.Representation is not None:
        shape = ifcopenshell.geom.create_shape(settings, product).geometry
        product_shapes.append((product, shape))

# print(product_shapes)

# A horizontal plane is created from which a face is constructed to intersect with
# the building. The face is transparently displayed along with the building.
section_height = 0
section_plane = OCC.Core.gp.gp_Pln(
    OCC.Core.gp.gp_Pnt(0, 0, section_height),
    OCC.Core.gp.gp_Dir(0, 0, 1)
)
section_face = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(section_plane, -10, 10, -10, 10).Face()

for product, shape in product_shapes:
    section = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Section(section_face, shape).Shape()
    exp = OCC.Core.TopExp.TopExp_Explorer(section, OCC.Core.TopAbs.TopAbs_EDGE)
    section_edges = []
    while exp.More():
        section_edges.append(OCC.Core.TopoDS.topods.Edge(exp.Current()))
        exp.Next()

    if len(section_edges) > 0:
        print("    {:<20}: {}".format(product.is_a(), product.Name))

        edges = OCC.Core.TopTools.TopTools_HSequenceOfShape()
        wires = OCC.Core.TopTools.TopTools_HSequenceOfShape()

        # The edges are copied to the sequence
        for edge in section_edges:
            edges.Append(edge)

        # A wire is formed by connecting the edges
        OCC.Core.ShapeAnalysis.ShapeAnalysis_FreeBounds.ConnectEdgesToWires(edges, 1e-5, True, wires)
        print(wires)
    print()
