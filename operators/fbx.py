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
    import_options = {}
    if type_string == "StaticMesh":
        import_options = {
            "use_custom_normals": True,
            "axis_forward": "X",  # set forward axis to "-Z"
            "axis_up": "Z",  # set up axis to "Y
        }
    elif type_string == "SkeletalMesh":
        import_options = {
            "use_custom_normals": True,
            "use_custom_props": True,
            "use_image_search": True,
            "use_anim": True,
            "use_anim_action_all": True,
            "use_default_take": True,
            "use_anim_optimize": True,
            "anim_optimize_precision": 6.0,
            "path_mode": "AUTO",
            "axis_forward": "X",  # set forward axis to "-Z"
            "axis_up": "Z",  # set up axis to "Y
        }

    return import_options


def get_general_import_opts(type_string):
    import_options = {}
    if type_string == "StaticMesh":
        import_options = {
            "use_custom_normals": True,
            "axis_forward": "-X",  # set forward axis to "-Z"
            "axis_up": "Z",  # set up axis to "Y
        }
    elif type_string == "SkeletalMesh":
        import_options = {
            "use_custom_normals": True,
            "use_custom_props": True,
            "use_image_search": True,
            "use_anim": True,
            "axis_forward": "-X",  # set forward axis to "-Z"
            "axis_up": "Z",  # set up axis to "Y
        }

    return import_options


# Export Options:
# filepath: str # File Path, Filepath used for exporting the file
# check_existing: bool # Check Existing, Check and warn on overwriting existing files
# use_selection: bool # Selected Objects, Export selected and visible objects only
# use_visible: bool # Visible Objects, Export visible objects only
# use_active_collection: bool # Active Collection, Export only objects from the active collection (and its children)
# global_scale: float # Scale, Scale all data (Some importers do not support scaled armatures!)
# apply_unit_scale: bool # Apply Unit, Take into account current Blender units settings (if unset, raw Blender Units values are used as-is)
# apply_scale_options: str # Apply Scalings, How to apply custom and units scalings in generated FBX file
# use_space_transform: bool # Use Space Transform, Apply global space transform to the object rotations
# bake_space_transform: bool # Apply Transform, Bake space transform into object data, avoids getting unwanted rotations to objects
# object_types: set # Object Types, Which kind of object to export
# use_mesh_modifiers: bool # Use Mesh Modifiers, Apply or ignore mesh modifiers
# use_mesh_modifiers_render: bool # Use Modifiers Render Setting, Use render settings when applying modifiers to mesh objects
# mesh_smooth_type: str # Smoothing, Export smoothing information
# colors_type: str # Vertex Colors, Export vertex color attributes
# prioritize_active_color: bool # Prioritize Active Color, Ensure active color is exported first
# use_subsurf: bool # Export Subdivision Surface, Export last subdivision modifier as FBX subdivision
# use_mesh_edges: bool # Loose Edges, Export loose edges (as two-vertices polygons)
# use_tspace: bool # Tangent Space, Add binormal and tangent vectors
# use_triangles: bool # Triangulate Faces, Convert all faces to triangles
# use_custom_props: bool # Custom Properties, Export custom properties
# add_leaf_bones: bool # Add Leaf Bones, Append a final bone to end of each chain to specify last bone length
# use_armature_deform_only: bool # Only Deform Bones, Only write deforming bones
# armature_nodetype: str # Armature FBXNode Type, FBX type of node used to represent Blender's armatures
# bake_anim: bool # Baked Animation, Export baked keyframe animation
# bake_anim_use_all_bones: bool # Key All Bones, Force at least one key of animation for all bones
# bake_anim_use_nla_strips: bool # NLA Strips, Export each non-muted NLA strip as a separated FBX's AnimStack
# bake_anim_use_all_actions: bool # All Actions, Export each action as a separated FBX's AnimStack
# bake_anim_force_startend_keying: bool # Force Start/End Keying, Always add a keyframe at start and end of actions
# bake_anim_step: float # Sampling Rate, How often to evaluate animated values (in frames)
# bake_anim_simplify_factor: float # Simplify, How much to simplify baked values
# path_mode: str # Path Mode, Method used to reference paths
# embed_textures: bool # Embed Textures, Embed textures in FBX binary file
# batch_mode: str # Batch Mode, Method for batch exporting
# use_batch_own_dir: bool # Batch Own Dir, Create a dir for each exported file
# use_metadata: bool # Use Metadata, Include Blender metadata in the file
# axis_forward: str # Forward, Set the forward direction in the exported file
# axis_up: str # Up, Set the up direction in the exported file

def get_unreal_export_opts():
    export_options = {
        "use_selection": True,  # only export selected objects
        "use_mesh_modifiers": True,  # apply mesh modifiers
        "use_metadata": True,  # don't include metadata
        "mesh_smooth_type": "FACE",  # don't smooth meshes
        "use_subsurf": False,  # don't apply subsurface modifiers
        "use_mesh_edges": False,  # don't include mesh edges
        "use_tspace": True,  # include texture space data
        "use_armature_deform_only": False,  # include full armature deformations
        "add_leaf_bones": False,  # add leaf bones for armatures
        "global_scale": 1.0,  # don't change the global scale
        "path_mode": "AUTO",  # set path mode to "AUTO" to automatically determine the best path mode
        "bake_space_transform": True,  # bake space transform matrices
        "use_custom_props": True,  # include custom properties
        "axis_forward": "Y",  # set forward axis to "-Z"
        "axis_up": "Z",  # set up axis to "Y
    }
    return export_options


def get_unreal_skeletal_export_opts():
    export_opts = {
        "use_selection": True,  # only export selected objects
        "use_mesh_modifiers": True,  # apply mesh modifiers
        "use_mesh_modifiers_render": True,  # use render settings for modifiers
        "use_metadata": True,  # include metadata
        "mesh_smooth_type": "FACE",  # face smoothing
        "use_subsurf": False,  # don't apply subsurface modifiers
        "use_mesh_edges": False,  # don't include mesh edges
        "use_tspace": True,  # include texture space data
        "use_armature_deform_only": False,  # export full skeleton hierarchy
        "add_leaf_bones": False,  # don't add leaf bones for armatures
        "global_scale": 1.0,  # don't change the global scale
        "path_mode": "AUTO",  # auto path mode
        "bake_space_transform": False,  # NEVER bake transforms for armatures
        "use_custom_props": True,  # include custom properties
        "axis_forward": "-Y",  # forward axis -Y for Unreal
        "axis_up": "Z",  # up axis Z
        "primary_bone_axis": "Y",  # primary bone axis Y (Blender's bone direction)
        "secondary_bone_axis": "X",  # secondary bone axis X
        "armature_nodetype": "NULL",  # don't add armature node wrapper
        "bake_anim": True,  # export baked animation (required for shape keys)
        "bake_anim_use_all_bones": True,  # key all bones
        "bake_anim_use_nla_strips": False,  # don't split NLA strips
        "bake_anim_use_all_actions": False,  # don't export all actions separately
        "bake_anim_force_startend_keying": True,  # ensure start/end keyframes
        "bake_anim_step": 1.0,  # sample every frame
        "bake_anim_simplify_factor": 0.0,  # no simplification for accuracy
    }
    return export_opts
