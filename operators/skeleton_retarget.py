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
import re
from mathutils import Vector, Matrix
from bpy.props import (
    StringProperty, 
    BoolProperty, 
    FloatProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty
)
from bpy.types import PropertyGroup, Operator


# =============================================================================
# BONE NAME MAPPING - Common UE5 to various skeleton naming conventions
# =============================================================================

UE5_BONE_ALIASES = {
    'root': ['root', 'main', 'origin', 'armature'],
    'pelvis': ['pelvis', 'hips', 'hip', 'cog', 'center_of_gravity'],
    'spine_01': ['spine', 'spine1', 'spine_01', 'spine.001', 'abdomen'],
    'spine_02': ['spine2', 'spine_02', 'spine.002', 'chest_lower'],
    'spine_03': ['spine3', 'spine_03', 'spine.003', 'chest', 'chest_upper'],
    'spine_04': ['spine4', 'spine_04', 'spine.004'],
    'spine_05': ['spine5', 'spine_05', 'spine.005'],
    'neck_01': ['neck', 'neck1', 'neck_01', 'neck.001'],
    'neck_02': ['neck2', 'neck_02', 'neck.002'],
    'head': ['head', 'skull'],
    'clavicle_l': ['clavicle_l', 'collar_l', 'shoulder_l', 'leftshoulder', 'l_clavicle', 'clavicle.l'],
    'clavicle_r': ['clavicle_r', 'collar_r', 'shoulder_r', 'rightshoulder', 'r_clavicle', 'clavicle.r'],
    'upperarm_l': ['upperarm_l', 'arm_l', 'leftarm', 'l_upperarm', 'upper_arm_l', 'upperarm.l'],
    'upperarm_r': ['upperarm_r', 'arm_r', 'rightarm', 'r_upperarm', 'upper_arm_r', 'upperarm.r'],
    'lowerarm_l': ['lowerarm_l', 'forearm_l', 'leftforearm', 'l_lowerarm', 'lower_arm_l', 'lowerarm.l'],
    'lowerarm_r': ['lowerarm_r', 'forearm_r', 'rightforearm', 'r_lowerarm', 'lower_arm_r', 'lowerarm.r'],
    'hand_l': ['hand_l', 'lefthand', 'l_hand', 'wrist_l', 'hand.l'],
    'hand_r': ['hand_r', 'righthand', 'r_hand', 'wrist_r', 'hand.r'],
    'thigh_l': ['thigh_l', 'upperleg_l', 'leftupleg', 'l_thigh', 'upper_leg_l', 'thigh.l'],
    'thigh_r': ['thigh_r', 'upperleg_r', 'rightupleg', 'r_thigh', 'upper_leg_r', 'thigh.r'],
    'calf_l': ['calf_l', 'lowerleg_l', 'shin_l', 'leftleg', 'l_calf', 'lower_leg_l', 'calf.l'],
    'calf_r': ['calf_r', 'lowerleg_r', 'shin_r', 'rightleg', 'r_calf', 'lower_leg_r', 'calf.r'],
    'foot_l': ['foot_l', 'leftfoot', 'l_foot', 'ankle_l', 'foot.l'],
    'foot_r': ['foot_r', 'rightfoot', 'r_foot', 'ankle_r', 'foot.r'],
    'ball_l': ['ball_l', 'toe_l', 'lefttoebase', 'l_ball', 'toes_l', 'ball.l'],
    'ball_r': ['ball_r', 'toe_r', 'righttoebase', 'r_ball', 'toes_r', 'ball.r'],
}

FINGER_PATTERNS = {
    'thumb': ['thumb', 'finger0', 'finger_0'],
    'index': ['index', 'finger1', 'finger_1', 'pointer'],
    'middle': ['middle', 'finger2', 'finger_2', 'mid'],
    'ring': ['ring', 'finger3', 'finger_3'],
    'pinky': ['pinky', 'finger4', 'finger_4', 'little', 'small'],
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def levenshtein_distance(s1, s2):
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def normalize_bone_name(name):
    """Normalize bone name for comparison - lowercase, remove common prefixes/suffixes."""
    name = name.lower().strip()
    # Remove common prefixes
    prefixes = ['def_', 'def-', 'drv_', 'drv-', 'ctrl_', 'ctrl-', 'ik_', 'ik-', 'fk_', 'fk-', 'mch_', 'mch-']
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    # Remove common suffixes
    suffixes = ['_def', '-def', '_drv', '-drv', '_ctrl', '-ctrl']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


def get_side_from_name(name):
    """Determine if bone is left, right, or center."""
    name_lower = name.lower()
    
    left_patterns = ['_l', '.l', '-l', 'left', '_left', '.left', '-left', 'l_', 'l.', 'l-']
    right_patterns = ['_r', '.r', '-r', 'right', '_right', '.right', '-right', 'r_', 'r.', 'r-']
    
    for pattern in left_patterns:
        if pattern in name_lower or name_lower.endswith(pattern) or name_lower.startswith(pattern):
            return 'left'
    
    for pattern in right_patterns:
        if pattern in name_lower or name_lower.endswith(pattern) or name_lower.startswith(pattern):
            return 'right'
    
    return 'center'


def compute_match_confidence(ue5_bone, target_bone):
    """
    Compute confidence score (0.0 to 1.0) for a bone name match.
    Returns tuple: (confidence, match_reason)
    """
    ue5_norm = normalize_bone_name(ue5_bone)
    target_norm = normalize_bone_name(target_bone)
    
    # Exact match after normalization
    if ue5_norm == target_norm:
        return (1.0, "exact_match")
    
    # Check alias table
    ue5_lower = ue5_bone.lower()
    for ue5_canonical, aliases in UE5_BONE_ALIASES.items():
        if ue5_lower == ue5_canonical or ue5_lower in aliases:
            if target_norm in aliases or target_norm == ue5_canonical:
                return (0.95, "alias_match")
    
    # Check side consistency
    ue5_side = get_side_from_name(ue5_bone)
    target_side = get_side_from_name(target_bone)
    
    if ue5_side != target_side and ue5_side != 'center' and target_side != 'center':
        return (0.0, "side_mismatch")
    
    # Levenshtein-based fuzzy match
    max_len = max(len(ue5_norm), len(target_norm))
    if max_len == 0:
        return (0.0, "empty_names")
    
    distance = levenshtein_distance(ue5_norm, target_norm)
    similarity = 1.0 - (distance / max_len)
    
    # Boost score if key substrings match
    key_parts = ['spine', 'arm', 'leg', 'hand', 'foot', 'head', 'neck', 'thigh', 'calf', 'shoulder']
    for part in key_parts:
        if part in ue5_norm and part in target_norm:
            similarity = min(1.0, similarity + 0.15)
            break
    
    # Finger matching
    for finger, patterns in FINGER_PATTERNS.items():
        ue5_has_finger = any(p in ue5_norm for p in patterns) or finger in ue5_norm
        target_has_finger = any(p in target_norm for p in patterns) or finger in target_norm
        if ue5_has_finger and target_has_finger:
            similarity = min(1.0, similarity + 0.2)
            break
        elif ue5_has_finger != target_has_finger:
            similarity = max(0.0, similarity - 0.3)
    
    if similarity >= 0.7:
        return (similarity, "fuzzy_high")
    elif similarity >= 0.5:
        return (similarity, "fuzzy_medium")
    else:
        return (similarity, "fuzzy_low")


def build_bone_mapping(ue5_armature, target_armature):
    """
    Build automatic bone mapping between UE5 skeleton and target skeleton.
    Uses multi-pass approach: exact matches first, then fuzzy matching.
    Returns list of dicts with mapping info and confidence scores.
    """
    ue5_bones = [bone.name for bone in ue5_armature.data.bones]
    target_bones = [bone.name for bone in target_armature.data.bones]
    
    # Create lookup sets for fast matching
    target_bones_lower = {bone.lower(): bone for bone in target_bones}
    target_bones_normalized = {normalize_bone_name(bone): bone for bone in target_bones}
    
    used_targets = set()
    mapping_results = {}  # ue5_bone -> mapping dict
    
    # =========================================================================
    # PASS 1: Exact case-insensitive matches (highest priority)
    # =========================================================================
    for ue5_bone in ue5_bones:
        ue5_lower = ue5_bone.lower()
        
        if ue5_lower in target_bones_lower:
            target_bone = target_bones_lower[ue5_lower]
            if target_bone not in used_targets:
                mapping_results[ue5_bone] = {
                    'ue5_bone': ue5_bone,
                    'target_bone': target_bone,
                    'confidence': 1.0,
                    'category': 'HIGH',
                    'reason': 'exact_match',
                    'enabled': True,
                }
                used_targets.add(target_bone)
    
    # =========================================================================
    # PASS 2: Normalized exact matches (e.g., def_spine_01 -> spine_01)
    # =========================================================================
    for ue5_bone in ue5_bones:
        if ue5_bone in mapping_results:
            continue
        
        ue5_norm = normalize_bone_name(ue5_bone)
        
        if ue5_norm in target_bones_normalized:
            target_bone = target_bones_normalized[ue5_norm]
            if target_bone not in used_targets:
                mapping_results[ue5_bone] = {
                    'ue5_bone': ue5_bone,
                    'target_bone': target_bone,
                    'confidence': 0.95,
                    'category': 'HIGH',
                    'reason': 'normalized_match',
                    'enabled': True,
                }
                used_targets.add(target_bone)
    
    # =========================================================================
    # PASS 3: Alias table matches
    # =========================================================================
    for ue5_bone in ue5_bones:
        if ue5_bone in mapping_results:
            continue
        
        ue5_lower = ue5_bone.lower()
        matched = False
        
        for ue5_canonical, aliases in UE5_BONE_ALIASES.items():
            if ue5_lower == ue5_canonical or ue5_lower in aliases:
                # Found UE5 bone in alias table, look for target match
                for target_bone in target_bones:
                    if target_bone in used_targets:
                        continue
                    target_lower = target_bone.lower()
                    if target_lower == ue5_canonical or target_lower in aliases:
                        mapping_results[ue5_bone] = {
                            'ue5_bone': ue5_bone,
                            'target_bone': target_bone,
                            'confidence': 0.90,
                            'category': 'HIGH',
                            'reason': 'alias_match',
                            'enabled': True,
                        }
                        used_targets.add(target_bone)
                        matched = True
                        break
                if matched:
                    break
    
    # =========================================================================
    # PASS 4: Fuzzy matching for remaining bones
    # =========================================================================
    remaining_ue5 = [b for b in ue5_bones if b not in mapping_results]
    remaining_targets = [b for b in target_bones if b not in used_targets]
    
    for ue5_bone in remaining_ue5:
        best_match = None
        best_confidence = 0.0
        best_reason = "no_match"
        
        for target_bone in remaining_targets:
            if target_bone in used_targets:
                continue
            
            confidence, reason = compute_match_confidence(ue5_bone, target_bone)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = target_bone
                best_reason = reason
        
        # Determine confidence category
        if best_confidence >= 0.85:
            category = 'HIGH'
        elif best_confidence >= 0.5:
            category = 'MEDIUM'
        elif best_match is not None and best_confidence >= 0.3:
            category = 'LOW'
        else:
            category = 'NONE'
        
        mapping_results[ue5_bone] = {
            'ue5_bone': ue5_bone,
            'target_bone': best_match if best_confidence >= 0.3 else "",
            'confidence': best_confidence,
            'category': category,
            'reason': best_reason,
            'enabled': best_confidence >= 0.5,
        }
        
        if best_match and best_confidence >= 0.3:
            used_targets.add(best_match)
    
    # Return mappings in original bone order
    return [mapping_results[bone] for bone in ue5_bones]


# =============================================================================
# PROPERTY GROUPS
# =============================================================================

class BoneMappingItem(PropertyGroup):
    """Single bone mapping entry for UI display."""
    ue5_bone: StringProperty(name="UE5 Bone", default="")
    target_bone: StringProperty(name="Target Bone", default="")
    confidence: FloatProperty(name="Confidence", default=0.0, min=0.0, max=1.0)
    category: EnumProperty(
        name="Category",
        items=[
            ('HIGH', "High", "High confidence match"),
            ('MEDIUM', "Medium", "Medium confidence - review recommended"),
            ('LOW', "Low", "Low confidence - likely wrong"),
            ('NONE', "None", "No match found"),
        ],
        default='NONE'
    )
    enabled: BoolProperty(name="Enabled", default=True)
    reason: StringProperty(name="Reason", default="")


class SkeletonRetargetSettings(PropertyGroup):
    """Settings for skeleton retargeting stored on Scene."""
    source_armature: PointerProperty(
        name="UE5 Skeleton",
        description="The UE5 skeleton to use as source",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    target_armature: PointerProperty(
        name="Target Skeleton",
        description="The target skeleton to match",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    bone_mappings: CollectionProperty(type=BoneMappingItem)
    active_mapping_index: IntProperty(name="Active Mapping Index", default=0)
    show_high_confidence: BoolProperty(name="Show High", default=True)
    show_medium_confidence: BoolProperty(name="Show Medium", default=True)
    show_low_confidence: BoolProperty(name="Show Low", default=True)
    show_unmapped: BoolProperty(name="Show Unmapped", default=True)


# =============================================================================
# OPERATORS
# =============================================================================

class ASSETSBRIDGE_OT_BuildBoneMapping(Operator):
    """Analyze both skeletons and build automatic bone name mapping"""
    bl_idname = "assetsbridge.build_bone_mapping"
    bl_label = "Build Bone Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) != 2:
            return False
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        return len(armatures) == 2 and context.active_object in armatures

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        target_armature = context.active_object
        source_armature = [obj for obj in armatures if obj != target_armature][0]
        
        settings = context.scene.ab_skeleton_retarget
        settings.source_armature = source_armature
        settings.target_armature = target_armature
        
        # Log all bones for reference
        self.log_bone_lists(source_armature, target_armature)
        
        # Clear existing mappings
        settings.bone_mappings.clear()
        
        # Build mappings
        mappings = build_bone_mapping(source_armature, target_armature)
        
        high_count = 0
        medium_count = 0
        low_count = 0
        unmapped_count = 0
        
        for mapping in mappings:
            item = settings.bone_mappings.add()
            item.ue5_bone = mapping['ue5_bone']
            item.target_bone = mapping['target_bone']
            item.confidence = mapping['confidence']
            item.category = mapping['category']
            item.enabled = mapping['enabled']
            item.reason = mapping['reason']
            
            if mapping['category'] == 'HIGH':
                high_count += 1
            elif mapping['category'] == 'MEDIUM':
                medium_count += 1
            elif mapping['category'] == 'LOW':
                low_count += 1
            else:
                unmapped_count += 1
        
        self.report({'INFO'}, f"Mapping complete: {high_count} high, {medium_count} medium, {low_count} low, {unmapped_count} unmapped")
        return {'FINISHED'}
    
    def log_bone_lists(self, source_armature, target_armature):
        """Log all bones from both skeletons for reference.
        Creates a Text block in Blender for easy viewing."""
        source_bones = [bone.name for bone in source_armature.data.bones]
        target_bones = [bone.name for bone in target_armature.data.bones]
        
        # Build the log content
        lines = []
        lines.append("=" * 80)
        lines.append("SKELETON RETARGET - BONE REFERENCE LIST")
        lines.append("=" * 80)
        
        lines.append(f"\nUE5 SOURCE SKELETON: {source_armature.name}")
        lines.append(f"Total bones: {len(source_bones)}")
        lines.append("-" * 40)
        for i, bone in enumerate(source_bones, 1):
            lines.append(f"  {i:3d}. {bone}")
        
        lines.append(f"\nTARGET SKELETON: {target_armature.name}")
        lines.append(f"Total bones: {len(target_bones)}")
        lines.append("-" * 40)
        for i, bone in enumerate(target_bones, 1):
            lines.append(f"  {i:3d}. {bone}")
        
        lines.append("\n" + "=" * 80)
        lines.append("END OF BONE REFERENCE LIST")
        lines.append("=" * 80)
        
        log_text = "\n".join(lines)
        
        # Print to system console
        print(log_text)
        
        # Also create/update a Text block for easy access
        text_name = "AB_BoneMapping_Log"
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(text_name)
        
        text_block.write(log_text)
        
        self.report({'INFO'}, f"Bone list saved to Text block '{text_name}' (see Text Editor)")


class ASSETSBRIDGE_OT_ClearBoneMapping(Operator):
    """Clear the current bone mapping"""
    bl_idname = "assetsbridge.clear_bone_mapping"
    bl_label = "Clear Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.ab_skeleton_retarget
        settings.bone_mappings.clear()
        settings.source_armature = None
        settings.target_armature = None
        self.report({'INFO'}, "Bone mapping cleared")
        return {'FINISHED'}


class ASSETSBRIDGE_OT_RetargetSkeleton(Operator):
    """Align UE5 skeleton to target and transfer mesh weights"""
    bl_idname = "assetsbridge.retarget_skeleton"
    bl_label = "Retarget Skeleton to UE5"
    bl_options = {'REGISTER', 'UNDO'}

    transfer_weights: BoolProperty(
        name="Transfer Weights",
        description="Transfer vertex weights from target skeleton to UE5 skeleton",
        default=True
    )
    
    apply_scale: BoolProperty(
        name="Apply Scale",
        description="Apply scale to bone data (recommended)",
        default=True
    )
    
    delete_target_skeleton: BoolProperty(
        name="Delete Target Skeleton",
        description="Delete the original target skeleton after transfer (recommended)",
        default=True
    )
    
    delete_ue5_source_mesh: BoolProperty(
        name="Delete UE5 Source Mesh",
        description="Delete meshes originally parented to the UE5 skeleton (e.g., Mannequin)",
        default=True
    )

    @classmethod
    def poll(cls, context):
        settings = context.scene.ab_skeleton_retarget
        return (settings.source_armature is not None and 
                settings.target_armature is not None and
                len(settings.bone_mappings) > 0)

    def execute(self, context):
        settings = context.scene.ab_skeleton_retarget
        source = settings.source_armature
        target = settings.target_armature
        
        # Validate armatures still exist
        if source is None or target is None:
            self.report({'ERROR'}, "Source or target armature no longer exists")
            return {'CANCELLED'}
        
        # Build mapping dict from enabled mappings only
        bone_map = {}
        skipped_bones = []
        
        for mapping in settings.bone_mappings:
            if mapping.enabled and mapping.target_bone:
                bone_map[mapping.ue5_bone] = mapping.target_bone
            else:
                skipped_bones.append(mapping.ue5_bone)
        
        if not bone_map:
            self.report({'ERROR'}, "No enabled bone mappings found")
            return {'CANCELLED'}
        
        # Log skipped bones
        if skipped_bones:
            self.report({'WARNING'}, f"Skipping {len(skipped_bones)} unmapped/disabled bones")
        
        # Collect UE5 source meshes BEFORE transfer (meshes parented to UE5 skeleton)
        ue5_source_meshes = []
        if self.delete_ue5_source_mesh:
            ue5_source_meshes = self.find_meshes_for_armature(source)
        
        # Step 1: Align UE5 skeleton bones to target positions
        aligned_count = self.align_skeleton_bones(context, source, target, bone_map)
        
        if aligned_count == 0:
            self.report({'ERROR'}, "No bones were aligned - check your mapping")
            return {'CANCELLED'}
        
        # Step 2: Transfer weights and collect transferred meshes
        transferred_meshes = []
        if self.transfer_weights:
            transferred_meshes = self.transfer_mesh_weights(context, source, target, bone_map)
        
        # Step 3: Setup proper hierarchy - move UE5 skeleton to target's position, parent meshes
        self.setup_hierarchy(context, source, target, transferred_meshes)
        
        # Step 4: Delete UE5 source meshes (if they exist and weren't transferred)
        deleted_ue5_meshes = 0
        if self.delete_ue5_source_mesh and ue5_source_meshes:
            deleted_ue5_meshes = self.cleanup_ue5_meshes(context, ue5_source_meshes, transferred_meshes)
        
        # Step 5: Delete target skeleton
        deleted_target = False
        if self.delete_target_skeleton and target:
            deleted_target = self.cleanup_target_skeleton(context, target)
        
        # Clear the mapping references since target is deleted
        if deleted_target:
            settings.target_armature = None
            settings.bone_mappings.clear()
        
        # Build result message
        msg_parts = [f"{aligned_count} bones aligned", f"{len(transferred_meshes)} meshes rebound"]
        if deleted_ue5_meshes > 0:
            msg_parts.append(f"{deleted_ue5_meshes} UE5 meshes deleted")
        if deleted_target:
            msg_parts.append("target skeleton deleted")
        
        self.report({'INFO'}, f"Retarget complete: {', '.join(msg_parts)}")
        return {'FINISHED'}
    
    def find_meshes_for_armature(self, armature):
        """Find all meshes parented to or using this armature."""
        meshes = []
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            
            # Check armature modifier
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object == armature:
                    if obj not in meshes:
                        meshes.append(obj)
                    break
            
            # Check parent
            if obj.parent == armature and obj not in meshes:
                meshes.append(obj)
        
        return meshes
    
    def setup_hierarchy(self, context, source_armature, target_armature, meshes):
        """Setup proper parent-child hierarchy for export.
        Moves source armature to target's position in hierarchy, then parents meshes to it."""
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # =========================================================================
        # Step 1: Move source armature to target's position in hierarchy
        # =========================================================================
        
        # Capture target's hierarchy info before it gets deleted
        target_parent = target_armature.parent if target_armature else None
        target_collections = list(target_armature.users_collection) if target_armature else []
        
        # Move source armature to target's parent
        if target_parent:
            # Store world transform
            world_matrix = source_armature.matrix_world.copy()
            
            # Set parent
            source_armature.parent = target_parent
            source_armature.parent_type = 'OBJECT'
            
            # Restore world transform
            source_armature.matrix_parent_inverse = target_parent.matrix_world.inverted() @ world_matrix
        
        # Move source armature to target's collections
        if target_collections:
            # Get source's current collections
            source_collections = list(source_armature.users_collection)
            
            # Add to target's collections
            for coll in target_collections:
                if source_armature.name not in coll.objects:
                    coll.objects.link(source_armature)
            
            # Remove from old collections (except if it's also a target collection)
            for coll in source_collections:
                if coll not in target_collections:
                    coll.objects.unlink(source_armature)
        
        # =========================================================================
        # Step 2: Parent meshes to source armature
        # =========================================================================
        for mesh_obj in meshes:
            if mesh_obj is None:
                continue
            
            # Ensure mesh is parented to armature
            if mesh_obj.parent != source_armature:
                # Store world transform
                world_matrix = mesh_obj.matrix_world.copy()
                
                # Set parent
                mesh_obj.parent = source_armature
                mesh_obj.parent_type = 'OBJECT'
                
                # Restore world transform via parent inverse
                mesh_obj.matrix_parent_inverse = source_armature.matrix_world.inverted() @ world_matrix
            
            # Ensure armature modifier exists and points to correct armature
            has_armature_mod = False
            for mod in mesh_obj.modifiers:
                if mod.type == 'ARMATURE':
                    mod.object = source_armature
                    has_armature_mod = True
                    break
            
            if not has_armature_mod:
                mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = source_armature
    
    def cleanup_ue5_meshes(self, context, ue5_meshes, transferred_meshes):
        """Delete UE5 source meshes that weren't transferred."""
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        deleted = 0
        for mesh_obj in ue5_meshes:
            # Don't delete if it was a transferred mesh
            if mesh_obj in transferred_meshes:
                continue
            
            # Check if object still exists
            if mesh_obj is None or mesh_obj.name not in bpy.data.objects:
                continue
            
            # Delete the mesh
            bpy.data.objects.remove(mesh_obj, do_unlink=True)
            deleted += 1
        
        return deleted
    
    def cleanup_target_skeleton(self, context, target):
        """Delete the target skeleton after transfer."""
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Check if object still exists
        if target is None or target.name not in bpy.data.objects:
            return False
        
        # Deselect all first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Delete the armature
        bpy.data.objects.remove(target, do_unlink=True)
        return True

    def align_skeleton_bones(self, context, source, target, bone_map):
        """Align source (UE5) skeleton bones to match target skeleton positions."""
        aligned = 0
        
        # Ensure we're in object mode first
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Select and make source active
        bpy.ops.object.select_all(action='DESELECT')
        source.select_set(True)
        context.view_layer.objects.active = source
        
        # Enter edit mode on source armature
        bpy.ops.object.mode_set(mode='EDIT')
        
        source_edit_bones = source.data.edit_bones
        target_bones = target.data.bones
        
        # Get world matrices for coordinate transform
        source_matrix_inv = source.matrix_world.inverted()
        target_matrix = target.matrix_world
        
        for ue5_bone_name, target_bone_name in bone_map.items():
            if ue5_bone_name not in source_edit_bones:
                continue
            if target_bone_name not in target_bones:
                continue
            
            source_ebone = source_edit_bones[ue5_bone_name]
            target_bone = target_bones[target_bone_name]
            
            # Get target bone head/tail in world space, then convert to source local space
            target_head_world = target_matrix @ target_bone.head_local
            target_tail_world = target_matrix @ target_bone.tail_local
            
            source_head_local = source_matrix_inv @ target_head_world
            source_tail_local = source_matrix_inv @ target_tail_world
            
            # Apply positions
            source_ebone.head = source_head_local
            source_ebone.tail = source_tail_local
            
            # Copy bone roll from target
            source_ebone.roll = target_bone.matrix_local.to_euler()[2]
            
            aligned += 1
        
        # Back to object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Apply scale if requested
        if self.apply_scale:
            bpy.ops.object.select_all(action='DESELECT')
            source.select_set(True)
            context.view_layer.objects.active = source
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        return aligned

    def transfer_mesh_weights(self, context, source, target, bone_map):
        """Transfer vertex weights from meshes bound to target to source skeleton.
        Returns list of successfully transferred mesh objects."""
        transferred_meshes = []
        
        # Find all meshes parented to or using the target armature
        meshes_to_transfer = []
        
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            
            # Check if mesh has armature modifier pointing to target
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object == target:
                    meshes_to_transfer.append(obj)
                    break
            
            # Also check parent
            if obj.parent == target and obj not in meshes_to_transfer:
                meshes_to_transfer.append(obj)
        
        for mesh_obj in meshes_to_transfer:
            success = self.transfer_single_mesh_weights(context, mesh_obj, source, target, bone_map)
            if success:
                transferred_meshes.append(mesh_obj)
        
        return transferred_meshes

    def transfer_single_mesh_weights(self, context, mesh_obj, source, target, bone_map):
        """Transfer weights for a single mesh object."""
        
        # Ensure object mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Create reverse mapping (target bone -> ue5 bone)
        reverse_map = {v: k for k, v in bone_map.items()}
        
        # Rename vertex groups from target names to UE5 names
        renamed_groups = 0
        groups_to_rename = []
        
        for vg in mesh_obj.vertex_groups:
            if vg.name in reverse_map:
                groups_to_rename.append((vg, reverse_map[vg.name]))
        
        for vg, new_name in groups_to_rename:
            # Check if target name already exists
            existing = mesh_obj.vertex_groups.get(new_name)
            if existing and existing != vg:
                # Merge weights
                self.merge_vertex_groups(mesh_obj, vg, existing)
                mesh_obj.vertex_groups.remove(vg)
            else:
                vg.name = new_name
            renamed_groups += 1
        
        # Update armature modifier to point to source (UE5) skeleton
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == target:
                mod.object = source
        
        # Update parent if needed
        if mesh_obj.parent == target:
            mesh_obj.parent = source
            # Preserve transform
            mesh_obj.matrix_parent_inverse = source.matrix_world.inverted()
        
        return renamed_groups > 0

    def merge_vertex_groups(self, mesh_obj, source_vg, target_vg):
        """Merge weights from source vertex group into target vertex group."""
        mesh = mesh_obj.data
        
        for vert in mesh.vertices:
            try:
                source_weight = source_vg.weight(vert.index)
                try:
                    target_weight = target_vg.weight(vert.index)
                    # Average the weights
                    target_vg.add([vert.index], (source_weight + target_weight) / 2, 'REPLACE')
                except RuntimeError:
                    # Target doesn't have this vert, just add it
                    target_vg.add([vert.index], source_weight, 'REPLACE')
            except RuntimeError:
                # Source doesn't have this vert, skip
                pass

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ab_skeleton_retarget
        
        box = layout.box()
        box.label(text="Retarget Configuration", icon='ARMATURE_DATA')
        
        if settings.source_armature and settings.target_armature:
            row = box.row()
            row.label(text=f"UE5 Source: {settings.source_armature.name}", icon='FORWARD')
            row = box.row()
            row.label(text=f"Target: {settings.target_armature.name}", icon='BACK')
            
            # Count mappings
            enabled = sum(1 for m in settings.bone_mappings if m.enabled and m.target_bone)
            total = len(settings.bone_mappings)
            box.label(text=f"Enabled Mappings: {enabled} / {total}")
        
        layout.separator()
        layout.label(text="Transfer Options:", icon='OPTIONS')
        layout.prop(self, "transfer_weights")
        layout.prop(self, "apply_scale")
        
        layout.separator()
        layout.label(text="Cleanup Options:", icon='TRASH')
        layout.prop(self, "delete_target_skeleton")
        layout.prop(self, "delete_ue5_source_mesh")
        
        layout.separator()
        box = layout.box()
        box.label(text="⚠ DESTRUCTIVE OPERATION", icon='ERROR')
        col = box.column(align=True)
        col.label(text="This will:")
        col.label(text="  • Modify UE5 skeleton bone positions")
        if self.delete_target_skeleton:
            col.label(text="  • DELETE the target skeleton", icon='X')
        if self.delete_ue5_source_mesh:
            col.label(text="  • DELETE UE5 source meshes (e.g., Mannequin)", icon='X')
        col.label(text="")
        col.label(text="This cannot be undone easily. Save first!")


class ASSETSBRIDGE_OT_SetMappingTarget(Operator):
    """Set target bone for selected mapping from active bone"""
    bl_idname = "assetsbridge.set_mapping_target"
    bl_label = "Set Target from Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.ab_skeleton_retarget
        if not settings.bone_mappings:
            return False
        if settings.active_mapping_index >= len(settings.bone_mappings):
            return False
        # Check if we have a bone selected
        if context.mode == 'POSE' and context.active_pose_bone:
            return True
        if context.mode == 'EDIT_ARMATURE' and context.active_bone:
            return True
        return False

    def execute(self, context):
        settings = context.scene.ab_skeleton_retarget
        mapping = settings.bone_mappings[settings.active_mapping_index]
        
        if context.mode == 'POSE':
            bone_name = context.active_pose_bone.name
        else:
            bone_name = context.active_bone.name
        
        mapping.target_bone = bone_name
        mapping.enabled = True
        mapping.confidence = 1.0
        mapping.category = 'HIGH'
        mapping.reason = 'manual_override'
        
        self.report({'INFO'}, f"Set {mapping.ue5_bone} -> {bone_name}")
        return {'FINISHED'}


class ASSETSBRIDGE_OT_ToggleAllMappings(Operator):
    """Enable or disable all bone mappings"""
    bl_idname = "assetsbridge.toggle_all_mappings"
    bl_label = "Toggle All Mappings"
    bl_options = {'REGISTER', 'UNDO'}

    enable: BoolProperty(name="Enable", default=True)

    def execute(self, context):
        settings = context.scene.ab_skeleton_retarget
        for mapping in settings.bone_mappings:
            if mapping.target_bone:  # Only toggle if there's a mapping
                mapping.enabled = self.enable
        
        action = "Enabled" if self.enable else "Disabled"
        self.report({'INFO'}, f"{action} all bone mappings")
        return {'FINISHED'}


# =============================================================================
# UI LIST
# =============================================================================

class ASSETSBRIDGE_UL_BoneMappingList(bpy.types.UIList):
    """UI List for displaying bone mappings with color-coded confidence."""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        settings = context.scene.ab_skeleton_retarget
        
        # Filter by category visibility
        if item.category == 'HIGH' and not settings.show_high_confidence:
            return
        if item.category == 'MEDIUM' and not settings.show_medium_confidence:
            return
        if item.category == 'LOW' and not settings.show_low_confidence:
            return
        if item.category == 'NONE' and not settings.show_unmapped:
            return
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Enable checkbox
            row.prop(item, "enabled", text="")
            
            # Color-coded icon based on confidence
            if item.category == 'HIGH':
                icon = 'CHECKMARK'
            elif item.category == 'MEDIUM':
                icon = 'QUESTION'
            elif item.category == 'LOW':
                icon = 'ERROR'
            else:
                icon = 'CANCEL'
            
            row.label(text="", icon=icon)
            
            # Bone names
            split = row.split(factor=0.45)
            split.label(text=item.ue5_bone)
            
            split2 = split.split(factor=0.7)
            if item.target_bone:
                split2.prop(item, "target_bone", text="")
            else:
                split2.label(text="(unmapped)", icon='BLANK1')
            
            # Confidence percentage
            split2.label(text=f"{item.confidence:.0%}")
        
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.ue5_bone)
    
    def filter_items(self, context, data, propname):
        settings = context.scene.ab_skeleton_retarget
        items = getattr(data, propname)
        
        # Filter
        flt_flags = []
        for item in items:
            show = True
            if item.category == 'HIGH' and not settings.show_high_confidence:
                show = False
            elif item.category == 'MEDIUM' and not settings.show_medium_confidence:
                show = False
            elif item.category == 'LOW' and not settings.show_low_confidence:
                show = False
            elif item.category == 'NONE' and not settings.show_unmapped:
                show = False
            
            flt_flags.append(self.bitflag_filter_item if show else 0)
        
        # Sort by category then confidence
        flt_neworder = []
        category_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'NONE': 3}
        sorted_items = sorted(
            enumerate(items),
            key=lambda x: (category_order.get(x[1].category, 4), -x[1].confidence)
        )
        flt_neworder = [i for i, _ in sorted_items]
        
        return flt_flags, flt_neworder


# =============================================================================
# PANEL
# =============================================================================

class ASSETSBRIDGE_PT_SkeletonRetargetPanel(bpy.types.Panel):
    """Panel for skeleton retargeting tools."""
    bl_label = "Skeleton Retarget"
    bl_idname = "ASSETSBRIDGE_PT_skeleton_retarget"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AssetsBridge"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ab_skeleton_retarget
        
        # Selection info
        box = layout.box()
        box.label(text="1. Select Skeletons", icon='ARMATURE_DATA')
        
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        if len(armatures) == 2:
            target = context.active_object if context.active_object in armatures else None
            source = [a for a in armatures if a != target][0] if target else None
            
            if source and target:
                row = box.row()
                row.label(text=f"UE5 Source: {source.name}", icon='FORWARD')
                row = box.row()
                row.label(text=f"Target (Active): {target.name}", icon='BACK')
        else:
            box.label(text="Select 2 armatures (target = active)")
        
        row = box.row()
        row.operator("assetsbridge.build_bone_mapping", text="Build Mapping", icon='FILE_REFRESH')
        row.operator("assetsbridge.clear_bone_mapping", text="Clear", icon='X')
        
        # Mapping list
        if settings.bone_mappings:
            box = layout.box()
            box.label(text="2. Review Bone Mapping", icon='BONE_DATA')
            
            # Filter toggles
            row = box.row(align=True)
            row.prop(settings, "show_high_confidence", text="", icon='CHECKMARK', toggle=True)
            row.prop(settings, "show_medium_confidence", text="", icon='QUESTION', toggle=True)
            row.prop(settings, "show_low_confidence", text="", icon='ERROR', toggle=True)
            row.prop(settings, "show_unmapped", text="", icon='CANCEL', toggle=True)
            
            # Statistics
            high = sum(1 for m in settings.bone_mappings if m.category == 'HIGH')
            medium = sum(1 for m in settings.bone_mappings if m.category == 'MEDIUM')
            low = sum(1 for m in settings.bone_mappings if m.category == 'LOW')
            unmapped = sum(1 for m in settings.bone_mappings if m.category == 'NONE')
            
            row = box.row()
            row.label(text=f"H:{high} M:{medium} L:{low} U:{unmapped}")
            
            # UIList
            row = box.row()
            row.template_list(
                "ASSETSBRIDGE_UL_BoneMappingList", "",
                settings, "bone_mappings",
                settings, "active_mapping_index",
                rows=8
            )
            
            # Manual mapping tools
            col = row.column(align=True)
            col.operator("assetsbridge.set_mapping_target", text="", icon='EYEDROPPER')
            col.separator()
            op = col.operator("assetsbridge.toggle_all_mappings", text="", icon='CHECKBOX_HLT')
            op.enable = True
            op = col.operator("assetsbridge.toggle_all_mappings", text="", icon='CHECKBOX_DEHLT')
            op.enable = False
            
            # Active mapping details
            if settings.active_mapping_index < len(settings.bone_mappings):
                active = settings.bone_mappings[settings.active_mapping_index]
                detail_box = box.box()
                detail_box.label(text=f"UE5: {active.ue5_bone}")
                detail_box.prop(active, "target_bone", text="Target")
                detail_box.prop(active, "enabled")
                detail_box.label(text=f"Confidence: {active.confidence:.1%} ({active.reason})")
        
        # Finalize
        layout.separator()
        box = layout.box()
        box.label(text="3. Finalize", icon='PLAY')
        
        enabled = bool(settings.source_armature and settings.target_armature and len(settings.bone_mappings) > 0)
        row = box.row(align=True)
        row.scale_y = 1.5
        row.enabled = enabled
        row.operator("assetsbridge.retarget_skeleton", text="Retarget & Rebind", icon='ARMATURE_DATA')


# =============================================================================
# REGISTRATION
# =============================================================================

classes = [
    BoneMappingItem,
    SkeletonRetargetSettings,
    ASSETSBRIDGE_OT_BuildBoneMapping,
    ASSETSBRIDGE_OT_ClearBoneMapping,
    ASSETSBRIDGE_OT_RetargetSkeleton,
    ASSETSBRIDGE_OT_SetMappingTarget,
    ASSETSBRIDGE_OT_ToggleAllMappings,
    ASSETSBRIDGE_UL_BoneMappingList,
    ASSETSBRIDGE_PT_SkeletonRetargetPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ab_skeleton_retarget = PointerProperty(type=SkeletonRetargetSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ab_skeleton_retarget
