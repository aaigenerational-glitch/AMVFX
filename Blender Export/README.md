# AMVFX Blender Export

A Blender add-on that turns an AMVFX job folder (the output of an AMVFX
run) into a relightable plate, with all passes wired into the correct PBR
sockets — the Blender counterpart of Beeble's PBR loader.

## Install

`AMVFX_Blender_Export.zip` → in Blender: **Edit > Preferences > Add-ons >
Install…**, pick the zip, enable **AMVFX Blender Export**. Blender 3.6+
(developed defensively for 3.6–4.x APIs). No zip? Copy the
`amvfx_blender_export/` folder into your Blender addons directory instead.

## Use

1. Generate passes with AMVFX (`python -m amvfx shot.mp4 --out job/`).
2. In the 3D Viewport sidebar (**N**) open the **AMVFX** tab.
3. Point **AMVFX Job Folder** at the job folder, choose MP4 or PNG
   sequences, hit **Build AMVFX Plate**.

You get a plane in the source's aspect ratio and an **AMVFX_PBR** node
group (on the `AMVFX_Plate` material) with everything connected:

| Pass      | Wired to                                              |
|-----------|-------------------------------------------------------|
| BaseColor | Principled **Base Color** (multiplied by AO if present; falls back to the Source plate) |
| Source    | loaded alongside (original plate texture)             |
| Roughness | Principled **Roughness**                              |
| Metallic  | Principled **Metallic**                               |
| Specular  | Principled **Specular IOR Level** (4.x) / **Specular** (3.x), via luminance |
| Normal    | **Normal Map** node → Principled **Normal**           |
| Alpha     | Principled **Alpha** (material set to transparent blend) |
| Depth     | **Displacement** node → material Displacement output  |

Sequences and per-pass MP4s auto-play in sync (`frame_duration` set from
the manifest). **Add Multi-Layer EXR to Compositor** drops the job's EXR
sequence into the compositor with every layer available as sockets.

## Z-Depth displacement

Tick **Z-Displacement (Z-Depth)** in the AMVFX panel and the depth pass
starts displacing the plate's geometry (a Subdivision modifier is added
and only enabled while Z-Depth is on; displacement method switches to
"Both"). **Z-Depth Strength** and **Z-Depth Midlevel** tune the push.

The same controls live **inside the node space**: the AMVFX_PBR group node
exposes `Z-Depth Enable`, `Z-Depth Strength`, `Z-Depth Midlevel` and
`Normal Strength` as inputs — adjust them right on the group node in the
Shader Editor without touching the panel. The depth feed passes through a
multiply "gate" by the Enable value, so flipping it never rewires the
graph. Note: true displacement renders in Cycles (Eevee supports it from
4.2 in material preview); without Z-Depth the depth pass still feeds the
Displacement output at zero height, leaving bump-style shading intact.

## Legacy loader

`../blender/amvfx_loader.py` remains as a minimal one-shot script version
(first-frame material + compositor EXR) for headless use:
`blender -b -P amvfx_loader.py -- <job_dir>`.
