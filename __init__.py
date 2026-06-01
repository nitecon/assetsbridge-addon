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
from bpy.props import StringProperty, CollectionProperty, BoolProperty, FloatProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup, AddonPreferences

from . import operators
from .operators.bake import RESOLUTION_ITEMS

bl_info = {
    "name": "AssetsBridge",
    "author": "Nitecon Studios LLC.",
    "version": (1, 3, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Toolbar > AssetsBridge",
    "description": "AssetsBridge provides bi directional integration with unreal engine.",
    "warning": "",
    "doc_url": "",
    "category": "AssetsBridge",
}


class AssetBridgeVector(PropertyGroup):
    x: FloatProperty(name="X", default=0.0)
    y: FloatProperty(name="Y", default=0.0)
    z: FloatProperty(name="Z", default=0.0)


class AssetBridgeWorldData(PropertyGroup):
    rotation: bpy.props.PointerProperty(type=AssetBridgeVector, name="Rotation")
    location: bpy.props.PointerProperty(type=AssetBridgeVector, name="Translation")
    scale: bpy.props.PointerProperty(type=AssetBridgeVector, name="Scale")


class AssetBridgeMaterialProperty(PropertyGroup):
    name = bpy.props.StringProperty(name="Name", default="None")
    idx = bpy.props.IntProperty(name="Index", default=0)
    internalPath = bpy.props.StringProperty(name="Internal Path", default="None")


class AssetBridgeObjectProperty(PropertyGroup):
    model = bpy.props.StringProperty(name="Model", default="None")
    objectId = bpy.props.StringProperty(name="Object ID", default="None")
    objectMaterials = bpy.props.CollectionProperty(name="Materials", type=AssetBridgeMaterialProperty)
    internalPath = bpy.props.StringProperty(name="Internal Path", default="None")
    relativeExportPath = bpy.props.StringProperty(name="Relative Export Path", default="None")
    shortName = bpy.props.StringProperty(name="Short Name", default="None")
    exportLocation = bpy.props.StringProperty(name="Export Location", default="None")
    stringType = bpy.props.StringProperty(name="Type", default="None")
    worldData = bpy.props.PointerProperty(type=AssetBridgeWorldData)


class AssetBridgeProperty(PropertyGroup):
    operation = bpy.props.StringProperty(name="Operation", default="Import")
    # objects = bpy.props.PointerProperty(type=bpy.types.ID)
    objects = bpy.props.CollectionProperty(name="Objects", type=bpy.types.Object)


class AssetBridgeFilePaths(PropertyGroup):
    # name: bpy.props.StringProperty()
    path: StringProperty(subtype='FILE_PATH')
    display: BoolProperty()


class AssetsBridgePreferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    filepaths: CollectionProperty(
        name="File paths",
        type=AssetBridgeFilePaths)
    
    static_mesh_export_scale: FloatProperty(
        name="Static Mesh Export Scale",
        description="Scale multiplier for static mesh exports to Unreal Engine",
        default=0.01,
        min=0.0001,
        max=100.0,
        precision=4,
        step=1
    )
    
    skeletal_mesh_export_scale: FloatProperty(
        name="Skeletal Mesh Export Scale",
        description="Scale multiplier for skeletal mesh exports to Unreal Engine",
        default=0.1,
        min=0.0001,
        max=100.0,
        precision=4,
        step=1
    )

    # --- PBR bake settings ---
    bake_resolution: EnumProperty(
        name="Bake Resolution",
        description="Output resolution for baked PBR textures",
        items=RESOLUTION_ITEMS,
        default='2048'
    )
    bake_margin: IntProperty(
        name="Bake Margin (px)",
        description="Edge padding added around UV islands to avoid seams",
        default=8, min=0, max=64
    )
    bake_samples: IntProperty(
        name="Bake Samples",
        description="Cycles samples per bake pass",
        default=16, min=1, max=256
    )
    normal_flip_green: BoolProperty(
        name="Flip Normal Green (DirectX for UE)",
        description="Invert the normal map green channel so it matches Unreal's DirectX convention",
        default=True
    )

    # --- UCX collision settings ---
    warn_missing_ucx: BoolProperty(
        name="Warn if UCX collision missing",
        description="Warn on export when a static mesh has no UCX_ collision mesh",
        default=True
    )
    auto_generate_ucx: BoolProperty(
        name="Auto-generate convex UCX on export",
        description="Automatically create a convex-hull UCX collision when one is missing",
        default=False
    )

    def draw(self, context):
        self.layout.label(text="Browse to any file in the AssetsBridge directory.")
        self.layout.label(text="The addon will use from-unreal.json (import) and from-blender.json (export).")
        for i in self.filepaths:
            if i.display:
                self.layout.prop(i, "path")

        self.layout.separator()
        self.layout.label(text="Export Settings:")
        self.layout.prop(self, "static_mesh_export_scale")
        self.layout.prop(self, "skeletal_mesh_export_scale")

        self.layout.separator()
        self.layout.label(text="PBR Bake Settings:")
        self.layout.prop(self, "bake_resolution")
        self.layout.prop(self, "bake_samples")
        self.layout.prop(self, "bake_margin")
        self.layout.prop(self, "normal_flip_green")

        self.layout.separator()
        self.layout.label(text="Collision Settings:")
        self.layout.prop(self, "warn_missing_ucx")
        self.layout.prop(self, "auto_generate_ucx")


filepath_list = {
    "AssetsBridge": "AssetsBridge.json"
}


class AssetsBridgePanel(bpy.types.Panel):
    bl_label = "Assets Bridge"
    bl_idname = "OBJECT_PT_AssetsBridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AssetsBridge"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Import from Unreal (from-unreal.json)")
        row = layout.row()
        row.operator(operators.BridgedImport.bl_idname, text="Import Objects", icon='IMPORT')
        row = layout.row()
        row.label(text="Export to Unreal (from-blender.json)")

        row = layout.row()
        row.operator(operators.BridgedExport.bl_idname, text="Export Selected", icon='EXPORT')
        
        layout.separator()
        row = layout.row()
        row.label(text="Mesh Tools", icon='MESH_DATA')
        
        row = layout.row()
        row.operator(operators.SplitToNewMesh.bl_idname, text="Split to New Mesh", icon='MOD_EXPLODE')
        
        row = layout.row()
        row.operator(operators.SetUnrealExportPath.bl_idname, text="Set Export Path", icon='FILE_FOLDER')
        
        row = layout.row()
        row.operator(operators.AssignUE5Skeleton.bl_idname, text="Assign UE5 Skeleton", icon='ARMATURE_DATA')

        row = layout.row()
        row.operator(operators.ReorganizeToContainer.bl_idname, text="Reorganize to Container", icon='OUTLINER_COLLECTION')

        layout.separator()
        row = layout.row()
        row.label(text="Texture Tools", icon='TEXTURE')

        row = layout.row()
        row.operator(operators.BridgedBakePBR.bl_idname, text="Bake PBR", icon='RENDER_STILL')

        row = layout.row()
        row.operator(operators.GenerateUCXCollision.bl_idname, text="Generate UCX", icon='MESH_CUBE')

        layout.separator()
        row = layout.row()
        row.label(text="Shape Key Tools", icon='SHAPEKEY_DATA')
        row = layout.row()
        row.operator(operators.TransferShapeKeys.bl_idname, text="Transfer All Shape Keys", icon='SHAPEKEY_DATA')
        row = layout.row()
        row.operator(operators.SelectiveTransferShapeKeys.bl_idname, text="Selective Transfer", icon='CHECKBOX_HLT')
        
        layout.separator()
        row = layout.row()
        row.label(text="Export Settings", icon='PREFERENCES')
        prefs = context.preferences.addons[__name__].preferences
        row = layout.row()
        row.prop(prefs, "static_mesh_export_scale", text="Static Mesh Scale")
        row = layout.row()
        row.prop(prefs, "skeletal_mesh_export_scale", text="Skeletal Mesh Scale")


_class_registers = [
    AssetBridgeVector,
    AssetBridgeWorldData,
    AssetBridgeMaterialProperty,
    AssetBridgeObjectProperty,
    AssetBridgeProperty,
    AssetsBridgePanel,
    AssetBridgeFilePaths,
    AssetsBridgePreferences
]


def register():
    for cls in _class_registers:
        bpy.utils.register_class(cls)
    paths = bpy.context.preferences.addons[__name__].preferences.filepaths
    if not paths:
        for key, value in filepath_list.items():
            item = paths.add()
            item.name = key
            item.path = value
            item.display = True
    bpy.types.Scene.ab_obj_data = bpy.props.PointerProperty(type=AssetBridgeProperty)
    # bpy.context.scene.ab_obj_data.add()
    operators.register()


def unregister():
    for cls in _class_registers:
        bpy.utils.unregister_class(cls)
    operators.unregister()
    del bpy.types.Scene.ab_obj_data


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
    bpy.ops.object.BridgedExport('INVOKE_DEFAULT')
