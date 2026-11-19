"""Headless verification of the AMVFX Blender Export add-on.

Run:  AMVFX_JOB_DIR=<job> blender -b --factory-startup -P tests/test_blender_addon.py
Requires an AMVFX job folder (lite profile is enough) and Blender 3.6-4.x.
Verified passing on Blender 4.0.2 (2026-10-30); camera checks added
2026-11-18, ground-plane checks added 2026-11-19 (not runnable on the
dev VM, which has no Blender binary - syntax-checked only).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Blender Export"))
import bpy  # noqa: E402

import amvfx_blender_export as addon  # noqa: E402

addon.register()
scene = bpy.context.scene
props = scene.amvfx
props.job_dir = os.environ.get("AMVFX_JOB_DIR", "/tmp/amvfx_job_test")
props.prefer_mp4 = False

res = bpy.ops.amvfx.build_plate()
assert "FINISHED" in res, res

mat = bpy.data.materials["AMVFX_Plate"]
group_node = None
for n in mat.node_tree.nodes:
    if n.type == "GROUP":
        group_node = n
assert group_node is not None, "no group node in material"
ng = group_node.node_tree
assert ng.name == "AMVFX_PBR", ng.name

tex = sorted(n.name for n in ng.nodes if n.type == "TEX_IMAGE")
print("TEX NODES:", tex)
assert "AMVFX_depth" in tex and "AMVFX_normal" in tex and "AMVFX_alpha" in tex

# verify key links exist inside the group
def has_link(from_name, from_sock, to_type, to_sock):
    for link in ng.links:
        if (link.from_node.name == from_name
                and link.from_socket.name == from_sock
                and link.to_node.type == to_type
                and link.to_socket.name == to_sock):
            return True
    return False

checks = {
    "normal->NormalMap": has_link("AMVFX_normal", "Color", "NORMAL_MAP", "Color"),
    "alpha->Principled": has_link("AMVFX_alpha", "Color", "BSDF_PRINCIPLED", "Alpha"),
    "depth->gate": has_link("AMVFX_depth", "Color", "MATH", "Value"),
}
print("LINKS:", checks)
assert all(checks.values()), checks

obj = bpy.data.objects["AMVFX_Plate"]
mod = obj.modifiers.get("AMVFX_Subdiv")
assert mod is not None, "subdiv modifier missing"
def disp_method(m):
    c = getattr(m, "cycles", None)
    if c is not None and hasattr(c, "displacement_method"):
        return c.displacement_method
    return getattr(m, "displacement_method", None)

print("z off: enable input =", group_node.inputs["Z-Depth Enable"].default_value,
      "| mat displacement =", disp_method(mat),
      "| subdiv viewport =", mod.show_viewport)
assert group_node.inputs["Z-Depth Enable"].default_value == 0.0
assert disp_method(mat) == "BUMP"
assert mod.show_viewport is False

# flip the panel checkbox -> update callback should sync the group
props.z_depth_enabled = True
print("z on: enable input =", group_node.inputs["Z-Depth Enable"].default_value,
      "| mat displacement =", disp_method(mat),
      "| subdiv viewport =", mod.show_viewport)
assert group_node.inputs["Z-Depth Enable"].default_value == 1.0
assert disp_method(mat) == "BOTH"
assert mod.show_viewport is True

props.z_depth_strength = 0.8
assert abs(group_node.inputs["Z-Depth Strength"].default_value - 0.8) < 1e-6

# ---- camera-from-plate (v0.4.0) ------------------------------------------
res = bpy.ops.amvfx.add_camera()
assert "FINISHED" in res, res
cam = bpy.data.objects.get("AMVFX_Camera")
assert cam is not None and cam.type == "CAMERA", "no AMVFX_Camera object"
assert bpy.context.scene.camera == cam, "scene camera not set"
rend = bpy.context.scene.render
print("CAMERA:", cam.name, "| res =", rend.resolution_x, "x",
      rend.resolution_y, "| loc =", tuple(round(v, 3) for v in cam.location))
# render resolution must match the plate aspect
src = bpy.data.images.get("source") or None
plate = None
for img in bpy.data.images:
    if img.name.startswith("frame_") or "source" in img.name.lower():
        plate = img
        break
if plate is not None and plate.size[0] and plate.size[1]:
    assert rend.resolution_x == plate.size[0], (rend.resolution_x, plate.size)
    assert rend.resolution_y == plate.size[1], (rend.resolution_y, plate.size)
    assert abs(rend.resolution_x / rend.resolution_y
               - plate.size[0] / plate.size[1]) < 1e-6
assert cam.data.show_background_images is True
bgs = [b for b in cam.data.background_images if b.image is not None]
assert bgs, "no background image on camera"
assert bgs[0].frame_method == "FIT", bgs[0].frame_method
assert bgs[0].depth == "BACK", bgs[0].depth
# camera sits on +Z looking at the plate, far enough to frame it
import math
assert cam.location.z > 1.0 / math.tan(cam.data.angle / 2.0), cam.location

# ---- ground plane (v0.5.0) ---------------------------------------------
res = bpy.ops.amvfx.add_ground_plane()
assert "FINISHED" in res, res
ground = bpy.data.objects.get("AMVFX_Ground")
assert ground is not None and ground.type == "MESH", "no AMVFX_Ground object"
# horizontal: face normal points up (+Y), i.e. -90 deg about X
assert abs(ground.rotation_euler[0] + math.pi / 2.0) < 1e-6, \
    ground.rotation_euler
# sits at the plate's bottom edge (plate is 2 units tall, centred on origin)
assert abs(ground.location.y + 1.0) < 1e-6, ground.location
# extends from the plate toward the camera (+Z)
assert ground.location.z > 0.0, ground.location
# width matches the plate aspect; depth from the panel prop
plate_obj = bpy.data.objects["AMVFX_Plate"]
assert abs(ground.scale[0] - plate_obj.scale[0]) < 1e-6, \
    (ground.scale, plate_obj.scale)
assert abs(ground.scale[1] * 2.0 - props.ground_depth) < 1e-6, ground.scale
assert ground.data.materials \
    and ground.data.materials[0].name == "AMVFX_Ground"
# re-running reuses the same object (no duplicates)
res = bpy.ops.amvfx.add_ground_plane()
assert "FINISHED" in res, res
assert len([o for o in bpy.data.objects
            if o.name == "AMVFX_Ground"]) == 1, \
    [o.name for o in bpy.data.objects if "Ground" in o.name]
print("GROUND:", ground.name, "| loc =",
      tuple(round(v, 3) for v in ground.location), "| scale =",
      tuple(round(v, 3) for v in ground.scale))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get("TMPDIR", "/tmp"), "amvfx_blender_test.blend"))
print("AMVFX BLENDER ADDON TEST: ALL PASS")
