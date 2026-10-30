"""AMVFX -> Blender loader.

Run inside Blender's Scripting workspace (or `blender -b -P amvfx_loader.py -- <job_dir>`)
after generating passes with AMVFX. It builds:

1. A "AMVFX_Plate" material for a plane: Basecolor -> Principled Base Color,
   Roughness -> Roughness, Metallic -> Metallic, Normal -> Normal Map,
   using the pass PNG sequences (or the first frame).
2. A compositor node group that loads the multi-layer EXR sequence so all
   passes (Source, Alpha, Normal, Basecolor, Depth, Roughness, Metallic,
   Specular) are available as sockets for relighting/comp.

This mirrors the role of Beeble's PBR loader for Blender.
"""
import os
import sys

import bpy


def _job_dir():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv:
        return os.path.abspath(argv[0])
    return os.path.abspath(".")


def _first_png(job, pass_name):
    d = os.path.join(job, pass_name)
    if not os.path.isdir(d):
        return None
    files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    return os.path.join(d, files[0]) if files else None


def build_material(job):
    mat = bpy.data.materials.new("AMVFX_Plate")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    def tex(pass_name, colorspace):
        path = _first_png(job, pass_name)
        if not path:
            return None
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path)
        node.image.colorspace_settings.name = colorspace
        return node

    bc = tex("basecolor", "sRGB")
    if bc:
        nt.links.new(bc.outputs["Color"], bsdf.inputs["Base Color"])
    rough = tex("roughness", "Non-Color")
    if rough:
        nt.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    metal = tex("metallic", "Non-Color")
    if metal:
        nt.links.new(metal.outputs["Color"], bsdf.inputs["Metallic"])
    normal = tex("normal", "Non-Color")
    if normal:
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(normal.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    alpha = tex("alpha", "Non-Color")
    if alpha:
        nt.links.new(alpha.outputs["Color"], bsdf.inputs["Alpha"])
    return mat


def build_compositor(job):
    exr_dir = os.path.join(job, "exr")
    if not os.path.isdir(exr_dir):
        return None
    files = sorted(f for f in os.listdir(exr_dir) if f.endswith(".exr"))
    if not files:
        return None
    scene = bpy.context.scene
    scene.use_nodes = True
    nt = scene.node_tree
    node = nt.nodes.new("CompositorNodeImage")
    node.image = bpy.data.images.load(os.path.join(exr_dir, files[0]))
    node.label = "AMVFX Passes (multi-layer EXR)"
    return node


def main():
    job = _job_dir()
    mat = build_material(job)
    plane = bpy.data.objects.new("AMVFX_Plate", None)
    bpy.context.collection.objects.link(plane)
    mesh = bpy.data.meshes.new("AMVFX_PlateMesh")
    obj = bpy.data.objects.new("AMVFX_PlateMesh", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    build_compositor(job)
    print(f"[AMVFX] Loaded passes from {job}")


if __name__ == "__main__":
    main()
