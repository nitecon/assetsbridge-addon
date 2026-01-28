[← Back to Docs Index](./README.md)

# MeshTools

## Table of Contents

- [Split to New Mesh](#split-to-new-mesh)
- [Set Unreal Export Path](#set-unreal-export-path)
- [Assign UE5 Skeleton](#assign-ue5-skeleton)
- [Selective Shape Key Transfer](#selective-shape-key-transfer)

Documentation for AssetsBridge mesh slicing, skeleton assignment, and selective shape key transfer tools

# Mesh Tools

Tools for slicing character meshes into wearable parts and managing UE5 skeleton references.

## Split to New Mesh

**Operator:** `assetsbridge.split_to_new_mesh`

Separates selected faces from a mesh into a new mesh object with proper Unreal export path configuration.

### Usage
1. Select a mesh object and enter **Edit Mode**
2. Select the faces you want to split off (e.g., helmet, gloves, boots)
3. Click **Split to New Mesh** in the AssetsBridge panel
4. Configure:
   - **Mesh Name**: Name for the new mesh (e.g., `SK_F_Helmet_01`)
   - **Unreal Path**: Target path in Unreal (e.g., `/Game/Wearables/Armor/Helmets`)
   - **Copy Armature**: Preserves armature modifier and vertex weights
   - **Copy Shape Keys**: Transfers shape keys to the new mesh

### Features
- Automatically creates Blender collection hierarchy matching the Unreal path
- Copies vertex groups and weights for skinned meshes
- Sets all required `AB_` metadata for export
- Removes split faces from the original mesh

## Set Unreal Export Path

**Operator:** `assetsbridge.set_unreal_export_path`

Sets the Unreal export destination path for any object and optionally moves it to a matching collection hierarchy.

### Usage
1. Select the object
2. Click **Set Export Path**
3. Enter the Unreal path (e.g., `/Game/Characters/Armor/Chest`)
4. Enable **Move to Collection** to reorganize the object in Blender

## Assign UE5 Skeleton

**Operator:** `assetsbridge.assign_ue5_skeleton`

Assigns an existing Unreal skeleton path to a mesh, allowing it to re-use a skeleton already in the Unreal project instead of creating a new one on import.

### Usage
1. Select a mesh with an armature modifier, or select an armature directly
2. Click **Assign UE5 Skeleton**
3. Enter the skeleton path (e.g., `/Game/Characters/Mannequin/Mesh/SK_Mannequin_Skeleton`)

### Notes
- The skeleton path is stored in the `AB_ue5SkeletonPath` custom property
- On export, this path is included in the JSON metadata for Unreal to consume
- Use **Clear Skeleton Reference** to remove the assignment and create a new skeleton on import

## Selective Shape Key Transfer

**Operator:** `assetsbridge.selective_transfer_shape_keys`

Transfer only selected shape keys from a source mesh to a target mesh. Useful when splitting meshes - for example, a helmet doesn't need nostril or mouth shape keys.

### Usage
1. Select the **source mesh** (with shape keys)
2. Shift-select the **target mesh** (make it active)
3. Click **Selective Transfer** in the Shape Key Tools section
4. Uncheck shape keys you don't want to transfer
5. Click OK

### Features
- Checkbox UI for selecting individual shape keys
- Select All / Deselect All buttons
- Same distance-based transfer options as the full transfer tool
---

[↑ Back to Top](#meshtools) | [← Back to Docs Index](./README.md)
