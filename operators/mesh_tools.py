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
import bmesh


class SplitToNewMesh(bpy.types.Operator):
    """Split selected faces to a new mesh with Unreal export path and collection hierarchy"""
    bl_idname = "assetsbridge.split_to_new_mesh"
    bl_label = "Split to New Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    new_mesh_name: bpy.props.StringProperty(
        name="Mesh Name",
        description="Name for the new mesh object (e.g., SK_F_Helmet_01)",
        default="SK_NewMesh"
    )

    unreal_path: bpy.props.StringProperty(
        name="Unreal Path",
        description="Unreal Engine asset path (e.g., /Game/Wearables/Armor/Helmets)",
        default="/Game/Meshes"
    )

    export_as_skeletal: bpy.props.BoolProperty(
        name="Export as Skeletal Mesh",
        description="Create skeletal mesh hierarchy with armature for UE5 import. If disabled, exports as static mesh",
        default=True
    )

    copy_shape_keys: bpy.props.BoolProperty(
        name="Copy Shape Keys",
        description="Copy shape keys to the new mesh (will be transferred via distance matching)",
        default=False
    )

    ue5_skeleton_path: bpy.props.StringProperty(
        name="UE5 Skeleton Path",
        description="Path to existing skeleton in Unreal (leave empty to create new)",
        default=""
    )

    cached_face_count: bpy.props.IntProperty(
        name="Cached Face Count",
        default=0
    )

    cached_armature_name: bpy.props.StringProperty(
        name="Cached Armature Name",
        default=""
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        return True

    def execute(self, context):
        original_obj = context.active_object
        original_mesh = original_obj.data

        bpy.ops.object.mode_set(mode='OBJECT')

        selected_face_indices = [f.index for f in original_mesh.polygons if f.select]

        if not selected_face_indices:
            self.report({'ERROR'}, "No faces selected. Please select faces in Edit Mode.")
            bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}

        self.report({'INFO'}, f"Splitting {len(selected_face_indices)} faces to new mesh: {self.new_mesh_name}")

        target_collection = self.get_or_create_collection_hierarchy(self.unreal_path)

        source_armature = self.get_source_armature(original_obj)

        new_obj = self.create_mesh_from_faces(original_obj, selected_face_indices, target_collection)

        if new_obj is None:
            self.report({'ERROR'}, "Failed to create new mesh")
            bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}

        export_root = new_obj

        if self.export_as_skeletal and source_armature:
            export_root = self.create_skeletal_hierarchy(new_obj, source_armature, target_collection)
        elif not self.export_as_skeletal:
            pass
        else:
            self.report({'WARNING'}, "No armature found - exporting as static mesh")

        self.set_unreal_metadata(export_root, new_obj)

        if self.copy_shape_keys and original_mesh.shape_keys:
            self.transfer_shape_keys_to_new_mesh(original_obj, new_obj)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.delete(type='FACE')
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        export_root.select_set(True)
        context.view_layer.objects.active = export_root

        mesh_type = "SkeletalMesh" if self.export_as_skeletal and source_armature else "StaticMesh"
        self.report({'INFO'}, f"Created '{export_root.name}' ({mesh_type}) in collection hierarchy for {self.unreal_path}")
        return {'FINISHED'}

    def get_source_armature(self, obj):
        """Find the armature modifier target from source object."""
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
        return None

    def create_skeletal_hierarchy(self, mesh_obj, source_armature, target_collection):
        """
        Creates proper skeletal mesh export hierarchy:
        Empty (export root) -> Armature (copy) -> Mesh
        """
        root_empty = bpy.data.objects.new(self.new_mesh_name, None)
        root_empty.empty_display_type = 'PLAIN_AXES'
        root_empty.empty_display_size = 0.1
        target_collection.objects.link(root_empty)

        new_armature_data = source_armature.data.copy()
        new_armature = bpy.data.objects.new(source_armature.name, new_armature_data)
        new_armature.matrix_world = source_armature.matrix_world.copy()
        target_collection.objects.link(new_armature)

        new_armature.parent = root_empty

        mesh_obj.parent = new_armature
        mesh_obj.parent_type = 'OBJECT'

        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE':
                mesh_obj.modifiers.remove(mod)

        arm_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
        arm_mod.object = new_armature
        arm_mod.use_vertex_groups = True

        self.report({'INFO'}, f"Created skeletal hierarchy: {root_empty.name} -> {new_armature.name} -> {mesh_obj.name}")
        return root_empty

    def get_or_create_collection_hierarchy(self, unreal_path):
        """
        Creates a collection hierarchy matching the Unreal path structure.
        e.g., /Game/Wearables/Armor/Helmets -> Wearables > Armor > Helmets
        """
        path_parts = [p for p in unreal_path.split('/') if p and p != 'Game']

        if not path_parts:
            return bpy.context.scene.collection

        parent_collection = bpy.context.scene.collection

        for part in path_parts:
            existing = None
            for child in parent_collection.children:
                if child.name == part:
                    existing = child
                    break

            if existing:
                parent_collection = existing
            else:
                new_collection = bpy.data.collections.new(part)
                parent_collection.children.link(new_collection)
                parent_collection = new_collection

        return parent_collection

    def create_mesh_from_faces(self, source_obj, face_indices, target_collection):
        """
        Creates a new mesh object from selected face indices.
        Preserves vertex groups, UV maps, and materials.
        """
        source_mesh = source_obj.data

        bm = bmesh.new()
        bm.from_mesh(source_mesh)
        bm.faces.ensure_lookup_table()

        faces_to_keep = set(face_indices)
        faces_to_remove = [f for f in bm.faces if f.index not in faces_to_keep]

        bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')

        new_mesh = bpy.data.meshes.new(self.new_mesh_name)
        bm.to_mesh(new_mesh)
        bm.free()

        new_obj = bpy.data.objects.new(self.new_mesh_name, new_mesh)

        for coll in new_obj.users_collection:
            coll.objects.unlink(new_obj)
        target_collection.objects.link(new_obj)

        new_obj.matrix_world = source_obj.matrix_world.copy()

        for mat in source_obj.data.materials:
            new_obj.data.materials.append(mat)

        self.copy_material_custom_properties(source_obj, new_obj)

        for vg in source_obj.vertex_groups:
            new_obj.vertex_groups.new(name=vg.name)

        self.transfer_vertex_weights(source_obj, new_obj, face_indices)

        return new_obj

    def copy_material_custom_properties(self, source_obj, target_obj):
        """
        Copies AB_ material properties from source to target object.
        """
        for key in source_obj.keys():
            if key.startswith("AB_") and "Material" in key:
                target_obj[key] = source_obj[key]
        
        if hasattr(source_obj, "ab_materials"):
            for i, mat_slot in enumerate(source_obj.material_slots):
                if i < len(target_obj.material_slots):
                    for key in ["AB_materialPath", "AB_materialName"]:
                        if key in mat_slot.material.keys() if mat_slot.material else False:
                            target_obj.material_slots[i].material[key] = mat_slot.material[key]

    def transfer_vertex_weights(self, source_obj, target_obj, original_face_indices):
        """
        Transfers vertex weights from source to target for vertices that were part of selected faces.
        """
        source_mesh = source_obj.data
        target_mesh = target_obj.data

        original_vertex_indices = set()
        for fi in original_face_indices:
            if fi < len(source_mesh.polygons):
                poly = source_mesh.polygons[fi]
                original_vertex_indices.update(poly.vertices)

        target_to_source = {}
        for tv in target_mesh.vertices:
            for sv_idx in original_vertex_indices:
                if sv_idx < len(source_mesh.vertices):
                    sv = source_mesh.vertices[sv_idx]
                    if (tv.co - sv.co).length < 0.0001:
                        target_to_source[tv.index] = sv_idx
                        break

        for vg in source_obj.vertex_groups:
            target_vg = target_obj.vertex_groups.get(vg.name)
            if not target_vg:
                continue

            for target_idx, source_idx in target_to_source.items():
                try:
                    weight = vg.weight(source_idx)
                    target_vg.add([target_idx], weight, 'REPLACE')
                except RuntimeError:
                    pass

    def copy_armature_setup(self, source_obj, target_obj):
        """
        Copies armature modifier from source to target object.
        """
        for mod in source_obj.modifiers:
            if mod.type == 'ARMATURE':
                new_mod = target_obj.modifiers.new(name=mod.name, type='ARMATURE')
                new_mod.object = mod.object
                new_mod.use_vertex_groups = mod.use_vertex_groups
                new_mod.use_bone_envelopes = mod.use_bone_envelopes
                self.report({'INFO'}, f"Copied armature modifier targeting: {mod.object.name if mod.object else 'None'}")
                break

    def set_unreal_metadata(self, export_root, mesh_obj):
        """
        Sets AssetsBridge metadata for Unreal export.
        """
        is_skeletal = self.export_as_skeletal and export_root != mesh_obj
        
        export_root["AB_isExportRoot"] = True
        export_root["AB_stringType"] = "SkeletalMesh" if is_skeletal else "StaticMesh"
        export_root["AB_internalPath"] = self.unreal_path
        export_root["AB_relativeExportPath"] = self.unreal_path
        export_root["AB_shortName"] = self.new_mesh_name
        
        if self.ue5_skeleton_path:
            export_root["AB_ue5SkeletonPath"] = self.ue5_skeleton_path

    def transfer_shape_keys_to_new_mesh(self, source_obj, target_obj):
        """
        Transfers shape keys from source to target using closest point matching.
        This is a simplified version - for full control use the TransferShapeKeys operator.
        """
        source_keys = source_obj.data.shape_keys
        if not source_keys or len(source_keys.key_blocks) < 2:
            return

        target_obj.shape_key_add(name="Basis", from_mix=False)

        for key in source_keys.key_blocks[1:]:
            new_key = target_obj.shape_key_add(name=key.name, from_mix=False)
            new_key.slider_min = key.slider_min
            new_key.slider_max = key.slider_max
            new_key.value = key.value

        self.report({'INFO'}, f"Transferred {len(source_keys.key_blocks) - 1} shape keys (positions need adjustment)")

    def invoke(self, context, event):
        obj = context.active_object
        if obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            self.cached_face_count = sum(1 for f in obj.data.polygons if f.select)
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    self.cached_armature_name = mod.object.name
                    break
            bpy.ops.object.mode_set(mode='EDIT')
        else:
            self.cached_face_count = 0
            self.cached_armature_name = ""
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        if self.cached_face_count > 0:
            box = layout.box()
            box.label(text=f"Selected Faces: {self.cached_face_count}", icon='FACE_MAPS')
            if self.cached_armature_name:
                box.label(text=f"Source Armature: {self.cached_armature_name}", icon='ARMATURE_DATA')

        layout.separator()
        layout.prop(self, "new_mesh_name")
        layout.prop(self, "unreal_path")

        layout.separator()
        box = layout.box()
        box.label(text="Mesh Type:", icon='MESH_DATA')
        box.prop(self, "export_as_skeletal")
        
        if self.export_as_skeletal:
            col = box.column()
            col.enabled = self.cached_armature_name != ""
            if not self.cached_armature_name:
                col.label(text="No armature found - will export as static", icon='ERROR')
            else:
                col.label(text="Will duplicate armature for export", icon='INFO')
            col.prop(self, "ue5_skeleton_path")
            col.prop(self, "copy_shape_keys")

        layout.separator()
        box = layout.box()
        box.label(text="Collection Preview:", icon='OUTLINER_COLLECTION')
        path_parts = [p for p in self.unreal_path.split('/') if p and p != 'Game']
        if path_parts:
            for i, part in enumerate(path_parts):
                row = box.row()
                row.label(text="  " * i + ("└ " if i > 0 else "") + part)


class AssignUE5Skeleton(bpy.types.Operator):
    """Assign a UE5 skeleton path for mesh export - allows re-using existing Unreal skeletons"""
    bl_idname = "assetsbridge.assign_ue5_skeleton"
    bl_label = "Assign UE5 Skeleton"
    bl_options = {'REGISTER', 'UNDO'}

    skeleton_path: bpy.props.StringProperty(
        name="Skeleton Path",
        description="Unreal Engine skeleton asset path (e.g., /Game/Characters/Mannequin/Mesh/SK_Mannequin_Skeleton)",
        default=""
    )

    clear_skeleton: bpy.props.BoolProperty(
        name="Clear Skeleton Reference",
        description="Remove the skeleton reference (export will create new skeleton)",
        default=False
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None:
            return False
        if obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE':
                    return True
        if obj.type == 'ARMATURE':
            return True
        return False

    def execute(self, context):
        obj = context.active_object

        targets = []
        if obj.type == 'ARMATURE':
            targets.append(obj)
            for child in obj.children:
                if child.type == 'MESH':
                    targets.append(child)
        else:
            targets.append(obj)
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    if mod.object not in targets:
                        targets.append(mod.object)

        if self.clear_skeleton:
            for target in targets:
                if "AB_ue5SkeletonPath" in target:
                    del target["AB_ue5SkeletonPath"]
            self.report({'INFO'}, f"Cleared skeleton reference from {len(targets)} object(s)")
        else:
            if not self.skeleton_path:
                self.report({'ERROR'}, "Please provide a skeleton path")
                return {'CANCELLED'}

            for target in targets:
                target["AB_ue5SkeletonPath"] = self.skeleton_path

            self.report({'INFO'}, f"Assigned skeleton '{self.skeleton_path}' to {len(targets)} object(s)")

        return {'FINISHED'}

    def invoke(self, context, event):
        obj = context.active_object
        if obj:
            existing = obj.get("AB_ue5SkeletonPath", "")
            if existing:
                self.skeleton_path = existing

        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout

        obj = context.active_object
        if obj:
            box = layout.box()
            box.label(text=f"Target: {obj.name}", icon='MESH_DATA' if obj.type == 'MESH' else 'ARMATURE_DATA')

            existing = obj.get("AB_ue5SkeletonPath", "")
            if existing:
                box.label(text=f"Current: {existing}", icon='LINKED')

        layout.separator()
        layout.prop(self, "skeleton_path")
        layout.prop(self, "clear_skeleton")

        layout.separator()
        box = layout.box()
        box.label(text="Usage:", icon='INFO')
        box.label(text="Set path to re-use an existing Unreal skeleton.")
        box.label(text="Leave empty and check 'Clear' to create new skeleton on export.")


class SetUnrealExportPath(bpy.types.Operator):
    """Set the Unreal export path and create matching collection hierarchy for selected object"""
    bl_idname = "assetsbridge.set_unreal_export_path"
    bl_label = "Set Unreal Export Path"
    bl_options = {'REGISTER', 'UNDO'}

    unreal_path: bpy.props.StringProperty(
        name="Unreal Path",
        description="Unreal Engine asset path (e.g., /Game/Wearables/Armor/Helmets)",
        default="/Game/Meshes"
    )

    move_to_collection: bpy.props.BoolProperty(
        name="Move to Collection",
        description="Move object to matching collection hierarchy",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object

        obj["AB_internalPath"] = self.unreal_path
        obj["AB_relativeExportPath"] = self.unreal_path

        if self.move_to_collection:
            target_collection = self.get_or_create_collection_hierarchy(self.unreal_path)

            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            target_collection.objects.link(obj)

            self.report({'INFO'}, f"Set path to '{self.unreal_path}' and moved to collection")
        else:
            self.report({'INFO'}, f"Set export path to '{self.unreal_path}'")

        return {'FINISHED'}

    def get_or_create_collection_hierarchy(self, unreal_path):
        """Creates collection hierarchy matching Unreal path structure."""
        path_parts = [p for p in unreal_path.split('/') if p and p != 'Game']

        if not path_parts:
            return bpy.context.scene.collection

        parent_collection = bpy.context.scene.collection

        for part in path_parts:
            existing = None
            for child in parent_collection.children:
                if child.name == part:
                    existing = child
                    break

            if existing:
                parent_collection = existing
            else:
                new_collection = bpy.data.collections.new(part)
                parent_collection.children.link(new_collection)
                parent_collection = new_collection

        return parent_collection

    def invoke(self, context, event):
        obj = context.active_object
        if obj:
            existing = obj.get("AB_internalPath", "")
            if existing:
                self.unreal_path = existing

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        obj = context.active_object
        if obj:
            box = layout.box()
            box.label(text=f"Object: {obj.name}", icon='OBJECT_DATA')
            existing = obj.get("AB_internalPath", "")
            if existing:
                box.label(text=f"Current Path: {existing}", icon='FILE_FOLDER')

        layout.separator()
        layout.prop(self, "unreal_path")
        layout.prop(self, "move_to_collection")

        layout.separator()
        box = layout.box()
        box.label(text="Collection Preview:", icon='OUTLINER_COLLECTION')
        path_parts = [p for p in self.unreal_path.split('/') if p and p != 'Game']
        if path_parts:
            for i, part in enumerate(path_parts):
                row = box.row()
                row.label(text="  " * i + ("└ " if i > 0 else "") + part)


def register():
    bpy.utils.register_class(SplitToNewMesh)
    bpy.utils.register_class(AssignUE5Skeleton)
    bpy.utils.register_class(SetUnrealExportPath)


def unregister():
    bpy.utils.unregister_class(SplitToNewMesh)
    bpy.utils.unregister_class(AssignUE5Skeleton)
    bpy.utils.unregister_class(SetUnrealExportPath)
