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
- **Set Unreal Export Path** - Configure the Unreal destination path for an object and optionally move it into a matching collection hierarchy
- **Reorganize to Container** - Move a mesh (and its baked textures) into the collection/container that mirrors its Unreal content path
- **Assign UE5 Skeleton** - Reuse existing skeleton on reimport instead of creating new

### Texture Tools
- **Bake PBR** - Bake a mesh's procedural/Principled materials into a UE-ready PBR texture set: `T_<asset>_D` (BaseColor, sRGB), `T_<asset>_ORM` (packed R=AO, G=Roughness, B=Metallic), `T_<asset>_N` (tangent-space normal, DirectX/green-flipped for Unreal), and `T_<asset>_E` (emissive). Auto re-unwraps degenerate UVs (Smart UV Project), can consolidate to a single material, and writes a `textures` manifest block into `from-blender.json` targeting the `M_ORM` master material.
- **Generate UCX** - Create a convex-hull `UCX_<name>` collision mesh for a static mesh so Unreal imports per-asset collision

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
- **Set Export Path** - Set destination like `/Game/Assets/Wearables/Armor/SK_F_Trooper` (optionally move the object to a matching collection)
- **Reorganize to Container** - Select the object, click Reorganize to Container, and enter a `/Game/...` path; the mesh moves into the mirrored collection and any baked textures are relocated to the new `Textures` folder
- **Assign UE5 Skeleton** - Link mesh to existing skeleton: `/Game/Characters/Skeleton`

### Texture Tools
- **Bake PBR** - Select a mesh with node-based materials, click **Bake PBR**, and choose resolution/samples/margin. The bake produces the `T_<asset>_{D,ORM,N,E}.png` set in a `Textures` folder next to the exported asset and records it for export. On the next **Export Selected**, the texture set plus an `MI_<asset>` material-instance reference (driven by the `/Game/Materials/_Core/M_ORM` master) are written into `from-blender.json` for the UE plugin to import.
- **Generate UCX** - Select a static mesh and click **Generate UCX** to add a convex-hull `UCX_<name>_##` collision. If `Auto-generate convex UCX on export` is enabled in preferences, missing collisions are created automatically on export; otherwise a warning is shown when `Warn if UCX collision missing` is on.

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
| Collection hierarchy wrong | Use **Set Export Path** or **Reorganize to Container** to fix the `/Game/...` path |
| Unreal generates wrong collision | Use **Generate UCX** to author a `UCX_<name>` convex collision before export |
| Baked textures import into the wrong UE folder | Re-run **Reorganize to Container** so the `Textures` path matches the asset's `/Game/...` container |

## Documentation

Detailed documentation available in [Docs](./Docs/):
- **[Docs Index](./Docs/README.md)** - Documentation table of contents
- **[MeshTools](./Docs/Meshtools.md)** - Split to New Mesh, Set Unreal Export Path, Reorganize to Container, Assign UE5 Skeleton
- **[Texture Tools](./Docs/TextureTools.md)** - PBR bake pipeline (BaseColor/ORM/Normal/Emissive), ORM channel packing, the `from-blender.json` textures block
- **[Collision](./Docs/Collision.md)** - UCX collision pre-check and Generate UCX

## Support

If you find this project useful, consider supporting development:

☕ **[Buy me a coffee](https://buymeacoffee.com/nitecon)**

## License

This project is open source under the GPL license.

---

**Made with ❤️ by [Nitecon Studios LLC](https://github.com/nitecon)**
