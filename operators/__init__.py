import bpy
from .imports import BridgedImport
from .exports import BridgedExport
# Imported for panel bl_idname references; registration is handled by shape_keys.register()
# (which also registers the ShapeKeySelectionItem PropertyGroup and the select/deselect ops
# in the correct order).
from .shape_keys import TransferShapeKeys, SelectiveTransferShapeKeys
from .mesh_tools import SplitToNewMesh, AssignUE5Skeleton, SetUnrealExportPath, ReorganizeToContainer
from .bake import BridgedBakePBR
from .collision import GenerateUCXCollision
from . import shape_keys
from . import skeleton_retarget

def register():
    bpy.utils.register_class(BridgedImport)
    bpy.utils.register_class(BridgedExport)
    shape_keys.register()
    bpy.utils.register_class(SplitToNewMesh)
    bpy.utils.register_class(AssignUE5Skeleton)
    bpy.utils.register_class(SetUnrealExportPath)
    bpy.utils.register_class(ReorganizeToContainer)
    bpy.utils.register_class(BridgedBakePBR)
    bpy.utils.register_class(GenerateUCXCollision)
    skeleton_retarget.register()


def unregister():
    skeleton_retarget.unregister()
    bpy.utils.unregister_class(GenerateUCXCollision)
    bpy.utils.unregister_class(BridgedBakePBR)
    bpy.utils.unregister_class(ReorganizeToContainer)
    bpy.utils.unregister_class(SetUnrealExportPath)
    bpy.utils.unregister_class(AssignUE5Skeleton)
    shape_keys.unregister()
    bpy.utils.unregister_class(BridgedExport)
    bpy.utils.unregister_class(BridgedImport)


