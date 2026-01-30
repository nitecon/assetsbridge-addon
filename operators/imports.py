# Copyright (c) 2023, Nitecon Studios LLC.  All rights reserved.

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

from .gltf import get_general_import_opts
from .objects import (
    set_world_rotation,
    set_world_scale,
    set_world_location,
)


def configure_scene_for_unreal():
    """
    Configures scene unit settings for Unreal compatibility.
    Sets Unit System to Metric and Unit Scale to 0.01.
    Returns True if changes were made.
    """
    unit_settings = bpy.context.scene.unit_settings
    changed = False
    
    if unit_settings.system != 'METRIC':
        unit_settings.system = 'METRIC'
        changed = True
    
    # Use tolerance for float comparison
    if abs(unit_settings.scale_length - 0.01) > 0.001:
        unit_settings.scale_length = 0.01
        changed = True
    
    return changed


from .files import read_bridge_file, get_from_unreal_path, is_bridge_configured


class BridgedImport(bpy.types.Operator):
    """AssetsBridge import from task script"""
    bl_idname = "assetsbridge.imports"
    bl_label = "Import items from the json task file"
    bl_options = {'REGISTER', 'UNDO'}
    task_task_file_path: bpy.props.StringProperty(name="TaskFileVar", default="//AssetsBridge.json",
                                             description="Task file location")

    def execute(self, context):
        """
        Execute the task by processing the task file and importing objects.

        :param context: The context for the task execution
        :return: A set indicating the status of the task execution, can be {'CANCELLED'} or {'FINISHED'}
        """
        # Configure scene units for Unreal compatibility before import
        if configure_scene_for_unreal():
            self.report({"INFO"}, "Scene units configured for Unreal (Metric, Scale 0.01)")
        
        task_file_path = self.retrieve_task_task_file_path(context)
        if not task_file_path:
            return {'CANCELLED'}

        task_data = read_bridge_file(task_file_path)
        if not task_data or task_data['operation'] == "":
            self.report({"ERROR"}, "Invalid or empty task file.")
            return {'CANCELLED'}

        for item in task_data['objects']:
            self.process_and_import_object(item, task_data['operation'])

        return {'FINISHED'}

    def retrieve_task_task_file_path(self, context):
        """Returns the path to from-unreal.json for importing assets from Unreal.
        Ensures the AssetsBridge Addon Preferences are configured properly.
        """
        if not is_bridge_configured():
            self.report({"ERROR"}, "Please configure AssetsBridge Addon Preferences to point to the bridge directory.")
            return ""
        
        from_unreal_path = get_from_unreal_path()
        if not from_unreal_path:
            self.report({"ERROR"}, "Could not determine from-unreal.json path.")
            return ""
        
        import os
        if not os.path.exists(from_unreal_path):
            self.report({"ERROR"}, f"Import file not found: {from_unreal_path}. Export from Unreal first.")
            return ""
        
        return from_unreal_path

    def find_existing_object_by_id(self, object_id):
        """Find an existing object in the scene by its AB_objectId custom property."""
        for obj in bpy.data.objects:
            if obj.get("AB_objectId") == object_id:
                return obj
        return None

    def update_existing_object_transform(self, existing_obj, item, operation):
        """Update the transform of an existing object with new worldData."""
        item_type = item.get("stringType", "StaticMesh")
        if item_type == "StaticMesh":
            set_world_scale(existing_obj, item, operation)
            set_world_rotation(existing_obj, item, operation)
            set_world_location(existing_obj, item, operation)
        elif item_type == "SkeletalMesh":
            if existing_obj.get("AB_isExportRoot", False):
                set_world_scale(existing_obj, item, operation)
                set_world_rotation(existing_obj, item, operation)
                set_world_location(existing_obj, item, operation)

    def process_and_import_object(self, item, operation):
        object_id = item.get("objectId", "")
        
        # Check if object already exists in scene
        if object_id:
            existing_obj = self.find_existing_object_by_id(object_id)
            if existing_obj:
                self.update_existing_object_transform(existing_obj, item, operation)
                self.report({"INFO"}, f"Position updated for existing object: {existing_obj.name}")
                return
        
        # Determine the collection hierarchy based on the internal path
        # Filter empty strings from split (handles leading slash in paths like "/Assets/...")
        collections_hierarchy = [p for p in item["internalPath"].split('/') if p]
        root_collection = self.ensure_collection_hierarchy(collections_hierarchy)

        # Import the object
        item_type = item["stringType"]
        import_options = get_general_import_opts(item_type)
        bpy.ops.import_scene.gltf(filepath=item["exportLocation"], **import_options)

        # Process the imported objects
        imported_objs = [obj for obj in bpy.context.selected_objects]
        
        # Find the root object of the import hierarchy
        root_obj = self.find_import_root(imported_objs, item_type)
        
        # Restore shape key names from JSON for skeletal meshes
        if item_type == "SkeletalMesh":
            morph_targets = item.get("morphTargets", [])
            if morph_targets:
                self.restore_shape_key_names(imported_objs, morph_targets)
        
        for obj in imported_objs:
            self.set_object_custom_properties(obj, item)
            # Mark the root object for export identification
            obj["AB_isExportRoot"] = (obj == root_obj)
            
            if obj.name not in root_collection.objects:
                root_collection.objects.link(obj)
                bpy.context.collection.objects.unlink(obj)
            
            # Handle scaling based on mesh type:
            # Both StaticMesh and SkeletalMesh use scale 1.0 (scene units handle conversion)
            if item_type == "StaticMesh":
                obj.scale = (1.0, 1.0, 1.0)
                set_world_scale(obj, item, operation)  # Multiplies by worldData scale
                set_world_rotation(obj, item, operation)
                set_world_location(obj, item, operation)
            elif item_type == "SkeletalMesh" and obj == root_obj:
                obj.scale = (1, 1, 1)  # Scale down skeletal mesh from Unreal
                set_world_scale(obj, item, operation)
                set_world_rotation(obj, item, operation)
                set_world_location(obj, item, operation)
    
    def find_import_root(self, imported_objs, item_type):
        """
        Finds the root object of an imported asset hierarchy.
        For SkeletalMesh: prefer EMPTY parent, then ARMATURE, then MESH
        For StaticMesh: prefer MESH
        """
        if item_type == "SkeletalMesh":
            # First look for an EMPTY (typical root for skeletal imports)
            for obj in imported_objs:
                if obj.type == "EMPTY" and obj.parent is None:
                    return obj
            # Then look for ARMATURE without parent
            for obj in imported_objs:
                if obj.type == "ARMATURE" and obj.parent is None:
                    return obj
            # Fall back to any parentless MESH
            for obj in imported_objs:
                if obj.type == "MESH" and obj.parent is None:
                    return obj
        else:
            # StaticMesh - prefer MESH
            for obj in imported_objs:
                if obj.type == "MESH" and obj.parent is None:
                    return obj
        
        # Last resort: return any parentless object or first object
        for obj in imported_objs:
            if obj.parent is None:
                return obj
        return imported_objs[0] if imported_objs else None

    def get_top_collection(self):
        """
        Finds the top-level 'Collection' in the Blender scene.
        If it does not exist, it creates one.
        """
        # Iterate through all collections in the Blender file
        for coll in bpy.data.collections:
            # Check if this collection is linked directly to a scene
            if any(coll.name in scene.collection.children for scene in bpy.data.scenes):
                # If we find the 'Collection', return it
                if coll.name == "Collection":
                    return coll

        # If 'Collection' does not exist, create it and link it to the current scene's master collection
        new_coll = bpy.data.collections.new("Collection")
        bpy.context.scene.collection.children.link(new_coll)
        return new_coll

    def ensure_collection_hierarchy(self, collections_hierarchy):
        """
        Creates the collection hierarchy under the top-level 'Collection'.
        Preserves the original Unreal path structure (e.g., Assets/Wearables/...).
        """
        # Ensure the hierarchy starts from a top-level 'Collection'
        parent_collection = self.get_top_collection()

        # Create the full hierarchy under Collection, preserving original structure
        for collection_name in collections_hierarchy:
            found_collection = False
            for coll in parent_collection.children:
                if coll.name == collection_name:
                    parent_collection = coll
                    found_collection = True
                    break
            if not found_collection:
                new_coll = bpy.data.collections.new(collection_name)
                parent_collection.children.link(new_coll)
                parent_collection = new_coll
        return parent_collection

    def restore_shape_key_names(self, imported_objs, morph_targets):
        """
        Restores shape key names from the original morph target names stored in JSON.
        glTF import names them as 'target_0', 'target_1', etc. - we rename them back.
        """
        for obj in imported_objs:
            if obj.type != 'MESH':
                continue
            
            if not obj.data.shape_keys:
                continue
            
            key_blocks = obj.data.shape_keys.key_blocks
            # Skip 'Basis' which is at index 0
            shape_key_index = 0
            for i, key_block in enumerate(key_blocks):
                if key_block.name == "Basis":
                    continue
                
                # Check if this is a target_N named shape key
                if key_block.name.startswith("target_") or key_block.name.startswith("Key "):
                    if shape_key_index < len(morph_targets):
                        old_name = key_block.name
                        new_name = morph_targets[shape_key_index]
                        key_block.name = new_name
                        print(f"AssetsBridge: Renamed shape key '{old_name}' -> '{new_name}'")
                    shape_key_index += 1

    def set_object_custom_properties(self, obj, item):
        # Assuming 'item' is a dictionary containing all the necessary info
        obj["AB_model"] = item.get("model", "")
        obj["AB_objectId"] = item.get("objectId", "")
        obj["AB_internalPath"] = item.get("internalPath", "")
        obj["AB_relativeExportPath"] = item.get("relativeExportPath", "")
        obj["AB_exportLocation"] = item.get("exportLocation", "")
        obj["AB_stringType"] = item.get("stringType", "")
        obj["AB_shortName"] = item.get("shortName", "")
        obj["AB_objectMaterials"] = item.get("objectMaterials", [])
        # Preserve skeleton path for SkeletalMesh reimport
        if item.get("skeleton"):
            obj["AB_skeleton"] = item.get("skeleton", "")
