# Copyright (c) 2023, Nitecon Studios LLC.  All rights reserved.
import os

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

from .gltf import *
from .files import write_bridge_file, get_from_blender_path, is_bridge_configured, get_bridge_directory
from .objects import *


class BridgedExport(bpy.types.Operator):
    """AssetsBridge export to task script"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "assetsbridge.exports"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Export selected items to the json task file"  # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    task_file_var: bpy.props.StringProperty(name="TaskFileVar", default="//AssetsBridge.json", description="Task file location")

    def execute(self, context):  # execute() is called when running the operator.
        if not is_bridge_configured():
            self.report({"ERROR"}, "Please configure AssetsBridge Addon Preferences to point to the bridge directory.")
            return {'CANCELLED'}
        
        from_blender_path = get_from_blender_path()
        if not from_blender_path:
            self.report({"ERROR"}, "Could not determine from-blender.json path.")
            return {'CANCELLED'}
        
        self.task_file_var = from_blender_path
        
        # Get selected objects
        selected_objects = bpy.context.selected_objects
        if len(selected_objects) == 0:
            self.report({'INFO'}, "Nothing selected, Please select an object to export.")
            return {'FINISHED'}

        # Find unique export roots from selection (handles selecting multiple objects in same hierarchy)
        export_roots = self.find_export_roots(selected_objects)
        
        if not export_roots:
            self.report({'ERROR'}, "No valid exportable objects found in selection.")
            return {'CANCELLED'}
        
        new_data = {'operation': 'BlenderExport', 'objects': []}
        self.report({'INFO'}, f"Export process started - found {len(export_roots)} asset(s) to export")
        
        for root_obj in export_roots:
            self.report({'INFO'}, f"Processing asset: {root_obj.name} (type: {root_obj.type})")
            
            # Determine export type based on stored metadata or object structure
            string_type = root_obj.get("AB_stringType", "")
            
            if string_type == "SkeletalMesh" or self.is_skeletal_hierarchy(root_obj):
                # Skeletal mesh export
                # For skeletal meshes, we need to export Armature + Mesh, NOT the Empty parent
                # The Empty is used for scene placement but creates an extra root bone in Unreal
                self.setup_naming(root_obj)
                self.prepare_object(root_obj)
                export_options = get_unreal_skeletal_export_opts()
                
                # Find the armature in the hierarchy - this is what we actually export
                armature_obj = self.find_armature_in_hierarchy(root_obj)
                
                if armature_obj:
                    # Select full hierarchy first to preserve relationships, then deselect the Empty
                    # This ensures proper bind pose context while excluding the Empty from export
                    bpy.ops.object.select_all(action='DESELECT')
                    root_obj.select_set(True)
                    self.select_child_hierarchy(root_obj)
                    
                    # Now deselect the Empty parent if root is an EMPTY
                    if root_obj.type == "EMPTY":
                        root_obj.select_set(False)
                    
                    # Prepare armature and its children
                    self.prepare_object(armature_obj)
                    self.prepare_hierarchy(armature_obj)
                    
                    # Export using armature, but get info from the metadata root
                    update_info = self.export_skeletal_mesh(root_obj, armature_obj, export_options)
                else:
                    # Fallback: no armature found, export the whole hierarchy
                    self.report({'WARNING'}, f"No armature found in {root_obj.name}, exporting full hierarchy")
                    bpy.ops.object.select_all(action='DESELECT')
                    root_obj.select_set(True)
                    self.select_child_hierarchy(root_obj)
                    self.prepare_hierarchy(root_obj)
                    update_info = self.export_object(root_obj, export_options)
                
                new_data['objects'].append(update_info)
            else:
                # Static mesh export
                self.setup_naming(root_obj)
                self.prepare_object(root_obj)
                export_options = get_unreal_export_opts()
                
                bpy.ops.object.select_all(action='DESELECT')
                root_obj.select_set(True)
                
                update_info = self.export_object(root_obj, export_options)
                new_data['objects'].append(update_info)

        write_bridge_file(new_data, self.task_file_var)
        self.report({'INFO'}, f"Export complete. Written to: {self.task_file_var}")
        return {'FINISHED'}
    
    def find_export_roots(self, selected_objects):
        """
        From a selection, find the unique root objects that represent exportable assets.
        Uses AB_isExportRoot metadata from import, or finds hierarchy roots.
        """
        export_roots = set()
        processed = set()
        
        for obj in selected_objects:
            if obj in processed:
                continue
            
            # If this object is marked as export root, use it
            if obj.get("AB_isExportRoot", False):
                export_roots.add(obj)
                processed.add(obj)
                # Mark all children as processed
                self.mark_hierarchy_processed(obj, processed)
                continue
            
            # Otherwise, find the root of this object's hierarchy
            root = self.find_hierarchy_root(obj)
            if root and root not in export_roots:
                export_roots.add(root)
                self.mark_hierarchy_processed(root, processed)
        
        return list(export_roots)
    
    def find_hierarchy_root(self, obj):
        """
        Walks up the parent chain to find the root of an object's hierarchy.
        Prefers objects marked with AB_isExportRoot.
        """
        current = obj
        while current.parent:
            if current.parent.get("AB_isExportRoot", False):
                return current.parent
            current = current.parent
        return current
    
    def mark_hierarchy_processed(self, obj, processed):
        """Recursively marks an object and all its children as processed."""
        processed.add(obj)
        for child in obj.children:
            self.mark_hierarchy_processed(child, processed)
    
    def is_skeletal_hierarchy(self, obj):
        """
        Checks if an object or its children contain an armature, indicating skeletal mesh.
        """
        if obj.type == "ARMATURE":
            return True
        for child in obj.children:
            if self.is_skeletal_hierarchy(child):
                return True
        # Also check if any MESH has an armature modifier
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE':
                    return True
        return False
    
    def find_armature_in_hierarchy(self, obj):
        """
        Finds the first Armature object in a hierarchy.
        Searches the object itself and its children recursively.
        """
        if obj.type == "ARMATURE":
            return obj
        for child in obj.children:
            armature = self.find_armature_in_hierarchy(child)
            if armature:
                return armature
        return None
    
    def export_skeletal_mesh(self, metadata_obj, armature_obj, export_options):
        """
        Exports a skeletal mesh using the armature as the export root,
        but retrieves metadata from the original root object (which may be an Empty).
        
        Parameters:
            metadata_obj: The object containing AB_ metadata (may be Empty)
            armature_obj: The actual armature to export
            export_options: FBX export options
        """
        from .objects import prepare_armature_for_export, revert_armature_export
        
        # Prepare armature - sets REST pose and preserves bind pose
        prepare_armature_for_export(armature_obj)
        
        # Export the skeletal mesh
        bpy.ops.export_scene.gltf(filepath=metadata_obj["AB_exportLocation"], **export_options)
        
        # Revert armature to original state
        revert_armature_export(armature_obj)
        
        # Return export info using metadata from the root object
        return self.get_export_info(metadata_obj)

    def select_child_hierarchy(self, obj):
        """
        Recursively selects the entire hierarchy of children for a given object.

        Parameters:
            obj (bpy.types.Object): The object whose children are to be selected.
        """
        if obj.children:
            for child in obj.children:
                child.select_set(True)
                self.select_child_hierarchy(child)

    def prepare_hierarchy(self, obj):
        """
        Recursively prepares the object hierarchy for export by processing each child object and setting defaults.

        Parameters:
            obj (bpy.types.Object): The parent object whose hierarchy is to be prepared.
        """
        for child in obj.children:
            self.report({'INFO'}, "Processing child: " + child.name + " (type: " + child.type + ")")
            self.prepare_object(child)
            if child.children:
                self.prepare_hierarchy(child)


    def prepare_object(self, obj):
        """
        Prepares the object for export by setting defaults and updating object properties.
        Preserves original Unreal paths and model references when available.

        Parameters:
            obj (bpy.types.Object): The object to be prepared for export.
        """
        self.setup_defaults(obj)
        
        # Use AB_shortName for asset name (handles EMPTY roots in skeletal hierarchies)
        short_name = obj.get("AB_shortName", obj.name)
        
        # Use preserved paths from Unreal import, or generate from collection hierarchy
        internal_path = obj.get("AB_internalPath") or self.get_collection_hierarchy_path(obj)
        
        # Update export location based on current collection structure
        obj["AB_exportLocation"] = self.get_export_path(obj)
        obj["AB_internalPath"] = internal_path
        obj["AB_relativeExportPath"] = internal_path

        # Only update model path if not preserved from import (check for default paths)
        existing_model = obj.get("AB_model", "")
        is_default_model = not existing_model or "'/Game/Meshes/" in existing_model
        if is_default_model:
            if obj.get("AB_stringType") == "StaticMesh":
                obj["AB_model"] = "/Script/Engine.StaticMesh'/Game/" + internal_path + "/" + short_name + "." + short_name + "'"
            elif obj.get("AB_stringType") == "SkeletalMesh":
                obj["AB_model"] = "/Script/Engine.SkeletalMesh'/Game/" + internal_path + "/" + short_name + "." + short_name + "'"

    def export_object(self, obj, export_options):
        """
        Exports the object using the provided export options.

        Parameters:
            obj (bpy.types.Object): The object to be exported.
            export_options (dict): Options for the export process.
        """
        prepare_for_export(obj)
        bpy.ops.export_scene.gltf(filepath=obj["AB_exportLocation"], **export_options)
        revert_export_mods(obj)
        return self.get_export_info(obj)

    def get_export_info(self, obj):
        """
        Retrieves export information for the given object.

        Parameters:
            obj (bpy.types.Object): The object for which export information is to be retrieved.

        Returns:
            dict: Export information for the object.
        """
        # Get current mesh materials - this captures any added/removed materials in Blender
        materials = self.get_current_materials(obj)
        if not materials:
            materials = [
                {
                    "name": "WorldGridMaterial",
                    "idx": 0,
                    "internalPath": "/Engine/EngineMaterials/WorldGridMaterial"
                }
            ]
        
        # Generate material changeset for tracking additions/removals
        material_changeset = self.get_material_changeset(obj)
        
        ob_info = {
            "model": str(obj.get("AB_model", "")),
            "objectId": str(obj.get("AB_objectId", "")),
            "internalPath": str(obj.get("AB_internalPath", "")),
            "relativeExportPath": str(obj.get("AB_relativeExportPath", "")),
            "shortName": str(obj.get("AB_shortName", obj.name)),
            "exportLocation": str(obj.get("AB_exportLocation", "")),
            "stringType": str(obj.get("AB_stringType", "")),
            "skeleton": str(obj.get("AB_skeleton", "")),
            "worldData": {
                "rotation": {
                    "x": float(obj.rotation_euler.x),
                    "y": float(obj.rotation_euler.y),
                    "z": float(obj.rotation_euler.z)
                },
                "scale": {
                    "x": float(obj.scale.x),
                    "y": float(obj.scale.y),
                    "z": float(obj.scale.z)
                },
                "location": {
                    "x": float(obj.location.x),
                    "y": float(obj.location.y),
                    "z": float(obj.location.z)
                }
            },
            "objectMaterials": materials,
            "materialChangeset": material_changeset,
        }

        return ob_info
    
    def get_current_materials(self, obj):
        """
        Gets the current materials from the mesh object.
        Matches Blender materials to their original Unreal paths where possible.
        """
        materials = []
        
        # Find the mesh object (could be the object itself or a child)
        mesh_obj = None
        if obj.type == 'MESH':
            mesh_obj = obj
        else:
            # Look for mesh in children (e.g., for EMPTY or ARMATURE roots)
            for child in obj.children_recursive:
                if child.type == 'MESH':
                    mesh_obj = child
                    break
        
        if not mesh_obj or not mesh_obj.data.materials:
            # Fall back to stored materials if no mesh found
            raw_materials = obj.get("AB_objectMaterials", [])
            return self.convert_to_serializable(raw_materials)
        
        # Get stored materials for path lookup
        stored_materials = {}
        raw_stored = obj.get("AB_objectMaterials", [])
        if raw_stored:
            for mat in self.convert_to_serializable(raw_stored):
                if isinstance(mat, dict):
                    stored_materials[mat.get("name", "")] = mat
        
        # Build materials list from current mesh state
        for idx, mat_slot in enumerate(mesh_obj.data.materials):
            mat_name = mat_slot.name if mat_slot else f"Material_{idx}"
            
            # Try to find matching Unreal path from stored materials
            stored_mat = stored_materials.get(mat_name, {})
            internal_path = stored_mat.get("internalPath", "")
            original_idx = stored_mat.get("idx", -1)
            if not internal_path:
                # Default path for new materials
                internal_path = "/Engine/EngineMaterials/WorldGridMaterial"
            
            materials.append({
                "name": mat_name,
                "idx": idx,
                "internalPath": internal_path,
                "originalIdx": original_idx
            })
        
        return materials
    
    def get_material_changeset(self, obj):
        """
        Generates a changeset comparing current mesh materials to original Unreal materials.
        Returns dict with 'added', 'removed', and 'unchanged' lists.
        """
        current_materials = self.get_current_materials(obj)
        
        # Get original materials from stored property
        stored_materials = {}
        stored_list = []
        raw_stored = obj.get("AB_objectMaterials", [])
        if raw_stored:
            stored_list = self.convert_to_serializable(raw_stored)
            for mat in stored_list:
                if isinstance(mat, dict):
                    stored_materials[mat.get("name", "")] = mat
        
        current_names = {m["name"] for m in current_materials}
        stored_names = set(stored_materials.keys())
        
        added = []
        removed = []
        unchanged = []
        
        # Find added materials (in current but not in stored)
        for mat in current_materials:
            if mat["name"] not in stored_names:
                added.append({
                    "name": mat["name"],
                    "idx": mat["idx"],
                    "internalPath": mat["internalPath"],
                    "originalIdx": -1
                })
            else:
                # Unchanged - restore original Unreal material
                unchanged.append({
                    "name": mat["name"],
                    "idx": mat["idx"],
                    "internalPath": stored_materials[mat["name"]].get("internalPath", ""),
                    "originalIdx": stored_materials[mat["name"]].get("idx", mat["idx"])
                })
        
        # Find removed materials (in stored but not in current)
        for name, mat in stored_materials.items():
            if name not in current_names:
                removed.append({
                    "name": name,
                    "idx": -1,
                    "internalPath": mat.get("internalPath", ""),
                    "originalIdx": mat.get("idx", -1)
                })
        
        return {
            "added": added,
            "removed": removed,
            "unchanged": unchanged
        }

    def convert_to_serializable(self, obj):
        """
        Recursively converts Blender IDPropertyGroup objects to plain Python types.
        """
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, 'to_list'):
            return obj.to_list()
        elif isinstance(obj, dict):
            return {k: self.convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self.convert_to_serializable(item) for item in obj]
        elif hasattr(obj, '__iter__') and not isinstance(obj, str):
            # Handle IDPropertyArray and similar iterables
            return [self.convert_to_serializable(item) for item in obj]
        else:
            return obj

    def setup_naming(self, obj):
        """
        Placeholder for naming setup. No automatic renaming - user is responsible for proper naming.

        Parameters:
            obj (bpy.types.Object): The object (not modified).
        """
        pass

    def setup_defaults(self, obj):
        """
        Sets default values for object properties if not already present.
        Preserves values from Unreal import if they exist.

        Parameters:
            obj (bpy.types.Object): The object for which default values are to be set.
        """
        # Only set stringType if not already preserved from import
        if not obj.get("AB_stringType"):
            # Detect type from Unreal naming conventions or structure
            if obj.name.startswith("SM_"):
                obj["AB_stringType"] = "StaticMesh"
            elif obj.name.startswith("SK_") or obj.name.startswith("SKM_"):
                obj["AB_stringType"] = "SkeletalMesh"
            elif self.is_skeletal_hierarchy(obj):
                obj["AB_stringType"] = "SkeletalMesh"
            else:
                obj["AB_stringType"] = "StaticMesh"

        obj["AB_objectId"] = obj.get("AB_objectId", "")
        obj["AB_internalPath"] = obj.get("AB_internalPath", "/Game/Meshes")
        obj["AB_relativeExportPath"] = obj.get("AB_relativeExportPath", "/Game/Meshes")
        obj["AB_shortName"] = obj.get("AB_shortName", obj.name)
        obj["AB_exportLocation"] = obj.get("AB_exportLocation", "")

        default_materials = [
            {
                "name": "WorldGridMaterial",
                "idx": 0,
                "internalPath": "/Engine/EngineMaterials/WorldGridMaterial"
            }
        ]
        obj["AB_objectMaterials"] = obj.get("AB_objectMaterials", default_materials)

    def get_collection_hierarchy_path(self, obj):
        """
        Retrieves the collection hierarchy path for the given object.

        Parameters:
            obj (bpy.types.Object): The object for which the collection hierarchy path is to be retrieved.

        Returns:
            str: The collection hierarchy path for the object.
        """
        def find_collection_hierarchy(collection, hierarchy=[]):
            # Base case: If the collection is already the root, return the current hierarchy
            if collection.name == 'Master Collection':
                return hierarchy
            for coll in bpy.data.collections:
                if collection.name in coll.children.keys():
                    hierarchy.insert(0, coll.name)
                    return find_collection_hierarchy(coll, hierarchy)
            return hierarchy

        collection_path = []
        for coll in obj.users_collection:
            hierarchy = find_collection_hierarchy(coll, [coll.name])
            if hierarchy:
                collection_path.extend(hierarchy)
                break

        if collection_path and (collection_path[0] == 'Scene Collection' or collection_path[0] == 'Master Collection'):
            collection_path = collection_path[1:]
        # Skip 'Collection' - it's just a Blender container, not part of the asset path
        if collection_path and collection_path[0] == 'Collection':
            collection_path = collection_path[1:]

        return '/'.join(collection_path)

    def get_ab_base_path(self):
        """
        Retrieves the base path for the asset bridge.

        Returns:
            str: The base path for the asset bridge.
        """
        return get_bridge_directory()

    def get_export_path(self, obj):
        """
        Retrieves the export path for the given object and ensures the directory structure is in place.
        Uses preserved AB_internalPath if available (from Unreal import), otherwise derives from collection.

        Parameters:
            obj (bpy.types.Object): The object for which the export path is to be retrieved.

        Returns:
            str: The export path for the object.
        """
        base_path = self.get_ab_base_path()
        # Prefer preserved internal path from Unreal import over collection hierarchy
        # This prevents issues with Blender renaming collections (e.g., Meshes.001)
        internal_path = obj.get("AB_internalPath", "")
        if internal_path:
            # Remove leading slash if present for path joining
            collection_path = internal_path.lstrip("/")
        else:
            collection_path = self.get_collection_hierarchy_path(obj)
        # Use AB_shortName for filename (handles EMPTY roots in skeletal hierarchies)
        filename = obj.get("AB_shortName", obj.name)
        export_path = os.path.join(base_path, collection_path, filename + ".glb")
        normalized_export_path = os.path.normpath(export_path)
        os.makedirs(os.path.dirname(normalized_export_path), exist_ok=True)
        return normalized_export_path

    def invoke(self, context, event):
        self.execute(context)
        return {'FINISHED'}
        # wm = context.window_manager
        # return wm.invoke_props_dialog(self)

    def draw(self, context):
        return {'FINISHED'}
        # layout = self.layout
        # layout.prop(self, "object_path")
        # layout.prop(self, "apply_transformations")
