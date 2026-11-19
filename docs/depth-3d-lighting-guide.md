# Depth-map 3D lighting guide

How to turn an AMVFX depth pass into real 3D relighting — in After
Effects and in Blender. The lite profile is enough: you need the
**depth** pass (and the **normal** pass helps you place the light).

## What the depth pass is

AMVFX normalises depth **clip-wide** (see `amvfx/geometry.py`): brighter
pixels are nearer the camera, darker pixels are farther away. The same
convention as the grayscale depth maps After Effects' own 3D Channel
Extract produces (closer = brighter). If an effect wants the opposite
polarity, invert the depth layer first.

## After Effects — native route (no paid plug-ins)

1. Generate passes for the clip (lite profile: source, alpha, depth,
   normal, AO) and import the **source** and **depth** sequences.
2. **Relief with Displacement Map.** Put the depth layer above the
   source, then on the source apply Effect > Distort > Displacement
   Map, set the depth layer as the Displacement Map Layer, and dial a
   small horizontal/vertical displacement (start around 5–20). The
   picture gains parallax-style relief that follows the depth.
   Honest limit: this is a **2D distortion, not true geometry** — the
   light cannot wrap around anything, and there are no real shadows.
3. **Real light needs a 3D layer.** Make the source layer 3D, then
   Layer > New > Light and pick **Point** (omnidirectional, like a
   bare bulb) or **Spot** (directional, with spread and falloff).
   Adobe's own docs stress that lights affect **only 3D layers**, so
   the layer must be 3D before the light does anything; the Classic,
   Cinema 4D and Advanced 3D renderers all support lights.
4. **True geometry route.** The AMV community tutorial "3D Lighting
   with Depth Maps in After Effects" (amvtutorial.com, Mar 2026)
   builds **real 3D geometry from a generated depth map with MIR3**
   and then throws a point light at it that reacts physically to the
   depth — no manual masking. That is the paid-plug-in version of
   step 2; the Blender route below is the free equivalent.

## Blender — free true-geometry route (AMVFX add-on)

1. In the AMVFX panel, build the plate from the job folder, then
   enable **Z-Depth Displacement** — the depth pass now displaces
   real subdivided geometry (strength/midlevel on the panel or on the
   AMVFX_PBR group node).
2. Add a light (Area or Point) and move it off-axis: a low key from
   one side rakes across the displaced geometry and the relief reads
   immediately. Add **Add Camera from Plate** to frame the shot, and
   **Add Ground Plane** (v0.5.0) so the light has a floor to land on
   and you can judge contact shadows.
3. Render in Cycles (displacement method switches to BOTH when
   Z-Depth is on) or Eevee for a quick preview.

## Placing the light with the normal pass

The **normal** pass encodes which way each surface faces (red = X,
green = Y, blue = Z in the OpenGL convention AMVFX writes by
default). Read it before placing the key light: surfaces whose
normals point toward your planned light position will catch it,
surfaces pointing away will fall off. If a face you want lit is dark
in the normal channel that matches your light direction, move the
light — don't just raise its intensity. In Blender the same normal
pass is already wired into the AMVFX_PBR group, so the Principled
BSDF shades it for you.

## Sources

- "3D Lighting with Depth Maps in After Effects", amvtutorial.com
  tutorials listing, Mar 2, 2026 (by Avoid) — generated depth map +
  MIR3 → real 3D geometry + point light.
  https://amvtutorial.com/tutorials
- Adobe, "Create and work with 3D in After Effects" — lights affect
  only 3D layers; Point / Spot / Parallel / Ambient types.
  https://helpx.adobe.com/ph_fil/after-effects/how-to/work-in-3d.html
- Adobe, "3D depth data extraction" — 3D Channel Extract depth maps,
  Depth of Field / Fog 3D reference depth directly.
  https://helpx.adobe.com/after-effects/desktop/work-with-3d-composition/work-with-3d-scene-depth-data/3d-depth-data-extraction.html
