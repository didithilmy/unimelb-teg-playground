import numpy as np
import pyquaternion
from dotbimpy import File
import trimesh


def divide_to_chunks(list_to_divide, chunk_size):
    for i in range(0, len(list_to_divide), chunk_size):
        yield list_to_divide[i : i + chunk_size]


def convert_dotbim_mesh_to_trimesh(mesh_to_convert, element) -> trimesh.Trimesh:
    faces = list(divide_to_chunks(mesh_to_convert.indices, 3))

    vertices = []
    counter = 0
    while counter < len(mesh_to_convert.coordinates):
        point = np.array(
            [
                mesh_to_convert.coordinates[counter],
                mesh_to_convert.coordinates[counter + 1],
                mesh_to_convert.coordinates[counter + 2],
            ]
        )

        rotation = pyquaternion.Quaternion(
            a=element.rotation.qw,
            b=element.rotation.qx,
            c=element.rotation.qy,
            d=element.rotation.qz,
        )

        point_rotated = rotation.rotate(point)
        vertices.append(
            [
                point_rotated[0] + element.vector.x,
                point_rotated[1] + element.vector.y,
                point_rotated[2] + element.vector.z,
            ]
        )
        counter += 3

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.visual.face_colors = [
        element.color.r,
        element.color.g,
        element.color.b,
        element.color.a,
    ]

    return mesh


def convert_file_to_trimesh_scene(file):
    scene = trimesh.Scene()
    for i in file.elements:
        mesh = next((x for x in file.meshes if x.mesh_id == i.mesh_id), None)
        trimesh_mesh = convert_dotbim_mesh_to_trimesh(mesh_to_convert=mesh, element=i)
        scene.add_geometry(trimesh_mesh)

    return scene

if __name__ == '__main__':
    file = File.read("House.bim")
    scene = convert_file_to_trimesh_scene(file)
    scene.export('output.obj', 'obj', include_color=True)