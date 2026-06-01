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
"""
UCX collision helpers for AssetsBridge.

Unreal imports a collision mesh named UCX_<MeshName>[_##] alongside a static mesh.
These helpers detect whether such a collision exists and can generate a convex-hull
UCX, and provide a pre-export check that warns (or auto-generates) when it is missing.
"""

import re

import bpy


def _ucx_base_name(mesh_obj):
    """The mesh name Unreal will match UCX against (the GLB short name, prefix kept)."""
    return mesh_obj.get("AB_shortName", mesh_obj.name)


def has_ucx_collision(mesh_obj):
    """True if a UCX_<name> or UCX_<name>_## collision mesh exists in the scene."""
    base = _ucx_base_name(mesh_obj)
    pattern = re.compile(r"^UCX_%s(_\d+)?$" % re.escape(base))
    return any(o.type == 'MESH' and pattern.match(o.name) for o in bpy.data.objects)


def _style_ucx(ucx_obj):
    """Apply the same UCX display styling the importer uses (wireframe blue, no render)."""
    ucx_obj.display.show_shadows = False
    ucx_obj.color = (0, 0.2, 1, 1)
    ucx_obj.display_type = 'WIRE'
    ucx_obj.hide_render = True


def create_convex_ucx(mesh_obj):
    """
    Create a convex-hull UCX collision mesh named UCX_<name>_01 from `mesh_obj`,
    linked into the same collections, and return it.
    """
    base = _ucx_base_name(mesh_obj)
    # Pick the next free UCX index.
    idx = 1
    while bpy.data.objects.get("UCX_%s_%02d" % (base, idx)):
        idx += 1
    ucx_name = "UCX_%s_%02d" % (base, idx)

    new_mesh = mesh_obj.data.copy()
    ucx = bpy.data.objects.new(ucx_name, new_mesh)
    for coll in mesh_obj.users_collection:
        coll.objects.link(ucx)
    ucx.matrix_world = mesh_obj.matrix_world.copy()

    # Reduce to a convex hull.
    prev_active = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    ucx.select_set(True)
    bpy.context.view_layer.objects.active = ucx
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.convex_hull()
    bpy.ops.object.mode_set(mode='OBJECT')
    ucx.data.materials.clear()

    _style_ucx(ucx)
    if prev_active:
        bpy.context.view_layer.objects.active = prev_active
    return ucx


def _iter_static_mesh_roots(export_roots):
    for root in export_roots:
        if root.type != 'MESH':
            continue
        if root.get("AB_stringType", "StaticMesh") == "StaticMesh":
            yield root


def check_ucx_before_export(operator, context, export_roots):
    """
    For each static-mesh export root lacking a UCX collision, either auto-generate one
    (when the preference is set) or warn the user. Degrades to operator.report() when no
    interactive popup is available (BridgedExport.invoke calls execute directly).
    """
    try:
        prefs = context.preferences.addons["AssetsBridge"].preferences
        warn = prefs.warn_missing_ucx
        auto = prefs.auto_generate_ucx
    except (KeyError, AttributeError):
        warn, auto = True, False

    if not warn and not auto:
        return

    missing = [r for r in _iter_static_mesh_roots(export_roots) if not has_ucx_collision(r)]
    if not missing:
        return

    if auto:
        for mesh_obj in missing:
            ucx = create_convex_ucx(mesh_obj)
            operator.report({'INFO'}, "Generated collision '%s'" % ucx.name)
        return

    names = ", ".join(_ucx_base_name(m) for m in missing)
    msg = "No UCX_ collision for: %s. Add one (Generate UCX) or enable auto-generate." % names
    operator.report({'WARNING'}, msg)
    try:
        def _draw(self, _ctx):
            self.layout.label(text="Missing UCX collision mesh(es):")
            for m in missing:
                self.layout.label(text="  - %s" % _ucx_base_name(m))
            self.layout.label(text="Unreal will use auto-generated collision unless a UCX_ mesh exists.")
        context.window_manager.popup_menu(_draw, title="AssetsBridge: Collision Missing", icon='ERROR')
    except Exception:  # noqa: BLE001 - popup unavailable in non-interactive context
        pass


class GenerateUCXCollision(bpy.types.Operator):
    """Generate a convex-hull UCX collision mesh for the active static mesh"""
    bl_idname = "assetsbridge.generate_ucx"
    bl_label = "Generate UCX Collision"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        if has_ucx_collision(obj):
            self.report({'INFO'}, "UCX collision already exists for '%s'." % _ucx_base_name(obj))
            return {'CANCELLED'}
        ucx = create_convex_ucx(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        self.report({'INFO'}, "Generated collision '%s'." % ucx.name)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(GenerateUCXCollision)


def unregister():
    bpy.utils.unregister_class(GenerateUCXCollision)
