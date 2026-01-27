import bpy
from .imports import BridgedImport
from .exports import BridgedExport
from .shape_keys import TransferShapeKeys

def register():
    bpy.utils.register_class(BridgedImport)
    bpy.utils.register_class(BridgedExport)
    bpy.utils.register_class(TransferShapeKeys)


def unregister():
    bpy.utils.unregister_class(BridgedImport)
    bpy.utils.unregister_class(BridgedExport)
    bpy.utils.unregister_class(TransferShapeKeys)


