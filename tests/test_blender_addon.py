"""Headless verification of the AMVFX Blender Export add-on.

Run:  AMVFX_JOB_DIR=<job> blender -b --factory-startup -P tests/test_blender_addon.py
Requires an AMVFX job folder (lite profile is enough) and Blender 3.6-4.x.
Verified passing on Blender 4.0.2 (2026-10-30).
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

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get("TMPDIR", "/tmp"), "amvfx_blender_test.blend"))
print("AMVFX BLENDER ADDON TEST: ALL PASS")
