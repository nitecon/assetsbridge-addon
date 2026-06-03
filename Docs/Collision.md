[← Back to Docs Index](./README.md)

# Collision

## Table of Contents

- [Generate UCX Collision](#generate-ucx-collision)
- [Pre-Export Collision Check](#pre-export-collision-check)
- [Preferences](#preferences)

Documentation for AssetsBridge UCX collision authoring. Unreal Engine imports a collision mesh named `UCX_<MeshName>` (optionally suffixed `_##`) alongside a static mesh; these tools detect and generate such meshes.

# Generate UCX Collision

**Operator:** `assetsbridge.generate_ucx`

Generates a convex-hull `UCX_<name>_##` collision mesh for the active static mesh.

## Usage

1. Select a static mesh and make it active
2. Click **Generate UCX** in the **Texture Tools** section of the AssetsBridge panel

## Behavior

- The collision name matches what Unreal expects: `UCX_<shortName>_<NN>`, where `<shortName>` is the asset's GLB short name (prefix kept) and `NN` is the next free index (e.g. `UCX_SM_CreditChip_01`)
- The collision is a convex hull of the source mesh, linked into the same collections, with its materials cleared and styled as a blue wireframe that is hidden from render (matching the importer's UCX styling)
- If a `UCX_<name>` collision already exists for the mesh, the operator reports it and makes no change

## Pre-Export Collision Check

When exporting (**Export Selected**), AssetsBridge checks each **static mesh** export root for a matching `UCX_` collision:

- If `Auto-generate convex UCX on export` is enabled, a convex-hull UCX is created automatically for any static mesh missing one
- Otherwise, if `Warn if UCX collision missing` is enabled, a warning lists the meshes without collision (so Unreal would fall back to auto-generated collision unless a `UCX_` mesh exists)

## Preferences

Collision behavior is controlled under `Edit → Preferences → Add-ons → AssetsBridge`:

- **Warn if UCX collision missing** — warn on export when a static mesh has no `UCX_` collision (default on)
- **Auto-generate convex UCX on export** — automatically create a convex-hull UCX when one is missing (default off)

---

[↑ Back to Top](#collision) | [← Back to Docs Index](./README.md)
