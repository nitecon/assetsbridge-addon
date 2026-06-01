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
PBR texture baking for AssetsBridge.

Bakes the procedural/Principled materials of a mesh into a single UE-ready texture
set (BaseColor + packed ORM + Normal + Emissive) for import into Unreal Engine as a
Material Instance of the project master material (/Game/Materials/_Core/M_ORM).

Unreal channel conventions baked here:
    * BaseColor : sRGB color
    * ORM (MRAO param) : linear, R=AmbientOcclusion, G=Roughness, B=Metallic
    * Normal : tangent-space, GREEN FLIPPED (DirectX / -Y) which is what UE expects
    * Emissive : sRGB color (emission color * strength)

Baking requires Cycles (EEVEE cannot bake), so the render engine is switched to
CYCLES for the duration of the bake and restored in a finally block.
"""

import os

import bpy
import numpy as np

# ---------------------------------------------------------------------------
# Resolution enum shared by the operator and the addon preferences.
# ---------------------------------------------------------------------------
RESOLUTION_ITEMS = [
    ('128', '128', '128 x 128'),
    ('256', '256', '256 x 256'),
    ('512', '512', '512 x 512'),
    ('1024', '1k', '1024 x 1024'),
    ('2048', '2k', '2048 x 2048'),
    ('4096', '4k', '4096 x 4096'),
    ('8192', '8k', '8192 x 8192'),
]

# Master material this bake feeds into and its texture parameter names.
MASTER_MATERIAL_PATH = "/Game/Materials/_Core/M_ORM"
PARAM_BASECOLOR = "BaseColor"
PARAM_ORM = "ORM"
PARAM_NORMAL = "Normal"
PARAM_EMISSIVE = "Emissive Mask"

_MESH_PREFIXES = ("SM_", "SK_", "SKM_")


# ---------------------------------------------------------------------------
# Path / naming helpers (shared with exports.py so paths stay identical).
# ---------------------------------------------------------------------------
def strip_mesh_prefix(name):
    """Strip a leading SM_/SK_/SKM_ from an asset name (e.g. SM_CreditChip -> CreditChip)."""
    for prefix in _MESH_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def get_asset_short_name(obj):
    """Asset short name as used for the GLB filename."""
    return obj.get("AB_shortName", obj.name)


def _normalize_ue_internal(internal):
    """Normalize an AB_internalPath into a /Game-relative segment with no leading slash/Game."""
    internal = (internal or "").strip("/")
    if internal == "Game":
        return ""
    if internal.startswith("Game/"):
        return internal[len("Game/"):]
    return internal


def get_texture_dir_and_names(obj):
    """
    Resolve where baked textures live on disk and their intended Unreal content path,
    mirroring BridgedExport.get_export_path(): textures live in a 'Textures' subfolder
    next to the GLB.

    Returns: (disk_dir, content_dir, asset_name, filenames_dict)
      filenames_dict maps role -> absolute disk path. Roles: baseColor, orm, normal, emissive.
    """
    from .files import get_bridge_directory

    asset_name = strip_mesh_prefix(get_asset_short_name(obj))

    # Disk directory: prefer the directory of the resolved GLB export location.
    export_location = obj.get("AB_exportLocation", "")
    if export_location:
        disk_dir = os.path.join(os.path.dirname(export_location), "Textures")
    else:
        base = get_bridge_directory()
        if not base:
            # Bridge not configured yet: fall back to an ABSOLUTE writable location
            # (the .blend's folder, else Blender's temp dir) so we never try to create
            # a bare relative 'Textures' under Blender's CWD (e.g. Program Files).
            base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else bpy.app.tempdir
        internal = (obj.get("AB_internalPath", "") or "").lstrip("/")
        disk_dir = os.path.join(base, internal, "Textures")
    disk_dir = os.path.normpath(disk_dir)

    # Unreal content directory mirrors the same internal path.
    ue_internal = _normalize_ue_internal(obj.get("AB_internalPath", ""))
    content_dir = "/Game/" + (ue_internal + "/" if ue_internal else "") + "Textures"

    filenames = {
        "baseColor": os.path.join(disk_dir, "T_%s_D.png" % asset_name),
        "orm": os.path.join(disk_dir, "T_%s_ORM.png" % asset_name),
        "normal": os.path.join(disk_dir, "T_%s_N.png" % asset_name),
        "emissive": os.path.join(disk_dir, "T_%s_E.png" % asset_name),
    }
    return disk_dir, content_dir, asset_name, filenames


def build_textures_manifest_block(obj):
    """
    Build the 'textures' manifest block for from-blender.json from the bake results
    persisted on obj['AB_textures']. Returns {} if no bake exists or files are missing.

    The block tells the Unreal plugin which PNGs to import, where to put them, the
    target master material, and which master-material parameter each texture drives.
    """
    stored = obj.get("AB_textures")
    if not stored:
        return {}
    stored = dict(stored) if hasattr(stored, "keys") else {}
    if not stored:
        return {}

    disk_dir, content_dir, asset_name, filenames = get_texture_dir_and_names(obj)

    roles = {
        "baseColor": {"param": PARAM_BASECOLOR, "colorSpace": "sRGB"},
        "orm": {"param": PARAM_ORM, "colorSpace": "Linear",
                "channels": {"r": "AO", "g": "Roughness", "b": "Metallic"}},
        "normal": {"param": PARAM_NORMAL, "colorSpace": "Linear", "format": "DirectX"},
        "emissive": {"param": PARAM_EMISSIVE, "colorSpace": "sRGB"},
    }

    block = {
        "master": MASTER_MATERIAL_PATH,
        "materialInstance": content_dir.replace("/Textures", "") + "/MI_" + asset_name,
    }
    have_any = False
    for role, meta in roles.items():
        disk_path = stored.get(role) or filenames.get(role)
        if not disk_path or not os.path.isfile(disk_path):
            continue
        have_any = True
        # contentPath is the destination FOLDER for the import (the UE side appends the
        # texture's own name). Must NOT include the texture name, or it nests as
        # .../Textures/T_X/T_X.
        entry = {
            "file": disk_path.replace("\\", "/"),
            "contentPath": content_dir,
        }
        entry.update(meta)
        block[role] = entry

    return block if have_any else {}


# ---------------------------------------------------------------------------
# Low-level baking helpers.
# ---------------------------------------------------------------------------
def _ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _uv_is_degenerate(obj):
    """
    True if the active UV layer is effectively unusable for baking - i.e. a large
    fraction of loops collapse to a single point (procedural meshes are often built
    with all UVs at the origin). Such a layer must be re-unwrapped before baking.
    """
    me = obj.data
    if not me.uv_layers.active:
        return True
    uv = me.uv_layers.active.data
    if len(uv) == 0:
        return True
    sample = min(len(uv), 4000)
    collapsed = sum(1 for i in range(sample) if uv[i].uv.x == 0.0 and uv[i].uv.y == 0.0)
    return (collapsed / sample) > 0.5


def _smart_unwrap(obj, report=None):
    """Smart-UV-Project the whole mesh into a single non-overlapping atlas."""
    _ensure_object_mode()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    if report:
        report({'INFO'}, "Smart-UV-Project unwrapped '%s'" % obj.name)


def ensure_usable_uv(obj, force=False, report=None):
    """Guarantee a bakeable UV layout, unwrapping when forced or when UVs are degenerate."""
    if force or _uv_is_degenerate(obj):
        _smart_unwrap(obj, report=report)


def _new_bake_image(name, res, non_color, alpha=False):
    """Create (or recreate) a target image for a bake pass."""
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, width=res, height=res, alpha=alpha, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    return img


def _attach_target_node(mat, image):
    """Add a temporary Image Texture node to a material and make it the active bake target."""
    nt = mat.node_tree
    node = nt.nodes.new('ShaderNodeTexImage')
    node.name = "AB_BAKE_TARGET"
    node.image = image
    node.select = True
    nt.nodes.active = node
    return node


def _remove_target_nodes(materials):
    for mat in materials:
        if not mat or not mat.use_nodes:
            continue
        for node in [n for n in mat.node_tree.nodes if n.name == "AB_BAKE_TARGET"]:
            mat.node_tree.nodes.remove(node)


def _principled_of(mat):
    if not mat or not mat.use_nodes:
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    return None


def _bake_pass(bake_type, pass_filter=None, margin=8, normal_green='POS_Y'):
    """Run a single bake into the currently active image-texture node of each material."""
    kwargs = dict(type=bake_type, margin=int(margin), use_clear=True)
    if pass_filter is not None:
        kwargs['pass_filter'] = pass_filter
    if bake_type == 'NORMAL':
        kwargs['normal_space'] = 'TANGENT'
        kwargs['normal_r'] = 'POS_X'
        kwargs['normal_g'] = normal_green
        kwargs['normal_b'] = 'POS_Z'
    bpy.ops.object.bake(**kwargs)


class _metallic_as_emission:
    """
    Context manager that temporarily rewires every material so the Principled
    'Metallic' value drives an Emission shader feeding the Material Output, allowing
    metallic to be captured via an EMIT bake (Blender has no native metallic pass).
    Restores the original surface links on exit.
    """

    def __init__(self, materials):
        self.materials = materials
        self._restore = []

    def __enter__(self):
        for mat in self.materials:
            principled = _principled_of(mat)
            if not principled:
                continue
            nt = mat.node_tree
            output = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
            if not output:
                continue
            surf = output.inputs.get('Surface')
            prev_link = surf.links[0].from_socket if (surf and surf.is_linked) else None

            emit = nt.nodes.new('ShaderNodeEmission')
            emit.name = "AB_BAKE_EMIT_METAL"
            metal_in = principled.inputs.get('Metallic')
            if metal_in and metal_in.is_linked:
                nt.links.new(metal_in.links[0].from_socket, emit.inputs['Color'])
            else:
                v = float(metal_in.default_value) if metal_in else 0.0
                emit.inputs['Color'].default_value = (v, v, v, 1.0)
            nt.links.new(emit.outputs['Emission'], surf)
            self._restore.append((mat, output, prev_link, emit))
        return self

    def __exit__(self, *exc):
        for mat, output, prev_link, emit in self._restore:
            nt = mat.node_tree
            if prev_link is not None:
                nt.links.new(prev_link, output.inputs['Surface'])
            if emit.name in nt.nodes:
                nt.nodes.remove(emit)
        self._restore = []
        return False


def _pixels(img):
    arr = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(-1, 4)


def _save_image(img, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.filepath_raw = filepath
    img.file_format = 'PNG'
    img.save()


# ---------------------------------------------------------------------------
# Public bake entry point (usable standalone or from the operator).
# ---------------------------------------------------------------------------
def bake_pbr_textures(obj, out_dir, asset_name, resolution=2048, margin=8,
                      samples=16, flip_normal_green=True, bake_ao=True,
                      bake_emissive=True, re_unwrap=False, report=None):
    """
    Bake the PBR texture set for `obj` into `out_dir`. Returns dict role->filepath.

    Switches the scene to CYCLES for baking and restores prior settings afterwards.
    Auto-unwraps (Smart UV Project) when `re_unwrap` is set or the active UV layer is
    degenerate, so procedurally-built meshes with collapsed UVs bake correctly.
    """
    def _log(msg):
        if report:
            report({'INFO'}, msg)

    res = int(resolution)
    materials = [m for m in obj.data.materials if m and m.use_nodes]
    if not materials:
        raise RuntimeError("Object has no node-based materials to bake.")

    ensure_usable_uv(obj, force=re_unwrap, report=report)

    scene = bpy.context.scene
    prev_engine = scene.render.engine
    prev_samples = getattr(scene.cycles, "samples", None) if hasattr(scene, "cycles") else None
    prev_denoise = getattr(scene.cycles, "use_denoising", None) if hasattr(scene, "cycles") else None

    out_paths = {}
    created_images = []
    base = "AB_%s" % asset_name

    try:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = int(samples)
        scene.cycles.use_denoising = False

        _ensure_object_mode()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # --- BaseColor (sRGB, DIFFUSE color only) ---
        img_bc = _new_bake_image(base + "_D", res, non_color=False, alpha=True)
        created_images.append(img_bc)
        target_nodes = [_attach_target_node(m, img_bc) for m in materials]
        _bake_pass('DIFFUSE', pass_filter={'COLOR'}, margin=margin)
        out_paths['baseColor'] = os.path.join(out_dir, "T_%s_D.png" % asset_name)
        _save_image(img_bc, out_paths['baseColor'])
        _log("Baked BaseColor")

        # --- Data passes into shared images, then packed into ORM ---
        def _rebind(image):
            for node in target_nodes:
                node.image = image

        img_rough = _new_bake_image(base + "_R", res, non_color=True)
        created_images.append(img_rough)
        _rebind(img_rough)
        _bake_pass('ROUGHNESS', margin=margin)
        _log("Baked Roughness")

        if bake_ao:
            img_ao = _new_bake_image(base + "_AO", res, non_color=True)
            created_images.append(img_ao)
            _rebind(img_ao)
            _bake_pass('AO', margin=margin)
            _log("Baked AO")
        else:
            img_ao = None

        img_metal = _new_bake_image(base + "_M", res, non_color=True)
        created_images.append(img_metal)
        _rebind(img_metal)
        with _metallic_as_emission(materials):
            _bake_pass('EMIT', margin=margin)
        _log("Baked Metallic (via emission swap)")

        # Pack ORM: R=AO, G=Roughness, B=Metallic
        rough_px = _pixels(img_rough)
        metal_px = _pixels(img_metal)
        ao_px = _pixels(img_ao) if img_ao is not None else None
        orm = np.ones((rough_px.shape[0], 4), dtype=np.float32)
        orm[:, 0] = ao_px[:, 0] if ao_px is not None else 1.0
        orm[:, 1] = rough_px[:, 0]
        orm[:, 2] = metal_px[:, 0]
        img_orm = _new_bake_image(base + "_ORM", res, non_color=True)
        created_images.append(img_orm)
        img_orm.pixels.foreach_set(orm.reshape(-1))
        out_paths['orm'] = os.path.join(out_dir, "T_%s_ORM.png" % asset_name)
        _save_image(img_orm, out_paths['orm'])
        _log("Packed ORM (R=AO, G=Rough, B=Metal)")

        # --- Normal (tangent OpenGL, then flip green for UE/DirectX) ---
        img_n = _new_bake_image(base + "_N", res, non_color=True)
        created_images.append(img_n)
        _rebind(img_n)
        _bake_pass('NORMAL', margin=margin)
        if flip_normal_green:
            npx = _pixels(img_n)
            npx[:, 1] = 1.0 - npx[:, 1]
            img_n.pixels.foreach_set(npx.reshape(-1))
        out_paths['normal'] = os.path.join(out_dir, "T_%s_N.png" % asset_name)
        _save_image(img_n, out_paths['normal'])
        _log("Baked Normal (%s)" % ("DirectX" if flip_normal_green else "OpenGL"))

        # --- Emissive (sRGB, EMIT) ---
        if bake_emissive:
            img_e = _new_bake_image(base + "_E", res, non_color=False)
            created_images.append(img_e)
            _rebind(img_e)
            _bake_pass('EMIT', margin=margin)
            out_paths['emissive'] = os.path.join(out_dir, "T_%s_E.png" % asset_name)
            _save_image(img_e, out_paths['emissive'])
            _log("Baked Emissive")

        return out_paths

    finally:
        _remove_target_nodes(materials)
        for img in created_images:
            # Keep nothing in-memory; saved copies live on disk. Remove temp datablocks.
            if img.name in bpy.data.images:
                try:
                    bpy.data.images.remove(bpy.data.images[img.name])
                except RuntimeError:
                    pass
        scene.render.engine = prev_engine
        if prev_samples is not None:
            scene.cycles.samples = prev_samples
        if prev_denoise is not None:
            scene.cycles.use_denoising = prev_denoise


def consolidate_to_single_material(obj, asset_name, tex_paths):
    """
    Replace the mesh's material slots with one M_<asset> material wired from the baked
    textures, so the glTF round-trip carries a single slot matching the M_ORM instance
    workflow. Original slot names are stashed on obj['AB_preBakeMaterials'].
    """
    old_names = [m.name if m else "" for m in obj.data.materials]
    obj["AB_preBakeMaterials"] = old_names

    mat = bpy.data.materials.new("M_%s" % asset_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    output = nt.nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (260, 0)
    nt.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    def _img_node(path, non_color, x, y):
        node = nt.nodes.new('ShaderNodeTexImage')
        node.location = (x, y)
        if path and os.path.isfile(path):
            img = bpy.data.images.load(path, check_existing=True)
            if non_color:
                img.colorspace_settings.name = 'Non-Color'
            node.image = img
        return node

    if tex_paths.get('baseColor'):
        bc = _img_node(tex_paths['baseColor'], False, -400, 300)
        nt.links.new(bc.outputs['Color'], bsdf.inputs['Base Color'])

    if tex_paths.get('orm'):
        orm = _img_node(tex_paths['orm'], True, -400, 0)
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        sep.location = (-120, 0)
        nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
        nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
        nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])

    if tex_paths.get('normal'):
        nrm = _img_node(tex_paths['normal'], True, -400, -300)
        nmap = nt.nodes.new('ShaderNodeNormalMap')
        nmap.location = (-120, -300)
        nt.links.new(nrm.outputs['Color'], nmap.inputs['Color'])
        nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])

    if tex_paths.get('emissive'):
        em = _img_node(tex_paths['emissive'], False, -400, -600)
        if 'Emission Color' in bsdf.inputs:
            nt.links.new(em.outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0

    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0
    return mat


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class BridgedBakePBR(bpy.types.Operator):
    """Bake the active mesh's materials into a UE-ready PBR texture set (BaseColor/ORM/Normal/Emissive)"""
    bl_idname = "assetsbridge.bake_pbr"
    bl_label = "Bake PBR Texture Set"
    bl_options = {'REGISTER', 'UNDO'}

    resolution: bpy.props.EnumProperty(name="Resolution", items=RESOLUTION_ITEMS, default='2048')
    margin: bpy.props.IntProperty(name="Margin (px)", default=8, min=0, max=64)
    samples: bpy.props.IntProperty(name="Samples", default=16, min=1, max=256)
    flip_normal_green: bpy.props.BoolProperty(
        name="Flip Normal Green (DirectX for UE)", default=True)
    bake_ao: bpy.props.BoolProperty(name="Bake AO", default=True)
    bake_emissive: bpy.props.BoolProperty(name="Bake Emissive", default=True)
    re_unwrap: bpy.props.BoolProperty(
        name="Re-unwrap (Smart UV)",
        description="Force a Smart UV Project unwrap before baking (auto-applied when UVs are degenerate)",
        default=False)
    consolidate_materials: bpy.props.BoolProperty(
        name="Consolidate to single material", default=True)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and len(obj.data.materials) > 0

    def invoke(self, context, event):
        try:
            prefs = context.preferences.addons["AssetsBridge"].preferences
            self.resolution = prefs.bake_resolution
            self.margin = prefs.bake_margin
            self.samples = prefs.bake_samples
            self.flip_normal_green = prefs.normal_flip_green
        except (KeyError, AttributeError):
            pass
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "resolution")
        layout.prop(self, "samples")
        layout.prop(self, "margin")
        layout.prop(self, "flip_normal_green")
        layout.prop(self, "bake_ao")
        layout.prop(self, "bake_emissive")
        layout.prop(self, "re_unwrap")
        layout.prop(self, "consolidate_materials")

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object to bake.")
            return {'CANCELLED'}

        disk_dir, content_dir, asset_name, _names = get_texture_dir_and_names(obj)
        try:
            tex_paths = bake_pbr_textures(
                obj, disk_dir, asset_name,
                resolution=self.resolution, margin=self.margin, samples=self.samples,
                flip_normal_green=self.flip_normal_green, bake_ao=self.bake_ao,
                bake_emissive=self.bake_emissive, re_unwrap=self.re_unwrap,
                report=self.report)
        except Exception as exc:  # noqa: BLE001 - surface bake failures to the user
            self.report({'ERROR'}, "Bake failed: %s" % exc)
            return {'CANCELLED'}

        # Persist results for the export manifest + reorganize tool.
        obj["AB_textures"] = {k: v.replace("\\", "/") for k, v in tex_paths.items()}

        if self.consolidate_materials:
            consolidate_to_single_material(obj, asset_name, tex_paths)

        self.report({'INFO'}, "Baked PBR set for '%s' to %s" % (asset_name, disk_dir))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(BridgedBakePBR)


def unregister():
    bpy.utils.unregister_class(BridgedBakePBR)
