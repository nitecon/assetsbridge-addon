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
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup, Operator


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_side_from_bone_name(name):
    """Determine if bone is left, right, or center based on naming conventions."""
    name_lower = name.lower()
    
    # Common left patterns
    left_patterns = ['_l', '.l', '-l', '_left', '.left', '-left']
    # Check suffix patterns
    for pattern in left_patterns:
        if name_lower.endswith(pattern):
            return 'LEFT'
    # Check prefix patterns
    if name_lower.startswith('l_') or name_lower.startswith('l.') or name_lower.startswith('l-'):
        return 'LEFT'
    if name_lower.startswith('left'):
        return 'LEFT'
    
    # Common right patterns
    right_patterns = ['_r', '.r', '-r', '_right', '.right', '-right']
    for pattern in right_patterns:
        if name_lower.endswith(pattern):
            return 'RIGHT'
    if name_lower.startswith('r_') or name_lower.startswith('r.') or name_lower.startswith('r-'):
        return 'RIGHT'
    if name_lower.startswith('right'):
        return 'RIGHT'
    
    return 'CENTER'


def get_armature_from_mesh(mesh_obj):
    """Get the armature associated with a mesh object."""
    if mesh_obj is None or mesh_obj.type != 'MESH':
        return None
    
    # Check armature modifier
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            return mod.object
    
    # Check parent
    if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
        return mesh_obj.parent
    
    return None


def get_mesh_from_context(context):
    """Get the mesh object from context, handling both object and weight paint modes."""
    obj = context.active_object
    
    if obj is None:
        return None
    
    if obj.type == 'MESH':
        return obj
    
    # In weight paint mode, we might have the armature selected
    if obj.type == 'ARMATURE':
        # Look for meshes using this armature
        for child in obj.children:
            if child.type == 'MESH':
                return child
    
    return None


def get_mirror_bone_name(bone_name):
    """Get the mirrored bone name (left <-> right)."""
    name_lower = bone_name.lower()
    
    # Suffix patterns
    replacements = [
        ('_l', '_r'), ('_r', '_l'),
        ('.l', '.r'), ('.r', '.l'),
        ('-l', '-r'), ('-r', '-l'),
        ('_left', '_right'), ('_right', '_left'),
        ('.left', '.right'), ('.right', '.left'),
        ('-left', '-right'), ('-right', '-left'),
    ]
    
    for old, new in replacements:
        if name_lower.endswith(old):
            return bone_name[:-len(old)] + (new.upper() if bone_name[-1].isupper() else new)
    
    # Prefix patterns
    prefix_replacements = [
        ('l_', 'r_'), ('r_', 'l_'),
        ('l.', 'r.'), ('r.', 'l.'),
        ('l-', 'r-'), ('r-', 'l-'),
        ('left_', 'right_'), ('right_', 'left_'),
        ('left.', 'right.'), ('right.', 'left.'),
        ('left-', 'right-'), ('right-', 'left-'),
    ]
    
    for old, new in prefix_replacements:
        if name_lower.startswith(old):
            return (new.upper() if bone_name[0].isupper() else new) + bone_name[len(old):]
    
    return None


def categorize_bones(armature):
    """Categorize all bones in an armature into left, center, right lists."""
    if armature is None or armature.type != 'ARMATURE':
        return [], [], []
    
    left_bones = []
    center_bones = []
    right_bones = []
    
    for bone in armature.data.bones:
        side = get_side_from_bone_name(bone.name)
        if side == 'LEFT':
            left_bones.append(bone.name)
        elif side == 'RIGHT':
            right_bones.append(bone.name)
        else:
            center_bones.append(bone.name)
    
    # Sort alphabetically for consistent ordering
    left_bones.sort()
    center_bones.sort()
    right_bones.sort()
    
    return left_bones, center_bones, right_bones


# =============================================================================
# PROPERTY GROUPS
# =============================================================================

class SkinningBoneItem(PropertyGroup):
    """Single bone entry for the skinning panel."""
    name: StringProperty(name="Bone Name", default="")
    side: EnumProperty(
        name="Side",
        items=[
            ('LEFT', "Left", "Left side bone"),
            ('CENTER', "Center", "Center bone"),
            ('RIGHT', "Right", "Right side bone"),
        ],
        default='CENTER'
    )


class SkinningSettings(PropertyGroup):
    """Settings for the skinning panel."""
    target_mesh: PointerProperty(
        name="Target Mesh",
        description="The mesh to paint weights on",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    show_all_bones: BoolProperty(
        name="Show All Bones",
        description="Show all bones including twist, roll, and helper bones",
        default=False
    )
    filter_text: StringProperty(
        name="Filter",
        description="Filter bones by name",
        default=""
    )
    # Cache for categorized bones
    left_bones: CollectionProperty(type=SkinningBoneItem)
    center_bones: CollectionProperty(type=SkinningBoneItem)
    right_bones: CollectionProperty(type=SkinningBoneItem)


# =============================================================================
# OPERATORS
# =============================================================================

class ASSETSBRIDGE_OT_SelectBoneForPaint(Operator):
    """Select a bone for weight painting - enters weight paint mode if needed"""
    bl_idname = "assetsbridge.select_bone_for_paint"
    bl_label = "Select Bone for Weight Paint"
    bl_options = {'REGISTER', 'UNDO'}

    bone_name: StringProperty(
        name="Bone Name",
        description="Name of the bone to select for weight painting",
        default=""
    )

    @classmethod
    def poll(cls, context):
        mesh_obj = get_mesh_from_context(context)
        if mesh_obj is None:
            return False
        armature = get_armature_from_mesh(mesh_obj)
        return armature is not None

    def execute(self, context):
        mesh_obj = get_mesh_from_context(context)
        armature = get_armature_from_mesh(mesh_obj)
        
        if mesh_obj is None or armature is None:
            self.report({'ERROR'}, "No mesh with armature found")
            return {'CANCELLED'}
        
        if self.bone_name not in armature.data.bones:
            self.report({'ERROR'}, f"Bone '{self.bone_name}' not found in armature")
            return {'CANCELLED'}
        
        # Check if we need to enter weight paint mode
        current_mode = context.mode
        
        if current_mode != 'PAINT_WEIGHT':
            # Enter weight paint mode
            # First, make sure we're in object mode
            if current_mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # Select the mesh and make it active
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            context.view_layer.objects.active = mesh_obj
            
            # Also select the armature (needed for bone selection in weight paint)
            armature.select_set(True)
            
            # Enter weight paint mode
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        
        # Now select the bone in the armature
        # We need to set the armature to pose mode bone selection
        armature.data.bones.active = armature.data.bones[self.bone_name]
        
        # Also set pose bone as active if in pose mode context
        if armature.pose:
            for pb in armature.pose.bones:
                pb.bone.select = (pb.name == self.bone_name)
        
        # Ensure the vertex group exists for this bone
        if self.bone_name not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=self.bone_name)
        
        # Set active vertex group
        vg_index = mesh_obj.vertex_groups[self.bone_name].index
        mesh_obj.vertex_groups.active_index = vg_index
        
        self.report({'INFO'}, f"Selected bone: {self.bone_name}")
        return {'FINISHED'}


class ASSETSBRIDGE_OT_RefreshSkinningBones(Operator):
    """Refresh the list of bones from the active mesh's armature"""
    bl_idname = "assetsbridge.refresh_skinning_bones"
    bl_label = "Refresh Bones"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        mesh_obj = get_mesh_from_context(context)
        if mesh_obj is None:
            return False
        return get_armature_from_mesh(mesh_obj) is not None

    def execute(self, context):
        settings = context.scene.ab_skinning
        mesh_obj = get_mesh_from_context(context)
        armature = get_armature_from_mesh(mesh_obj)
        
        if armature is None:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
        
        # Clear existing bone lists
        settings.left_bones.clear()
        settings.center_bones.clear()
        settings.right_bones.clear()
        
        # Categorize and populate
        left, center, right = categorize_bones(armature)
        
        for bone_name in left:
            item = settings.left_bones.add()
            item.name = bone_name
            item.side = 'LEFT'
        
        for bone_name in center:
            item = settings.center_bones.add()
            item.name = bone_name
            item.side = 'CENTER'
        
        for bone_name in right:
            item = settings.right_bones.add()
            item.name = bone_name
            item.side = 'RIGHT'
        
        self.report({'INFO'}, f"Found {len(left)} left, {len(center)} center, {len(right)} right bones")
        return {'FINISHED'}


class ASSETSBRIDGE_OT_CopyWeightsAcross(Operator):
    """Copy vertex weights from one side to the other (mirror weights)"""
    bl_idname = "assetsbridge.copy_weights_across"
    bl_label = "Copy Weights Across"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        items=[
            ('LEFT_TO_RIGHT', "Left → Right", "Copy weights from left side bones to right side"),
            ('RIGHT_TO_LEFT', "Right → Left", "Copy weights from right side bones to left side"),
        ],
        default='LEFT_TO_RIGHT'
    )

    @classmethod
    def poll(cls, context):
        mesh_obj = get_mesh_from_context(context)
        return mesh_obj is not None

    def execute(self, context):
        mesh_obj = get_mesh_from_context(context)
        
        if mesh_obj is None:
            self.report({'ERROR'}, "No mesh selected")
            return {'CANCELLED'}
        
        # Store current mode
        original_mode = context.mode
        
        # Need to be in object mode for weight operations
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Select only the mesh
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        
        # Use Blender's built-in mirror weights operator
        try:
            bpy.ops.object.vertex_group_mirror(
                mirror_weights=True,
                flip_group_names=True,
                all_groups=True,
                use_topology=False
            )
            self.report({'INFO'}, "Weights mirrored successfully")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to mirror weights: {str(e)}")
            return {'CANCELLED'}
        
        # Restore mode if we were in weight paint
        if original_mode == 'PAINT_WEIGHT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "direction")
        
        box = layout.box()
        box.label(text="This will mirror vertex weights", icon='INFO')
        box.label(text="using Blender's built-in mirror.")


class ASSETSBRIDGE_OT_NormalizeAllWeights(Operator):
    """Normalize all vertex weights on the mesh"""
    bl_idname = "assetsbridge.normalize_all_weights"
    bl_label = "Normalize All Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        mesh_obj = get_mesh_from_context(context)
        return mesh_obj is not None

    def execute(self, context):
        mesh_obj = get_mesh_from_context(context)
        
        if mesh_obj is None:
            self.report({'ERROR'}, "No mesh selected")
            return {'CANCELLED'}
        
        # Store current mode
        original_mode = context.mode
        
        # Need to be in object mode
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Select mesh
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        
        # Normalize all weights
        try:
            bpy.ops.object.vertex_group_normalize_all(lock_active=False)
            self.report({'INFO'}, "All weights normalized")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to normalize: {str(e)}")
            return {'CANCELLED'}
        
        # Restore mode
        if original_mode == 'PAINT_WEIGHT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        
        return {'FINISHED'}


class ASSETSBRIDGE_OT_CleanupWeights(Operator):
    """Remove vertices with very small weights from all vertex groups"""
    bl_idname = "assetsbridge.cleanup_weights"
    bl_label = "Cleanup Small Weights"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Remove weights below this value",
        default=0.01,
        min=0.0,
        max=0.5
    )

    @classmethod
    def poll(cls, context):
        mesh_obj = get_mesh_from_context(context)
        return mesh_obj is not None

    def execute(self, context):
        mesh_obj = get_mesh_from_context(context)
        
        if mesh_obj is None:
            self.report({'ERROR'}, "No mesh selected")
            return {'CANCELLED'}
        
        # Store current mode
        original_mode = context.mode
        
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        
        try:
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=self.threshold)
            self.report({'INFO'}, f"Cleaned weights below {self.threshold}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to clean weights: {str(e)}")
            return {'CANCELLED'}
        
        if original_mode == 'PAINT_WEIGHT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# =============================================================================
# UI PANEL
# =============================================================================

class ASSETSBRIDGE_PT_SkinningPanel(bpy.types.Panel):
    """Panel for easy weight painting with bone buttons."""
    bl_label = "Skinning"
    bl_idname = "ASSETSBRIDGE_PT_skinning"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AssetsBridge"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ab_skinning
        
        mesh_obj = get_mesh_from_context(context)
        armature = get_armature_from_mesh(mesh_obj) if mesh_obj else None
        
        # Status box
        box = layout.box()
        if mesh_obj and armature:
            row = box.row()
            row.label(text=f"Mesh: {mesh_obj.name}", icon='MESH_DATA')
            row = box.row()
            row.label(text=f"Armature: {armature.name}", icon='ARMATURE_DATA')
            
            # Current mode indicator
            if context.mode == 'PAINT_WEIGHT':
                box.label(text="Mode: Weight Paint", icon='WPAINT_HLT')
                # Show active bone
                if armature.data.bones.active:
                    box.label(text=f"Active: {armature.data.bones.active.name}", icon='BONE_DATA')
            else:
                box.label(text="Mode: Object (click bone to enter paint)", icon='OBJECT_DATAMODE')
        else:
            box.label(text="Select a mesh with armature", icon='ERROR')
            return
        
        # Refresh button
        row = layout.row()
        row.operator("assetsbridge.refresh_skinning_bones", text="Refresh Bones", icon='FILE_REFRESH')
        
        # Filter
        row = layout.row()
        row.prop(settings, "filter_text", text="", icon='VIEWZOOM')
        row.prop(settings, "show_all_bones", text="", icon='HIDE_OFF' if settings.show_all_bones else 'HIDE_ON')
        
        layout.separator()
        
        # Bone buttons in 3 columns
        self.draw_bone_columns(context, layout, settings, armature)
        
        layout.separator()
        
        # Utility buttons
        box = layout.box()
        box.label(text="Weight Tools", icon='TOOL_SETTINGS')
        
        row = box.row(align=True)
        row.operator("assetsbridge.copy_weights_across", text="Mirror Weights", icon='MOD_MIRROR')
        
        row = box.row(align=True)
        row.operator("assetsbridge.normalize_all_weights", text="Normalize", icon='NORMALIZE_FCURVES')
        row.operator("assetsbridge.cleanup_weights", text="Cleanup", icon='BRUSH_DATA')

    def draw_bone_columns(self, context, layout, settings, armature):
        """Draw the three-column bone button layout."""
        filter_text = settings.filter_text.lower()
        
        # Helper bones to hide unless show_all is enabled
        helper_patterns = ['twist', 'roll', 'helper', 'ik_', 'fk_', 'ctrl', 'mch', 'def_', 'org_']
        
        def should_show_bone(bone_name):
            """Check if bone should be shown based on filter settings."""
            name_lower = bone_name.lower()
            
            # Apply text filter
            if filter_text and filter_text not in name_lower:
                return False
            
            # Hide helper bones unless show_all is enabled
            if not settings.show_all_bones:
                for pattern in helper_patterns:
                    if pattern in name_lower:
                        return False
            
            return True
        
        # Get bones directly from armature for real-time accuracy
        left_bones = []
        center_bones = []
        right_bones = []
        
        for bone in armature.data.bones:
            if not should_show_bone(bone.name):
                continue
            
            side = get_side_from_bone_name(bone.name)
            if side == 'LEFT':
                left_bones.append(bone.name)
            elif side == 'RIGHT':
                right_bones.append(bone.name)
            else:
                center_bones.append(bone.name)
        
        # Sort for consistent display
        left_bones.sort()
        center_bones.sort()
        right_bones.sort()
        
        # Calculate max rows needed
        max_bones = max(len(left_bones), len(center_bones), len(right_bones))
        
        if max_bones == 0:
            layout.label(text="No bones match filter", icon='INFO')
            return
        
        # Header row
        header = layout.row()
        header.label(text="Left", icon='TRIA_LEFT')
        header.label(text="Center", icon='TRIA_UP')
        header.label(text="Right", icon='TRIA_RIGHT')
        
        # Draw bone buttons
        # Use a scrollable region via box
        box = layout.box()
        col = box.column(align=True)
        
        for i in range(max_bones):
            row = col.row(align=True)
            
            # Left bone button
            if i < len(left_bones):
                bone_name = left_bones[i]
                self.draw_bone_button(row, bone_name, armature)
            else:
                row.label(text="")
            
            # Center bone button
            if i < len(center_bones):
                bone_name = center_bones[i]
                self.draw_bone_button(row, bone_name, armature)
            else:
                row.label(text="")
            
            # Right bone button
            if i < len(right_bones):
                bone_name = right_bones[i]
                self.draw_bone_button(row, bone_name, armature)
            else:
                row.label(text="")

    def draw_bone_button(self, row, bone_name, armature):
        """Draw a single bone button with appropriate styling."""
        # Check if this is the active bone
        is_active = (armature.data.bones.active and 
                     armature.data.bones.active.name == bone_name)
        
        # Create operator button
        op = row.operator(
            "assetsbridge.select_bone_for_paint",
            text=self.get_short_bone_name(bone_name),
            depress=is_active
        )
        op.bone_name = bone_name

    def get_short_bone_name(self, bone_name):
        """Get a shortened version of the bone name for button display."""
        # Remove common prefixes
        prefixes = ['DEF_', 'DEF-', 'def_', 'def-', 'ORG_', 'ORG-', 'org_', 'org-']
        name = bone_name
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # Truncate if too long
        if len(name) > 12:
            name = name[:10] + ".."
        
        return name


# =============================================================================
# REGISTRATION
# =============================================================================

classes = [
    SkinningBoneItem,
    SkinningSettings,
    ASSETSBRIDGE_OT_SelectBoneForPaint,
    ASSETSBRIDGE_OT_RefreshSkinningBones,
    ASSETSBRIDGE_OT_CopyWeightsAcross,
    ASSETSBRIDGE_OT_NormalizeAllWeights,
    ASSETSBRIDGE_OT_CleanupWeights,
    ASSETSBRIDGE_PT_SkinningPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ab_skinning = PointerProperty(type=SkinningSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ab_skinning
