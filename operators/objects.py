# Copyright (c) 2023, Nitecon Studios LLC.  All rights reserved.

import math

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
import bpy

def setup_import(obj, item, operation):
    if obj is None or not hasattr(obj, "type"):
        return
    update_for_general_import(obj, item, operation)

    obj['import_data'] = item


def set_world_rotation(obj, item, operation):
    if item['worldData'] is not None:
        if item['worldData']['rotation'] is not None:
            if operation == "UnrealExport":
                rotate_object_in_degrees(obj, item['worldData']['rotation']['x'], item['worldData']['rotation']['y'], item['worldData']['rotation']['z'])
            else:
                rotate_object_in_degrees(obj, item['worldData']['rotation']['x'], item['worldData']['rotation']['y'], item['worldData']['rotation']['z'])


def set_world_location(obj, item, operation):
    if item['worldData'] is not None:
        if item['worldData']['location'] is not None:
            if operation == "UnrealExport":
                # Scene unit scale (0.01) handles cm->m conversion
                # Negate Y: Unreal (left-handed) to Blender (right-handed)
                obj.location.x = item['worldData']['location']['x']
                obj.location.y = -item['worldData']['location']['y']
                obj.location.z = item['worldData']['location']['z']
            else:
                obj.location.x = item['worldData']['location']['x']
                obj.location.y = -item['worldData']['location']['y']
                obj.location.z = item['worldData']['location']['z']

def prepare_for_export(obj):
    if obj is None or not hasattr(obj, "type"):
        return
    # Store the current location, rotation and scale
    obj['AB_currentLocation'] = obj.location.copy()
    obj['AB_currentRotation'] = obj.rotation_euler.copy()
    obj['AB_currentScale'] = obj.scale.copy()
    # now we set the location to 0,0,0
    rotate_object_in_degrees(obj, 0, 0, 0)
    obj.location.x = 0
    obj.location.y = 0
    obj.location.z = 0
    # Set scale for Unreal export (0.01 for static meshes)
    obj.scale = (0.01, 0.01, 0.01)
    # NEVER apply transforms to armatures - this breaks bind pose for Unreal
    if obj.type != "ARMATURE":
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
    bpy.context.view_layer.update()


def revert_export_mods(obj):
    if obj is None or not hasattr(obj, "type"):
        return
    obj.location = obj['AB_currentLocation']
    obj.rotation_euler = obj['AB_currentRotation']
    if 'AB_currentScale' in obj:
        obj.scale = obj['AB_currentScale']
        del obj['AB_currentScale']


def set_world_scale(obj, item, operation):
    """Apply world scale from Unreal. Note: For glTF imports, scale is handled in imports.py"""
    if item['worldData'] is not None:
        if item['worldData']['scale'] is not None:
            # Just apply the scale multiplier from worldData (typically 1.0)
            # The base mesh scale (0.01 for skeletal, 1.0 for static) is set in imports.py
            obj.scale.x *= item['worldData']['scale']['x']
            obj.scale.y *= item['worldData']['scale']['y']
            obj.scale.z *= item['worldData']['scale']['z']


def invert_world_data_rotation(obj, item):
    if item['worldData'] is not None:
        if item['worldData']['rotation'] is not None:
            rotate_object_in_degrees(obj, -item['worldData']['rotation']['x'], -item['worldData']['rotation']['y'], 0)


def check_if_world_scale_not_1(obj, item, operation):
    if item['worldData'] is not None:
        if item['worldData']['scale'] is not None:
            if item['worldData']['scale']['x'] != 1 or item['worldData']['scale']['y'] != 1:
                return True
    return False


def update_for_general_import(obj, item, operation):
    if obj.type == "MESH":
        # select the object
        obj.select_set(True)
        # bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.tris_convert_to_quads()
        bpy.ops.object.mode_set(mode='OBJECT')
        # Print the name of the object
    if obj.name.startswith("UCX"):
        obj.display.show_shadows = False
        obj.color = (0, 0.2, 1, 1)
        obj.display_type = 'WIRE'
        obj.hide_render = True


def update_object_post_export(obj):
    rotate_object_in_degrees(obj, 0, 0, 90)
    # if hasattr(obj, 'transform_apply'):
    #    obj.transform_apply(location=False, rotation=True, scale=False)


def create_collision_box(obj):
    # Get the object's collision box data
    collision_box = obj.bound_box

    # Create a list of vertices for the collision box mesh
    vertices = [
        collision_box[0], collision_box[1], collision_box[2],
        collision_box[3], collision_box[4], collision_box[5],
        collision_box[6], collision_box[7]
    ]

    # Create a list of edges for the collision box mesh
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]

    # Create a new mesh and link it to the scene
    mesh = bpy.data.meshes.new("Collision Box")
    short_name = obj.name.replace("SM_", "")
    collision_box_object = bpy.data.objects.new("UCX_" + short_name, mesh)
    bpy.context.collection.objects.link(collision_box_object)

    # Set the vertices and edges of the mesh
    mesh.from_pydata(vertices, edges, [])

    # Scale the bounding box mesh down until it closely matches the size of the object
    scale_factor = 0.9
    while collision_box_object.dimensions[0] < obj.dimensions[0] * scale_factor \
            or collision_box_object.dimensions[1] < obj.dimensions[1] * scale_factor \
            or collision_box_object.dimensions[2] < obj.dimensions[2] * scale_factor:
        collision_box_object.scale *= scale_factor

    # Update the scene
    bpy.context.view_layer.update()


# check to see if a collection exists by name, and if it does check to see if an existing mesh exists in the collection by the same name:
def check_for_existing_mesh_in_collection(collection):
    if collection is not None:
        if collection.objects.get(collection.name) is not None:
            return True
    return False


def get_mesh_in_collection(collection):
    if collection is not None:
        if collection.objects.get(collection.name) is not None:
            return collection.objects[collection.name]
    return None


def duplicate_mesh_object_in_collection(collection, mesh_object):
    # Get the mesh data
    mesh = mesh_object.data

    # Create a new mesh object
    new_mesh_object = bpy.data.objects.new(mesh.name, mesh)

    # Add the new mesh object to the scene
    collection.objects.link(new_mesh_object)

    # Make sure the new mesh object has a unique name
    i = 1
    while bpy.data.objects.get(new_mesh_object.name):
        new_mesh_object.name = f"{mesh.name}_{i}"
        i += 1

    return new_mesh_object


# get the object within a collection which matches the name:
def get_object_in_collection(collection, mesh_name):
    if collection is not None:
        if collection.objects.get(mesh_name) is not None:
            return collection.objects[mesh_name]
    return None


# get the first object in collection that is a mesh's transform in unreal units
def get_first_mesh_transform_in_unreal_units(collection):
    for obj in collection.objects:
        if obj.type == "MESH":
            return get_object_transform_in_unreal_units(obj)
    return None


# get object transform in unreal units
def get_object_transform_in_unreal_units(obj):
    transform = {'location': {'x': obj.location.x, 'y': -obj.location.y, 'z': obj.location.z},  # Negate Y for Unreal
                 'rotation': get_object_rotation_in_degrees(obj),
                 'scale': {'x': obj.scale.x, 'y': obj.scale.y, 'z': obj.scale.z}}
    return transform


# get object rotation in degrees
def get_object_rotation_in_degrees(obj):
    rotation = obj.rotation_euler
    x_rotation = math.degrees(rotation.x)
    y_rotation = math.degrees(rotation.y)
    z_rotation = math.degrees(rotation.z)
    rotation = {'x': x_rotation, 'y': y_rotation, 'z': z_rotation}
    return rotation


def rotate_object(obj, x, y, z):
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler.x = x
    obj.rotation_euler.y = y
    obj.rotation_euler.z = z


def rotate_object_in_degrees(obj, x, y, z):
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = math.radians(x), math.radians(y), math.radians(z)


def prepare_armature_for_export(armature_obj):
    """Prepare armature for export - set REST pose for proper bind pose."""
    if armature_obj is None or armature_obj.type != "ARMATURE":
        return None
    original_pose_position = armature_obj.data.pose_position
    armature_obj.data.pose_position = 'REST'
    armature_obj['AB_currentLocation'] = armature_obj.location.copy()
    armature_obj['AB_currentRotation'] = armature_obj.rotation_euler.copy()
    armature_obj['AB_currentScale'] = armature_obj.scale.copy()
    armature_obj['AB_originalPosePosition'] = original_pose_position
    armature_obj.location = (0, 0, 0)
    armature_obj.rotation_euler = (0, 0, 0)
    armature_obj.scale = (0.1, 0.1, 0.1)  # Scale for Unreal export
    bpy.context.view_layer.update()
    return original_pose_position

# DEPRECATED: Scale handling moved to imports.py
def _unused_prepare_armature_for_import(armature_obj):
    """Set scale for imported skeletal mesh. Call after glTF import."""
    if armature_obj is None or armature_obj.type != "ARMATURE":
        return None
    original_pose_position = armature_obj.data.pose_position
    armature_obj.data.pose_position = 'REST'
    armature_obj['AB_currentLocation'] = armature_obj.location.copy()
    armature_obj['AB_currentRotation'] = armature_obj.rotation_euler.copy()
    armature_obj['AB_currentScale'] = armature_obj.scale.copy()
    armature_obj['AB_originalPosePosition'] = original_pose_position
    armature_obj.location = (0, 0, 0)
    armature_obj.rotation_euler = (0, 0, 0)
    armature_obj.scale = (0.01, 0.01, 0.01)  # Scale down imported skeletal mesh
    bpy.context.view_layer.update()
    return original_pose_position


def revert_armature_export(armature_obj):
    """Revert armature to original state after export."""
    if armature_obj is None or armature_obj.type != "ARMATURE":
        return
    if 'AB_originalPosePosition' in armature_obj:
        armature_obj.data.pose_position = armature_obj['AB_originalPosePosition']
        del armature_obj['AB_originalPosePosition']
    if 'AB_currentLocation' in armature_obj:
        armature_obj.location = armature_obj['AB_currentLocation']
        del armature_obj['AB_currentLocation']
    if 'AB_currentRotation' in armature_obj:
        armature_obj.rotation_euler = armature_obj['AB_currentRotation']
        del armature_obj['AB_currentRotation']
    if 'AB_currentScale' in armature_obj:
        armature_obj.scale = armature_obj['AB_currentScale']
        del armature_obj['AB_currentScale']