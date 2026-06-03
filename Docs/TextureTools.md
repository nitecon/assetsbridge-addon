[← Back to Docs Index](./README.md)

# Texture Tools

## Table of Contents

- [Bake PBR Texture Set](#bake-pbr-texture-set)
- [Output Textures](#output-textures)
- [ORM Channel Packing](#orm-channel-packing)
- [Material Consolidation](#material-consolidation)
- [from-blender.json Textures Block](#from-blenderjson-textures-block)
- [Preferences](#preferences)

Documentation for the AssetsBridge PBR bake pipeline, which converts procedural Blender materials into a Unreal-ready texture set.

# Bake PBR Texture Set

**Operator:** `assetsbridge.bake_pbr`

Bakes the active mesh's Principled/procedural materials into a single Unreal Engine PBR texture set, ready to be imported by the UE plugin as a Material Instance of the project master material (`/Game/Materials/_Core/M_ORM`).

Baking requires the **Cycles** render engine (EEVEE cannot bake), so the addon temporarily switches the scene to Cycles for the duration of the bake and restores the previous engine and Cycles settings afterwards.

## Usage

1. Select a mesh object that has node-based materials and make it active
2. Click **Bake PBR** in the **Texture Tools** section of the AssetsBridge panel
3. Configure the bake dialog:
   - **Resolution** — Output texture size (128 up to 8k; default 2k)
   - **Samples** — Cycles samples per bake pass (default 16)
   - **Margin (px)** — Edge padding around UV islands to avoid seams (default 8)
   - **Flip Normal Green (DirectX for UE)** — Invert the normal map green channel to match Unreal's DirectX convention (default on)
   - **Bake AO** — Include an ambient-occlusion pass in the ORM red channel (default on)
   - **Bake Emissive** — Bake an emissive map (default on)
   - **Re-unwrap (Smart UV)** — Force a Smart UV Project unwrap before baking; this is applied automatically when the active UV layer is degenerate (e.g. procedural meshes whose UVs are collapsed to the origin)
   - **Consolidate to single material** — After baking, replace the mesh's material slots with one `M_<asset>` material wired from the baked textures (default on)

The bake writes textures to a `Textures` subfolder next to the asset's exported GLB. The resulting file paths are stored on the object (`AB_textures`) so the next export can reference them.

## Output Textures

For an asset named `<asset>` (the mesh short name with any `SM_`/`SK_`/`SKM_` prefix stripped), the bake produces:

| File | Map | Color Space | Notes |
|------|-----|-------------|-------|
| `T_<asset>_D.png`   | BaseColor | sRGB   | Diffuse color only |
| `T_<asset>_ORM.png` | ORM       | Linear | Packed AO / Roughness / Metallic |
| `T_<asset>_N.png`   | Normal    | Linear | Tangent-space; green flipped (DirectX) for Unreal |
| `T_<asset>_E.png`   | Emissive  | sRGB   | Only written when **Bake Emissive** is enabled |

## ORM Channel Packing

The ORM texture packs three data maps into one RGB image, matching the Unreal `M_ORM` master material convention:

- **R** = Ambient Occlusion (or 1.0 when **Bake AO** is off)
- **G** = Roughness
- **B** = Metallic

Blender has no native metallic bake pass, so the bake temporarily rewires each material's Principled **Metallic** input through an Emission shader and captures it with an `EMIT` bake, restoring the original surface links afterwards.

## Material Consolidation

When **Consolidate to single material** is enabled, the mesh's material slots are replaced with a single `M_<asset>` material built from the baked textures (BaseColor, ORM split into Roughness/Metallic, normal map, emissive). The original slot names are stashed on `AB_preBakeMaterials`. This keeps the glTF round-trip carrying a single material slot that matches the `M_ORM` instance workflow on the Unreal side.

## from-blender.json Textures Block

On the next **Export Selected**, baked assets emit a `textures` block per object into `from-blender.json`. It tells the Unreal plugin which PNGs to import, the destination content folder, the target master material, and which master-material parameter each texture drives:

- `master` — `/Game/Materials/_Core/M_ORM`
- `materialInstance` — `<content-path>/MI_<asset>`
- per-role entries (`baseColor`, `orm`, `normal`, `emissive`) with the source `file`, destination `contentPath` (the `Textures` folder), color space, and parameter name. The `orm` entry also records its channel map (`r: AO`, `g: Roughness`, `b: Metallic`) and the `normal` entry is flagged `DirectX`.

Because the look is defined by this texture set plus the material instance, glTF material export is set to `NONE` for baked assets so Unreal does not import duplicate embedded materials.

## Preferences

PBR bake defaults live under `Edit → Preferences → Add-ons → AssetsBridge`:

- **Bake Resolution** — default output resolution (default 2k)
- **Bake Samples** — Cycles samples per pass (default 16)
- **Bake Margin (px)** — island edge padding (default 8)
- **Flip Normal Green (DirectX for UE)** — DirectX normal convention (default on)

---

[↑ Back to Top](#texture-tools) | [← Back to Docs Index](./README.md)
