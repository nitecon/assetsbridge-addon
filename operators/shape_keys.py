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
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import PropertyGroup


class ShapeKeySelectionItem(PropertyGroup):
    """Property group for shape key selection in the UI"""
    name: StringProperty(name="Name")
    selected: BoolProperty(name="Selected", default=True)


class TransferShapeKeys(bpy.types.Operator):
    """Transfer shape keys from source mesh to target mesh using closest point mapping"""
    bl_idname = "assetsbridge.transfer_shape_keys"
    bl_label = "Transfer Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    distance_threshold: bpy.props.FloatProperty(
        name="Distance Threshold",
        description="Maximum distance for vertex matching (0 = unlimited)",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH'
    )
    
    use_topology: bpy.props.BoolProperty(
        name="Use Topology",
        description="Attempt topology-based transfer first (faster for matching meshes)",
        default=True
    )
    
    interpolation_falloff: bpy.props.FloatProperty(
        name="Falloff",
        description="Smoothing falloff for distant vertices (0 = sharp, 1 = smooth)",
        default=0.5,
        min=0.0,
        max=1.0
    )
    
    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Overwrite shape keys with same name on target",
        default=False
    )

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 2:
            return False
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        return len(meshes) == 2 and context.active_object in meshes

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if len(selected_meshes) != 2:
            self.report({'ERROR'}, "Please select exactly 2 mesh objects")
            return {'CANCELLED'}
        
        target_obj = context.active_object
        source_obj = [obj for obj in selected_meshes if obj != target_obj][0]
        
        if not source_obj.data.shape_keys:
            self.report({'ERROR'}, f"Source mesh '{source_obj.name}' has no shape keys")
            return {'CANCELLED'}
        
        if len(source_obj.data.shape_keys.key_blocks) < 2:
            self.report({'ERROR'}, f"Source mesh '{source_obj.name}' has no shape keys beyond Basis")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Transferring shape keys from '{source_obj.name}' to '{target_obj.name}'")
        
        transferred_count = self.transfer_shape_keys(source_obj, target_obj)
        
        if transferred_count > 0:
            self.report({'INFO'}, f"Successfully transferred {transferred_count} shape key(s)")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No shape keys were transferred")
            return {'CANCELLED'}

    def transfer_shape_keys(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data
        
        if not target_mesh.shape_keys:
            target_obj.shape_key_add(name="Basis", from_mix=False)
        
        vertex_mapping = self.build_vertex_mapping(source_obj, target_obj)
        
        if vertex_mapping is None:
            self.report({'ERROR'}, "Failed to build vertex mapping")
            return 0
        
        transferred = 0
        source_keys = source_mesh.shape_keys.key_blocks
        basis_key = source_keys[0]
        
        for shape_key in source_keys[1:]:
            if not self.overwrite_existing:
                existing = target_mesh.shape_keys.key_blocks.get(shape_key.name)
                if existing:
                    self.report({'INFO'}, f"Skipping '{shape_key.name}' (already exists)")
                    continue
            else:
                existing = target_mesh.shape_keys.key_blocks.get(shape_key.name)
                if existing:
                    target_obj.shape_key_remove(existing)
            
            new_key = target_obj.shape_key_add(name=shape_key.name, from_mix=False)
            new_key.slider_min = shape_key.slider_min
            new_key.slider_max = shape_key.slider_max
            new_key.value = shape_key.value
            
            self.apply_shape_key_deltas(
                basis_key, 
                shape_key, 
                new_key, 
                target_mesh,
                vertex_mapping
            )
            
            transferred += 1
        
        return transferred

    def build_vertex_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data
        
        if self.use_topology and len(source_mesh.vertices) == len(target_mesh.vertices):
            self.report({'INFO'}, "Using topology-based mapping (vertex counts match)")
            return self.build_topology_mapping(source_obj, target_obj)
        
        self.report({'INFO'}, "Using closest-point surface mapping")
        return self.build_closest_point_mapping(source_obj, target_obj)

    def build_topology_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data
        
        mapping = []
        
        source_world_matrix = source_obj.matrix_world
        target_world_matrix = target_obj.matrix_world
        target_world_matrix_inv = target_world_matrix.inverted()
        
        for target_idx, target_vert in enumerate(target_mesh.vertices):
            source_vert = source_mesh.vertices[target_idx]
            
            source_world_pos = source_world_matrix @ source_vert.co
            target_world_pos = target_world_matrix @ target_vert.co
            
            distance = (source_world_pos - target_world_pos).length
            
            if self.distance_threshold > 0 and distance > self.distance_threshold:
                weight = max(0.0, 1.0 - (distance - self.distance_threshold) * self.interpolation_falloff)
            else:
                weight = 1.0
            
            mapping.append({
                'target_idx': target_idx,
                'source_indices': [target_idx],
                'weights': [weight],
                'distance': distance
            })
        
        return mapping

    def build_closest_point_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data
        
        source_world_matrix = source_obj.matrix_world
        target_world_matrix = target_obj.matrix_world
        
        bm_source = bmesh.new()
        bm_source.from_mesh(source_mesh)
        bm_source.transform(source_world_matrix)
        bmesh.ops.triangulate(bm_source, faces=bm_source.faces)
        bm_source.faces.ensure_lookup_table()
        bm_source.verts.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm_source)
        
        source_verts_world = [source_world_matrix @ v.co for v in source_mesh.vertices]
        
        mapping = []
        
        for target_idx, target_vert in enumerate(target_mesh.vertices):
            target_world_pos = target_world_matrix @ target_vert.co
            
            location, normal, face_idx, distance = bvh.find_nearest(target_world_pos)
            
            if location is None:
                mapping.append({
                    'target_idx': target_idx,
                    'source_indices': [],
                    'weights': [],
                    'distance': float('inf')
                })
                continue
            
            if self.distance_threshold > 0 and distance > self.distance_threshold:
                dist_weight = max(0.0, 1.0 - (distance - self.distance_threshold) * self.interpolation_falloff * 10)
            else:
                dist_weight = 1.0
            
            source_face = bm_source.faces[face_idx]
            face_vert_indices = [v.index for v in source_face.verts]
            face_vert_positions = [source_verts_world[i] for i in face_vert_indices]
            
            bary_weights = self.compute_barycentric_weights(location, face_vert_positions)
            
            final_weights = [w * dist_weight for w in bary_weights]
            
            mapping.append({
                'target_idx': target_idx,
                'source_indices': face_vert_indices,
                'weights': final_weights,
                'distance': distance
            })
        
        bm_source.free()
        return mapping

    def compute_barycentric_weights(self, point, triangle_verts):
        if len(triangle_verts) < 3:
            return [1.0 / len(triangle_verts)] * len(triangle_verts) if triangle_verts else []
        
        v0 = triangle_verts[0]
        v1 = triangle_verts[1]
        v2 = triangle_verts[2]
        
        v0v1 = v1 - v0
        v0v2 = v2 - v0
        v0p = point - v0
        
        d00 = v0v1.dot(v0v1)
        d01 = v0v1.dot(v0v2)
        d11 = v0v2.dot(v0v2)
        d20 = v0p.dot(v0v1)
        d21 = v0p.dot(v0v2)
        
        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-10:
            return [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        
        v = (d11 * d20 - d01 * d21) / denom
        w = (d00 * d21 - d01 * d20) / denom
        u = 1.0 - v - w
        
        weights = [max(0.0, u), max(0.0, v), max(0.0, w)]
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            weights = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        
        if len(triangle_verts) > 3:
            weights.extend([0.0] * (len(triangle_verts) - 3))
        
        return weights

    def apply_shape_key_deltas(self, source_basis, source_shape, target_shape, target_mesh, vertex_mapping):
        source_basis_coords = [Vector(v.co) for v in source_basis.data]
        source_shape_coords = [Vector(v.co) for v in source_shape.data]
        
        source_deltas = [
            source_shape_coords[i] - source_basis_coords[i] 
            for i in range(len(source_basis_coords))
        ]
        
        target_basis = target_mesh.shape_keys.key_blocks[0]
        
        for map_entry in vertex_mapping:
            target_idx = map_entry['target_idx']
            source_indices = map_entry['source_indices']
            weights = map_entry['weights']
            
            if not source_indices or not weights:
                continue
            
            interpolated_delta = Vector((0.0, 0.0, 0.0))
            
            for src_idx, weight in zip(source_indices, weights):
                if src_idx < len(source_deltas):
                    interpolated_delta += source_deltas[src_idx] * weight
            
            target_shape.data[target_idx].co = target_basis.data[target_idx].co + interpolated_delta

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) == 2:
            target_obj = context.active_object
            source_obj = [obj for obj in selected_meshes if obj != target_obj][0]
            
            box = layout.box()
            box.label(text="Transfer Direction:", icon='FORWARD')
            row = box.row()
            row.label(text=f"Source: {source_obj.name}", icon='MESH_DATA')
            row = box.row()
            row.label(text=f"Target: {target_obj.name}", icon='MESH_DATA')
            
            if source_obj.data.shape_keys:
                key_count = len(source_obj.data.shape_keys.key_blocks) - 1
                row = box.row()
                row.label(text=f"Shape Keys: {key_count}", icon='SHAPEKEY_DATA')
        
        layout.separator()
        layout.prop(self, "use_topology")
        layout.prop(self, "distance_threshold")
        layout.prop(self, "interpolation_falloff")
        layout.prop(self, "overwrite_existing")


class SelectiveTransferShapeKeys(bpy.types.Operator):
    """Transfer selected shape keys from source mesh to target mesh"""
    bl_idname = "assetsbridge.selective_transfer_shape_keys"
    bl_label = "Selective Shape Key Transfer"
    bl_options = {'REGISTER', 'UNDO'}

    distance_threshold: bpy.props.FloatProperty(
        name="Distance Threshold",
        description="Maximum distance for vertex matching (0 = unlimited)",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH'
    )

    use_topology: bpy.props.BoolProperty(
        name="Use Topology",
        description="Attempt topology-based transfer first (faster for matching meshes)",
        default=True
    )

    interpolation_falloff: bpy.props.FloatProperty(
        name="Falloff",
        description="Smoothing falloff for distant vertices (0 = sharp, 1 = smooth)",
        default=0.5,
        min=0.0,
        max=1.0
    )

    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Overwrite shape keys with same name on target",
        default=False
    )

    shape_key_selection: CollectionProperty(type=ShapeKeySelectionItem)
    selection_initialized: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 2:
            return False
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        return len(meshes) == 2 and context.active_object in meshes

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if len(selected_meshes) != 2:
            self.report({'ERROR'}, "Please select exactly 2 mesh objects")
            return {'CANCELLED'}

        target_obj = context.active_object
        source_obj = [obj for obj in selected_meshes if obj != target_obj][0]

        if not source_obj.data.shape_keys:
            self.report({'ERROR'}, f"Source mesh '{source_obj.name}' has no shape keys")
            return {'CANCELLED'}

        selected_keys = [item.name for item in self.shape_key_selection if item.selected]

        if not selected_keys:
            self.report({'WARNING'}, "No shape keys selected for transfer")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Transferring {len(selected_keys)} shape key(s) from '{source_obj.name}' to '{target_obj.name}'")

        transferred_count = self.transfer_selected_shape_keys(source_obj, target_obj, selected_keys)

        if transferred_count > 0:
            self.report({'INFO'}, f"Successfully transferred {transferred_count} shape key(s)")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No shape keys were transferred")
            return {'CANCELLED'}

    def transfer_selected_shape_keys(self, source_obj, target_obj, selected_key_names):
        source_mesh = source_obj.data
        target_mesh = target_obj.data

        if not target_mesh.shape_keys:
            target_obj.shape_key_add(name="Basis", from_mix=False)

        vertex_mapping = self.build_vertex_mapping(source_obj, target_obj)

        if vertex_mapping is None:
            self.report({'ERROR'}, "Failed to build vertex mapping")
            return 0

        transferred = 0
        source_keys = source_mesh.shape_keys.key_blocks
        basis_key = source_keys[0]

        for shape_key in source_keys[1:]:
            if shape_key.name not in selected_key_names:
                continue

            if not self.overwrite_existing:
                existing = target_mesh.shape_keys.key_blocks.get(shape_key.name)
                if existing:
                    self.report({'INFO'}, f"Skipping '{shape_key.name}' (already exists)")
                    continue
            else:
                existing = target_mesh.shape_keys.key_blocks.get(shape_key.name)
                if existing:
                    target_obj.shape_key_remove(existing)

            new_key = target_obj.shape_key_add(name=shape_key.name, from_mix=False)
            new_key.slider_min = shape_key.slider_min
            new_key.slider_max = shape_key.slider_max
            new_key.value = shape_key.value

            self.apply_shape_key_deltas(
                basis_key,
                shape_key,
                new_key,
                target_mesh,
                vertex_mapping
            )

            transferred += 1

        return transferred

    def build_vertex_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data

        if self.use_topology and len(source_mesh.vertices) == len(target_mesh.vertices):
            self.report({'INFO'}, "Using topology-based mapping (vertex counts match)")
            return self.build_topology_mapping(source_obj, target_obj)

        self.report({'INFO'}, "Using closest-point surface mapping")
        return self.build_closest_point_mapping(source_obj, target_obj)

    def build_topology_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data

        mapping = []

        source_world_matrix = source_obj.matrix_world
        target_world_matrix = target_obj.matrix_world

        for target_idx, target_vert in enumerate(target_mesh.vertices):
            source_vert = source_mesh.vertices[target_idx]

            source_world_pos = source_world_matrix @ source_vert.co
            target_world_pos = target_world_matrix @ target_vert.co

            distance = (source_world_pos - target_world_pos).length

            if self.distance_threshold > 0 and distance > self.distance_threshold:
                weight = max(0.0, 1.0 - (distance - self.distance_threshold) * self.interpolation_falloff)
            else:
                weight = 1.0

            mapping.append({
                'target_idx': target_idx,
                'source_indices': [target_idx],
                'weights': [weight],
                'distance': distance
            })

        return mapping

    def build_closest_point_mapping(self, source_obj, target_obj):
        source_mesh = source_obj.data
        target_mesh = target_obj.data

        source_world_matrix = source_obj.matrix_world
        target_world_matrix = target_obj.matrix_world

        bm_source = bmesh.new()
        bm_source.from_mesh(source_mesh)
        bm_source.transform(source_world_matrix)
        bmesh.ops.triangulate(bm_source, faces=bm_source.faces)
        bm_source.faces.ensure_lookup_table()
        bm_source.verts.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm_source)

        source_verts_world = [source_world_matrix @ v.co for v in source_mesh.vertices]

        mapping = []

        for target_idx, target_vert in enumerate(target_mesh.vertices):
            target_world_pos = target_world_matrix @ target_vert.co

            location, normal, face_idx, distance = bvh.find_nearest(target_world_pos)

            if location is None:
                mapping.append({
                    'target_idx': target_idx,
                    'source_indices': [],
                    'weights': [],
                    'distance': float('inf')
                })
                continue

            if self.distance_threshold > 0 and distance > self.distance_threshold:
                dist_weight = max(0.0, 1.0 - (distance - self.distance_threshold) * self.interpolation_falloff * 10)
            else:
                dist_weight = 1.0

            source_face = bm_source.faces[face_idx]
            face_vert_indices = [v.index for v in source_face.verts]
            face_vert_positions = [source_verts_world[i] for i in face_vert_indices]

            bary_weights = self.compute_barycentric_weights(location, face_vert_positions)

            final_weights = [w * dist_weight for w in bary_weights]

            mapping.append({
                'target_idx': target_idx,
                'source_indices': face_vert_indices,
                'weights': final_weights,
                'distance': distance
            })

        bm_source.free()
        return mapping

    def compute_barycentric_weights(self, point, triangle_verts):
        if len(triangle_verts) < 3:
            return [1.0 / len(triangle_verts)] * len(triangle_verts) if triangle_verts else []

        v0 = triangle_verts[0]
        v1 = triangle_verts[1]
        v2 = triangle_verts[2]

        v0v1 = v1 - v0
        v0v2 = v2 - v0
        v0p = point - v0

        d00 = v0v1.dot(v0v1)
        d01 = v0v1.dot(v0v2)
        d11 = v0v2.dot(v0v2)
        d20 = v0p.dot(v0v1)
        d21 = v0p.dot(v0v2)

        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-10:
            return [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]

        v = (d11 * d20 - d01 * d21) / denom
        w = (d00 * d21 - d01 * d20) / denom
        u = 1.0 - v - w

        weights = [max(0.0, u), max(0.0, v), max(0.0, w)]
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            weights = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]

        if len(triangle_verts) > 3:
            weights.extend([0.0] * (len(triangle_verts) - 3))

        return weights

    def apply_shape_key_deltas(self, source_basis, source_shape, target_shape, target_mesh, vertex_mapping):
        source_basis_coords = [Vector(v.co) for v in source_basis.data]
        source_shape_coords = [Vector(v.co) for v in source_shape.data]

        source_deltas = [
            source_shape_coords[i] - source_basis_coords[i]
            for i in range(len(source_basis_coords))
        ]

        target_basis = target_mesh.shape_keys.key_blocks[0]

        for map_entry in vertex_mapping:
            target_idx = map_entry['target_idx']
            source_indices = map_entry['source_indices']
            weights = map_entry['weights']

            if not source_indices or not weights:
                continue

            interpolated_delta = Vector((0.0, 0.0, 0.0))

            for src_idx, weight in zip(source_indices, weights):
                if src_idx < len(source_deltas):
                    interpolated_delta += source_deltas[src_idx] * weight

            target_shape.data[target_idx].co = target_basis.data[target_idx].co + interpolated_delta

    def invoke(self, context, event):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) == 2:
            target_obj = context.active_object
            source_obj = [obj for obj in selected_meshes if obj != target_obj][0]

            if source_obj.data.shape_keys:
                self.shape_key_selection.clear()
                for key in source_obj.data.shape_keys.key_blocks[1:]:
                    item = self.shape_key_selection.add()
                    item.name = key.name
                    item.selected = True

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) == 2:
            target_obj = context.active_object
            source_obj = [obj for obj in selected_meshes if obj != target_obj][0]

            box = layout.box()
            box.label(text="Transfer Direction:", icon='FORWARD')
            row = box.row()
            row.label(text=f"Source: {source_obj.name}", icon='MESH_DATA')
            row = box.row()
            row.label(text=f"Target: {target_obj.name}", icon='MESH_DATA')

        layout.separator()

        box = layout.box()
        row = box.row()
        row.label(text="Select Shape Keys to Transfer:", icon='SHAPEKEY_DATA')

        row = box.row()
        row.operator("assetsbridge.select_all_shape_keys", text="Select All")
        row.operator("assetsbridge.deselect_all_shape_keys", text="Deselect All")

        col = box.column(align=True)
        for item in self.shape_key_selection:
            row = col.row()
            row.prop(item, "selected", text=item.name)

        selected_count = sum(1 for item in self.shape_key_selection if item.selected)
        total_count = len(self.shape_key_selection)
        box.label(text=f"Selected: {selected_count} / {total_count}")

        layout.separator()
        layout.prop(self, "use_topology")
        layout.prop(self, "distance_threshold")
        layout.prop(self, "interpolation_falloff")
        layout.prop(self, "overwrite_existing")


class SelectAllShapeKeys(bpy.types.Operator):
    """Select all shape keys for transfer"""
    bl_idname = "assetsbridge.select_all_shape_keys"
    bl_label = "Select All"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


class DeselectAllShapeKeys(bpy.types.Operator):
    """Deselect all shape keys for transfer"""
    bl_idname = "assetsbridge.deselect_all_shape_keys"
    bl_label = "Deselect All"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


def register():
    bpy.utils.register_class(ShapeKeySelectionItem)
    bpy.utils.register_class(TransferShapeKeys)
    bpy.utils.register_class(SelectiveTransferShapeKeys)
    bpy.utils.register_class(SelectAllShapeKeys)
    bpy.utils.register_class(DeselectAllShapeKeys)


def unregister():
    bpy.utils.unregister_class(DeselectAllShapeKeys)
    bpy.utils.unregister_class(SelectAllShapeKeys)
    bpy.utils.unregister_class(SelectiveTransferShapeKeys)
    bpy.utils.unregister_class(TransferShapeKeys)
    bpy.utils.unregister_class(ShapeKeySelectionItem)
