from typing import List, Any
import ifcopenshell

"""
Some IfcProducts are not yet parsable by this script.
For example, escalators and elevators cannot currently be properly parsed.
This function returns a list of elements that the script cannot currently support.
"""


def get_unparsable_elements(ifc_building) -> List[Any]:
    unparsable_elements = []
    elements = ifcopenshell.util.element.get_decomposition(ifc_building)
    for element in elements:
        if element.is_a("IfcTransportElement"):  # Escalators, elevators, travelators
            unparsable_elements.append((element, "Element is not yet supported"))
    return unparsable_elements
