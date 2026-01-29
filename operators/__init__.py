import bpy
from .imports import BridgedImport
from .exports import BridgedExport
from .shape_keys import TransferShapeKeys, SelectiveTransferShapeKeys
from .mesh_tools import SplitToNewMesh, AssignUE5Skeleton, SetUnrealExportPath
from . import skeleton_retarget

def register():
    bpy.utils.register_class(BridgedImport)
    bpy.utils.register_class(BridgedExport)
    bpy.utils.register_class(TransferShapeKeys)
    bpy.utils.register_class(SelectiveTransferShapeKeys)
    bpy.utils.register_class(SplitToNewMesh)
    bpy.utils.register_class(AssignUE5Skeleton)
    bpy.utils.register_class(SetUnrealExportPath)
    skeleton_retarget.register()


def unregister():
    skeleton_retarget.unregister()
    bpy.utils.unregister_class(SetUnrealExportPath)
    bpy.utils.unregister_class(AssignUE5Skeleton)
    bpy.utils.unregister_class(SplitToNewMesh)
    bpy.utils.unregister_class(SelectiveTransferShapeKeys)
    bpy.utils.unregister_class(TransferShapeKeys)
    bpy.utils.unregister_class(BridgedExport)
    bpy.utils.unregister_class(BridgedImport)


