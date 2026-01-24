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

from .fbx import *
from .files import read_bridge_file, get_from_unreal_path, is_bridge_configured
from .objects import *


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
        task_file_path = self.retrieve_task_task_file_path(context)  # Rename to improve clarity
        if not task_file_path:
            return {'CANCELLED'}

        task_data = read_bridge_file(task_file_path)  # Updated the function call with the new task_file_path
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

    def process_and_import_object(self, item, operation):
        # Determine the collection hierarchy based on the internal path
        # Filter empty strings from split (handles leading slash in paths like "/Assets/...")
        collections_hierarchy = [p for p in item["internalPath"].split('/') if p]
        root_collection = self.ensure_collection_hierarchy(collections_hierarchy)

        # Import the object
        item_type = item["stringType"]
        import_options = get_general_import_opts(item_type)
        bpy.ops.import_scene.fbx(filepath=item["exportLocation"], **import_options)

        # Process the imported objects
        imported_objs = [obj for obj in bpy.context.selected_objects]
        
        # Find the root object of the import hierarchy
        root_obj = self.find_import_root(imported_objs, item_type)
        
        for obj in imported_objs:
            self.set_object_custom_properties(obj, item)
            # Mark the root object for export identification
            obj["AB_isExportRoot"] = (obj == root_obj)
            
            if obj.name not in root_collection.objects:
                root_collection.objects.link(obj)
                bpy.context.collection.objects.unlink(obj)
                if item_type != "SkeletalMesh":
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
