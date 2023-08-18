#!/bin/bash

IfcConvert house.ifc house.svg -qy --plan --model --section-height-from-storeys --bounds=1024x1024 --include entities IfcWall IfcWindow IfcDoor IfcAnnotation
