# AssetsBridge Blender Addon

**Bidirectional asset bridge between Blender and Unreal Engine.**

AssetsBridge enables seamless round-trip asset workflows between Blender and Unreal Engine. Import meshes from Unreal, modify them in Blender, and send them back—preserving materials, transforms, skeleton references, and morph targets.

## Sister Project: Unreal Engine Plugin

This Blender addon works in tandem with the **AssetsBridge Unreal Engine Plugin**:

🔗 **[AssetsBridge UE Plugin](https://github.com/nitecon/AssetsBridge)**

Both components are required for the full workflow:

| Component | Purpose |
|-----------|---------|
| **UE Plugin** | Export assets to glTF, read modified assets back, manage UE-side integration |
| **This Addon** (Blender) | Import assets from Unreal, edit meshes/skeletons/shape keys, export back |

### Standalone vs. Combined Use

While each component can be used independently, the full workflow requires both:

- **Blender Addon Only:** Export meshes to FBX with Unreal-compatible settings, manage asset paths and collection hierarchies, split meshes into wearable parts
- **UE Plugin Only:** Export assets to a bridge directory for external editing
- **Both Together:** Full round-trip editing with automatic metadata preservation, skeleton references, material paths, and folder structure synchronization

## Features

### Import/Export
- **Import from Unreal** - Reads `from-unreal.json`, imports glTF files, creates collection hierarchy matching Unreal folder structure
- **Export to Unreal** - Writes `from-blender.json`, exports selected meshes as FBX with Unreal-compatible settings
- **Metadata Preservation** - Maintains object IDs, material paths, skeleton references, and world transforms
- **Collection Hierarchy** - Blender collections mirror Unreal's `/Game/...` folder structure

### Mesh Tools
- **Split to New Mesh** - Separate faces into new wearable pieces (preserves weights, shape keys)
- **Set Unreal Object Path** - Configure Unreal destination path for entire object hierarchies
- **Assign UE5 Skeleton** - Reuse existing skeleton on reimport instead of creating new

### Shape Key Tools
- **Transfer All Shape Keys** - Copy morph targets between meshes using closest-point mapping
- **Selective Transfer** - Choose specific shape keys to transfer (helmet doesn't need mouth morphs)

### Skeleton Retargeting
- **Automatic Bone Mapping** - Fuzzy matching algorithm maps bones between different skeletons
- **Manual Override** - Adjust individual bone mappings in a list UI
- **Weight Transfer** - Transfers and remaps vertex group weights to the new skeleton

## Installation

1. Download the latest `.zip` from [Releases](https://github.com/nitecon/assetsbridge-addon/releases)
2. In Blender: `Edit → Preferences → Add-ons → Install`
3. Select the downloaded `.zip` file
4. Enable "AssetsBridge" in the addon list

## Configuration

1. Go to `Edit → Preferences → Add-ons → AssetsBridge`
2. Browse to **any file** in your AssetsBridge exchange directory
3. The addon automatically uses the directory containing that file

> **Tip:** Use a shared folder that both Blender and Unreal can access. The Unreal plugin should be configured to use the same directory.

## Usage Workflow

### Unreal → Blender (Import)
1. In Unreal: Export assets using the AssetsBridge UE plugin
2. In Blender: Click **Import Objects** in the AssetsBridge panel (View3D → Toolbar → AssetsBridge)
3. Assets appear with collection hierarchy matching Unreal folder structure

### Blender → Unreal (Export)
1. Make your modifications in Blender
2. Select modified objects
3. Click **Export Selected** in the AssetsBridge panel
4. In Unreal: Use the UE plugin to import modified assets

### Mesh Tools
- **Split to New Mesh** - Select faces in Edit Mode, click Split to New Mesh, configure name and path
- **Set Unreal Object Path** - Set destination like `/Game/Assets/Wearables/Armor/SK_F_Trooper`
- **Assign UE5 Skeleton** - Link mesh to existing skeleton: `/Game/Characters/Skeleton`

## Supported Asset Types

| Type | Export | Import | Notes |
|------|--------|--------|-------|
| Static Mesh | ✅ | ✅ | Full support with materials |
| Skeletal Mesh | ✅ | ✅ | Includes skeleton and weights |
| Morph Targets | ✅ | ✅ | Shape keys preserved by name |
| Materials | ✅ | ✅ | Material slots tracked |

## Requirements

- **Blender 5.0+**
- **Unreal Engine 5.5+** (for full workflow with UE plugin)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Import file not found" | Export from Unreal first to create `from-unreal.json` |
| Objects not appearing in Unreal | Ensure the UE plugin is configured to the same bridge directory |
| Skeleton mismatch on import | Use **Assign UE5 Skeleton** to specify which skeleton to reuse |
| Collection hierarchy wrong | Use **Set Unreal Object Path** to fix the `/Game/...` path |

## Documentation

Detailed documentation available in [Docs](./Docs/):
- **[MeshTools](./Docs/Meshtools.md)** - Split to New Mesh, Set Unreal Object Path, Assign UE5 Skeleton

## Support

If you find this project useful, consider supporting development:

☕ **[Buy me a coffee](https://buymeacoffee.com/nitecon)**

## License

This project is open source under the GPL license.

---

**Made with ❤️ by [Nitecon Studios LLC](https://github.com/nitecon)**
