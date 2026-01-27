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

def get_unreal_import_opts(type_string):
    """
    Returns glTF import options configured for assets coming from Unreal Engine.
    """
    import_options = {}
    if type_string == "StaticMesh":
        import_options = {
            "import_pack_images": True,
            "merge_vertices": False,
            "import_shading": "NORMALS",
            "bone_heuristic": "TEMPERANCE",
            "guess_original_bind_pose": True,
        }
    elif type_string == "SkeletalMesh":
        import_options = {
            "import_pack_images": True,
            "merge_vertices": False,
            "import_shading": "NORMALS",
            "bone_heuristic": "TEMPERANCE",
            "guess_original_bind_pose": True,
        }

    return import_options


def get_general_import_opts(type_string):
    """
    Returns general glTF import options.
    """
    import_options = {}
    if type_string == "StaticMesh":
        import_options = {
            "import_pack_images": True,
            "merge_vertices": False,
            "import_shading": "NORMALS",
            "bone_heuristic": "TEMPERANCE",
            "guess_original_bind_pose": True,
        }
    elif type_string == "SkeletalMesh":
        import_options = {
            "import_pack_images": True,
            "merge_vertices": False,
            "import_shading": "NORMALS",
            "bone_heuristic": "TEMPERANCE",
            "guess_original_bind_pose": True,
        }

    return import_options


# glTF Export Options Reference:
# filepath: str - File Path, Filepath used for exporting the file
# check_existing: bool - Check Existing, Check and warn on overwriting existing files
# export_format: str - Format, Output format ('GLB', 'GLTF_SEPARATE', 'GLTF_EMBEDDED')
# use_selection: bool - Selected Objects, Export selected objects only
# use_visible: bool - Visible Objects, Export visible objects only
# use_active_collection: bool - Active Collection, Export objects from active collection only
# use_active_scene: bool - Active Scene, Export active scene only
# export_extras: bool - Custom Properties, Export custom properties as glTF extras
# export_cameras: bool - Export Cameras
# export_lights: bool - Export Lights
# use_renderable: bool - Renderable, Export renderable objects only
# export_apply: bool - Apply Modifiers, Apply modifiers (excluding armature) to mesh objects
# export_texcoords: bool - UVs, Export UVs (texture coordinates) with meshes
# export_normals: bool - Normals, Export vertex normals with meshes
# export_tangents: bool - Tangents, Export vertex tangents with meshes
# export_materials: str - Materials, Export materials ('EXPORT', 'PLACEHOLDER', 'NONE')
# export_colors: bool - Vertex Colors, Export vertex colors with meshes
# export_attributes: bool - Attributes, Export Attributes (when defined in mesh)
# use_mesh_edges: bool - Loose Edges, Export loose edges as lines
# use_mesh_vertices: bool - Loose Points, Export loose points as glTF points
# export_yup: bool - +Y Up, Export using glTF convention, +Y up
# export_skins: bool - Skinning, Export skinning (armature) data
# export_all_influences: bool - Include All Bone Influences
# export_morph: bool - Shape Keys, Export shape keys (morph targets)
# export_morph_normal: bool - Shape Key Normals, Export vertex normals with shape keys
# export_morph_tangent: bool - Shape Key Tangents, Export vertex tangents with shape keys
# export_animations: bool - Animations, Export animations
# export_current_frame: bool - Current Frame, Export only the current animation frame
# export_frame_range: bool - Limit to Playback Range
# export_frame_step: int - Sampling Rate, Animation sampling rate
# export_nla_strips: bool - Group by NLA Track
# export_def_bones: bool - Export Deformation Bones Only
# export_optimize_animation_size: bool - Optimize Animation Size
# export_reset_pose_bones: bool - Reset Pose Bones, Reset pose bones before export

def get_unreal_export_opts():
    """
    Returns glTF export options for static meshes destined for Unreal Engine.
    Uses GLB format for single-file convenience.
    Note: Blender 4.0+ changed vertex color handling - colors are now exported as attributes.
    """
    export_options = {
        "export_format": "GLB",
        "use_selection": True,
        "export_apply": True,
        "export_texcoords": True,
        "export_normals": True,
        "export_tangents": True,
        "export_materials": "EXPORT",
        "export_extras": True,
        "export_yup": True,
        "export_cameras": False,
        "export_lights": False,
        "use_mesh_edges": False,
        "use_mesh_vertices": False,
        "export_skins": False,
        "export_morph": False,
        "export_animations": False,
    }
    return export_options


def get_unreal_skeletal_export_opts():
    """
    Returns glTF export options for skeletal meshes destined for Unreal Engine.
    Includes skinning, shape keys, and animation export settings.
    Note: Blender 4.0+ changed vertex color handling - colors are now exported as attributes.
    """
    export_opts = {
        "export_format": "GLB",
        "use_selection": True,
        "export_apply": True,
        "export_texcoords": True,
        "export_normals": True,
        "export_tangents": True,
        "export_materials": "EXPORT",
        "export_extras": True,
        "export_yup": True,
        "export_cameras": False,
        "export_lights": False,
        "use_mesh_edges": False,
        "use_mesh_vertices": False,
        "export_skins": True,
        "export_all_influences": True,
        "export_morph": True,
        "export_morph_normal": True,
        "export_morph_tangent": False,
        "export_animations": False,
        "export_def_bones": False,
        "export_reset_pose_bones": True,
    }
    return export_opts
