# AssetsBridge Blender Addon

**Version:** 1.1.0  
**Blender:** 5.0+  
**Unreal Engine:** 5.7+

## Installation
1. Go to the "Releases" section of this repository.
2. Download the latest version of the AssetsBridge plugin.
3. Open Blender and navigate to `Edit -> Preferences -> Add-ons`.
4. Click on the "Install" button and select the downloaded plugin file.
5. Activate the AssetsBridge plugin by checking the box next to it.

## Configuration
1. Go to `Edit -> Preferences -> Add-ons -> AssetsBridge`.
2. Browse to **any file** in your AssetsBridge exchange directory.
3. The addon will automatically use the directory containing that file.

## Bidirectional JSON System

The addon uses distinct JSON files to indicate pipeline directionality:

| Direction | File | Writer | Reader |
|-----------|------|--------|--------|
| Unreal → Blender | `from-unreal.json` | Unreal Export | Blender Import |
| Blender → Unreal | `from-blender.json` | Blender Export | Unreal Import |

### Import (from Unreal)
- Reads `from-unreal.json` from the configured bridge directory
- File must exist (exported from Unreal first)
- Creates collection hierarchy matching Unreal folder structure

### Export (to Unreal)
- Writes `from-blender.json` to the configured bridge directory
- Exports selected meshes and skeletal meshes as FBX
- Preserves world transforms for reimport

## Usage
1. **Import from Unreal:** Click "Import Objects" in the AssetsBridge panel (View3D > Toolbar > AssetsBridge)
2. **Export to Unreal:** Select objects, then click "Export Selected"

## Capabilities
- Import items from Unreal Engine exports.
- Export selected items for import in Unreal Engine.
- Ensure proper collection hierarchy in the Blender scene.
- Adjust object properties for export and import processes.
- Support for both StaticMesh (SM_) and SkeletalMesh (SKM_) assets.