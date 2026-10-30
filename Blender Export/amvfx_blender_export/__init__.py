"""AMVFX Blender Export add-on.

Builds a relightable plate from an AMVFX job folder (the output of
`python -m amvfx <input> --out <job_dir>`):

* a plane with the source image/video aspect, and
* an "AMVFX_PBR" shader node group that loads the source plate and every
  generated pass (PNG sequences or per-pass MP4s) and wires them into a
  Principled BSDF the way a compositor expects:

      Source/ BaseColor -> Base Color   (x AO multiply when AO exists)
      Roughness         -> Roughness
      Metallic          -> Metallic
      Specular          -> Specular IOR Level (Blender 4.x) / Specular (3.x)
      Normal            -> Normal Map node -> Normal
      Alpha             -> Alpha
      Depth             -> Displacement node -> group Displacement output

* Z-displacement from the depth pass is controlled three ways that stay
  in sync: the "Z-Displacement (Z-Depth)" checkbox in the AMVFX panel,
  and the "Z-Depth Enable / Strength / Midlevel" inputs on the AMVFX_PBR
  group node itself, inside the same shader node space as the passes.

Install: Edit > Preferences > Add-ons > Install... -> AMVFX_Blender_Export.zip
(or drop the amvfx_blender_export folder into your addons directory).
Then look for the "AMVFX" tab in the 3D Viewport sidebar (N).
"""

import json
import os

import bpy
from bpy.props import (BoolProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup

bl_info = {
    "name": "AMVFX Blender Export",
    "author": "AMVFX",
    "version": (0, 2, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Sidebar > AMVFX",
    "description": "Build a relightable PBR plate (with optional Z-depth "
                   "displacement) from an AMVFX job folder.",
    "category": "Material",
}

GROUP_NAME = "AMVFX_PBR"
MAT_NAME = "AMVFX_Plate"
OBJ_NAME = "AMVFX_Plate"

# pass name -> (colorspace, label)
PASS_STYLE = {
    "source": ("sRGB", "Source (original plate)"),
    "basecolor": ("sRGB", "Base Color"),
    "roughness": ("Non-Color", "Roughness"),
    "metallic": ("Non-Color", "Metallic"),
    "specular": ("Non-Color", "Specular F0"),
    "normal": ("Non-Color", "Normal"),
    "alpha": ("Non-Color", "Alpha"),
    "ao": ("Non-Color", "AO"),
    "depth": ("Non-Color", "Depth (Z)"),
}
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _pass_files(job, pass_name):
    d = os.path.join(job, pass_name)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith(".png"))


def _load_pass_image(job, pass_name, frame_count, prefer_mp4):
    """Load a pass as a movie clip or PNG sequence image datablock."""
    if prefer_mp4:
        mp4 = os.path.join(job, pass_name + ".mp4")
        if os.path.isfile(mp4):
            img = bpy.data.images.load(mp4)
            img.source = "MOVIE"
            return img
    files = _pass_files(job, pass_name)
    if not files:
        return None
    img = bpy.data.images.load(files[0])
    if len(files) > 1:
        img.source = "SEQUENCE"
    return img


def _group_socket(ng, name, in_out, socket_type, default=None):
    """Create a node-group input/output socket (Blender 3.x and 4.x APIs)."""
    if hasattr(ng, "interface"):  # Blender 4.0+
        sock = ng.interface.new_socket(name=name, in_out=in_out,
                                       socket_type=socket_type)
        if default is not None:
            try:
                sock.default_value = default
            except Exception:
                pass
        return sock
    coll = ng.inputs if in_out == "INPUT" else ng.outputs
    sock = coll.new(socket_type, name)
    if default is not None:
        try:
            sock.default_value = default
        except Exception:
            pass
    return sock


def _set_displacement_method(mat, enabled):
    """Displacement method lives on Material in <=3.x and on
    Material.cycles in 4.x - set whichever exists."""
    value = "BOTH" if enabled else "BUMP"
    cycles = getattr(mat, "cycles", None)
    if cycles is not None and hasattr(cycles, "displacement_method"):
        try:
            cycles.displacement_method = value
            return
        except Exception:
            pass
    if hasattr(mat, "displacement_method"):
        try:
            mat.displacement_method = value
        except Exception:
            pass


def _find_group_node(mat):
    if not mat or not mat.use_nodes:
        return None
    for node in mat.node_tree.nodes:
        if node.type == "GROUP" and node.node_tree and \
                node.node_tree.name == GROUP_NAME:
            return node
    return None


def _sync_from_props(context):
    """Push the panel props into the built group node's inputs."""
    props = context.scene.amvfx
    mat = bpy.data.materials.get(MAT_NAME)
    gnode = _find_group_node(mat)
    if gnode:
        def set_in(name, value):
            sock = gnode.inputs.get(name)
            if sock:
                sock.default_value = value
        set_in("Z-Depth Enable", 1.0 if props.z_depth_enabled else 0.0)
        set_in("Z-Depth Strength", props.z_depth_strength)
        set_in("Z-Depth Midlevel", props.z_depth_midlevel)
        set_in("Normal Strength", props.normal_strength)
    if mat:
        _set_displacement_method(mat, props.z_depth_enabled)
    obj = bpy.data.objects.get(OBJ_NAME)
    if obj:
        mod = obj.modifiers.get("AMVFX_Subdiv")
        if mod:
            mod.levels = props.subdiv_levels
            mod.render_levels = props.subdiv_levels
            mod.show_viewport = props.z_depth_enabled
            mod.show_render = props.z_depth_enabled


def _on_zdepth_toggle(self, context):
    _sync_from_props(context)


def _on_prop_change(self, context):
    _sync_from_props(context)


# --------------------------------------------------------------------------
# properties
# --------------------------------------------------------------------------

class AMVFXProps(PropertyGroup):
    job_dir: StringProperty(
        name="AMVFX Job Folder",
        description="Folder produced by an AMVFX run (contains manifest.json "
                    "and one subfolder per pass)",
        subtype="DIR_PATH")
    prefer_mp4: BoolProperty(
        name="Use per-pass MP4s (video jobs)",
        description="Load the <pass>.mp4 movie clips instead of PNG sequences",
        default=True)
    z_depth_enabled: BoolProperty(
        name="Z-Displacement (Z-Depth)",
        description="Displace the plate geometry using the depth pass",
        default=False, update=_on_zdepth_toggle)
    z_depth_strength: FloatProperty(
        name="Z-Depth Strength",
        description="Displacement scale for the depth pass",
        default=0.35, min=0.0, max=5.0, update=_on_prop_change)
    z_depth_midlevel: FloatProperty(
        name="Z-Depth Midlevel",
        description="Depth value treated as zero displacement",
        default=0.5, min=0.0, max=1.0, update=_on_prop_change)
    normal_strength: FloatProperty(
        name="Normal Strength",
        default=1.0, min=0.0, max=5.0, update=_on_prop_change)
    subdiv_levels: IntProperty(
        name="Subdivision Levels (for displacement)",
        description="Subdivision applied to the plate so displacement has "
                    "geometry to push. Only used when Z-Depth is enabled",
        default=5, min=0, max=8, update=_on_prop_change)


# --------------------------------------------------------------------------
# node graph construction
# --------------------------------------------------------------------------

def build_group(job, frame_count, props):
    """Create (or replace) the AMVFX_PBR node group for a job folder."""
    old = bpy.data.node_groups.get(GROUP_NAME)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")

    _group_socket(ng, "Z-Depth Enable", "INPUT", "NodeSocketFloat", 0.0)
    _group_socket(ng, "Z-Depth Strength", "INPUT", "NodeSocketFloat",
                  props.z_depth_strength)
    _group_socket(ng, "Z-Depth Midlevel", "INPUT", "NodeSocketFloat",
                  props.z_depth_midlevel)
    _group_socket(ng, "Normal Strength", "INPUT", "NodeSocketFloat",
                  props.normal_strength)
    _group_socket(ng, "Surface", "OUTPUT", "NodeSocketShader")
    _group_socket(ng, "Displacement", "OUTPUT", "NodeSocketVector")

    nodes, links = ng.nodes, ng.links
    gin = nodes.new("NodeGroupInput")
    gin.location = (-1050, 0)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (650, 0)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (350, 120)
    links.new(bsdf.outputs["BSDF"], gout.inputs["Surface"])

    # Texture Coordinate (Generated) so sequences/movies map to the plane UVs
    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-1050, -450)

    y = 420
    tex_nodes = {}
    for pass_name in ("source", "basecolor", "roughness", "metallic",
                      "specular", "normal", "alpha", "ao", "depth"):
        img = _load_pass_image(job, pass_name, frame_count, props.prefer_mp4)
        if img is None:
            continue
        colorspace, label = PASS_STYLE[pass_name]
        try:
            img.colorspace_settings.name = colorspace
        except Exception:
            pass
        node = nodes.new("ShaderNodeTexImage")
        node.image = img
        node.label = label
        node.name = "AMVFX_" + pass_name
        node.location = (-820, y)
        if img.source in ("SEQUENCE", "MOVIE"):
            node.image_user.frame_duration = max(1, frame_count)
            node.image_user.use_auto_refresh = True
        links.new(texcoord.outputs["Generated"], node.inputs["Vector"])
        tex_nodes[pass_name] = node
        y -= 260

    def link(node, bsdf_input):
        sock = bsdf.inputs.get(bsdf_input)
        if sock:
            links.new(node.outputs["Color"], sock)

    # Base Color: basecolor pass, or the source plate when there is none
    color_src = tex_nodes.get("basecolor") or tex_nodes.get("source")
    if color_src is not None:
        if "ao" in tex_nodes:  # AO multiplies into the base color
            mix = nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            mix.location = (40, 330)
            links.new(color_src.outputs["Color"], mix.inputs[1])
            links.new(tex_nodes["ao"].outputs["Color"], mix.inputs[2])
            links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            link(color_src, "Base Color")
    if "roughness" in tex_nodes:
        link(tex_nodes["roughness"], "Roughness")
    if "metallic" in tex_nodes:
        link(tex_nodes["metallic"], "Metallic")
    if "specular" in tex_nodes:
        # Blender 4.x renamed the socket; AMVFX specular is an F0 map, and
        # the Principled socket wants an IOR-level scalar - use luminance.
        spec_sock = bsdf.inputs.get("Specular IOR Level") or \
            bsdf.inputs.get("Specular")
        if spec_sock:
            rgb2bw = nodes.new("ShaderNodeRGBToBW")
            rgb2bw.location = (40, -60)
            links.new(tex_nodes["specular"].outputs["Color"],
                      rgb2bw.inputs["Color"])
            links.new(rgb2bw.outputs["Val"], spec_sock)
    if "normal" in tex_nodes:
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.location = (40, -300)
        links.new(tex_nodes["normal"].outputs["Color"], nmap.inputs["Color"])
        links.new(gin.outputs["Normal Strength"], nmap.inputs["Strength"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    if "alpha" in tex_nodes:
        link(tex_nodes["alpha"], "Alpha")

    # ---- Z-depth displacement chain -------------------------------------
    # Depth -> (x Z-Depth Enable) -> Displacement node -> group output.
    # The Displacement node always exists; the Enable input (0/1) turns it
    # off without rewiring, and Strength/Midlevel stay adjustable on the
    # group node in the material tree.
    if "depth" in tex_nodes:
        gate = nodes.new("ShaderNodeMath")
        gate.operation = "MULTIPLY"
        gate.label = "Z-Depth Enable gate"
        gate.location = (40, -560)
        links.new(tex_nodes["depth"].outputs["Color"], gate.inputs[0])
        links.new(gin.outputs["Z-Depth Enable"], gate.inputs[1])

        disp = nodes.new("ShaderNodeDisplacement")
        disp.location = (350, -560)
        links.new(gate.outputs["Value"], disp.inputs["Height"])
        links.new(gin.outputs["Z-Depth Strength"], disp.inputs["Scale"])
        links.new(gin.outputs["Z-Depth Midlevel"], disp.inputs["Midlevel"])
        links.new(disp.outputs["Displacement"], gout.inputs["Displacement"])
    return ng


def build_plate(context):
    props = context.scene.amvfx
    job = bpy.path.abspath(props.job_dir)
    if not job or not os.path.isdir(job):
        return None, "Pick an AMVFX job folder first."

    frame_count = 1
    passes = []
    manifest_path = os.path.join(job, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            frame_count = int(manifest.get("frames", 1))
            passes = manifest.get("passes", [])
        except Exception:
            pass
    if not passes:
        passes = [d for d in os.listdir(job)
                  if os.path.isdir(os.path.join(job, d))]
    if frame_count <= 1:
        files = _pass_files(job, "source") or _pass_files(job, "depth")
        frame_count = max(1, len(files))

    ng = build_group(job, frame_count, props)

    # material: group node -> material output (surface + displacement)
    mat = bpy.data.materials.get(MAT_NAME) or \
        bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    gnode = nt.nodes.new("ShaderNodeGroup")
    gnode.node_tree = ng
    gnode.label = "AMVFX passes"
    gnode.location = (-200, 100)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (150, 100)
    nt.links.new(gnode.outputs["Surface"], out.inputs["Surface"])
    if "Displacement" in gnode.outputs:
        nt.links.new(gnode.outputs["Displacement"], out.inputs["Displacement"])
    _set_displacement_method(mat, props.z_depth_enabled)
    if "alpha" in passes:  # transparent plate where alpha exists
        for attr, val in (("blend_method", "BLEND"),
                          ("surface_render_method", "DITHERED")):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass

    # plate object with the source aspect ratio
    src_img = None
    for cand in ("source", "basecolor", "depth"):
        files = _pass_files(job, cand)
        if files:
            src_img = bpy.data.images.load(files[0])
            break
    aspect = 16.0 / 9.0
    if src_img and src_img.size[1]:
        aspect = src_img.size[0] / float(src_img.size[1])

    obj = bpy.data.objects.get(OBJ_NAME)
    if obj is None:
        bpy.ops.mesh.primitive_plane_add(size=2.0,
                                         location=(0.0, 0.0, 0.0))
        obj = context.active_object
        obj.name = OBJ_NAME
    obj.scale = (aspect, 1.0, 1.0)
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat

    mod = obj.modifiers.get("AMVFX_Subdiv")
    if mod is None:
        mod = obj.modifiers.new("AMVFX_Subdiv", "SUBSURF")
    mod.levels = props.subdiv_levels
    mod.render_levels = props.subdiv_levels
    mod.show_viewport = props.z_depth_enabled
    mod.show_render = props.z_depth_enabled

    _sync_from_props(context)
    return (obj, f"Built AMVFX plate: {len(passes)} passes "
                 f"({', '.join(passes) if passes else 'none found'}), "
                 f"{frame_count} frame(s), Z-Depth "
                 f"{'ON' if props.z_depth_enabled else 'off'}.")


# --------------------------------------------------------------------------
# operators + panel
# --------------------------------------------------------------------------

class AMVFX_OT_build(Operator):
    bl_idname = "amvfx.build_plate"
    bl_label = "Build AMVFX Plate"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        result, msg = build_plate(context)
        if result is None:
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class AMVFX_OT_compositor(Operator):
    bl_idname = "amvfx.add_exr_compositor"
    bl_label = "Add Multi-Layer EXR to Compositor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        job = bpy.path.abspath(context.scene.amvfx.job_dir)
        exr_dir = os.path.join(job, "exr")
        files = []
        if os.path.isdir(exr_dir):
            files = sorted(f for f in os.listdir(exr_dir)
                           if f.lower().endswith(".exr"))
        if not files:
            self.report({"ERROR"}, "No EXR sequence in <job>/exr.")
            return {"CANCELLED"}
        scene = context.scene
        scene.use_nodes = True
        node = scene.node_tree.nodes.new("CompositorNodeImage")
        node.image = bpy.data.images.load(os.path.join(exr_dir, files[0]))
        if len(files) > 1:
            node.image.source = "SEQUENCE"
            node.frame_duration = len(files)
        node.label = "AMVFX Passes (multi-layer EXR)"
        self.report({"INFO"}, f"EXR sequence added ({len(files)} frames).")
        return {"FINISHED"}


class AMVFX_PT_panel(Panel):
    bl_label = "AMVFX Blender Export"
    bl_idname = "AMVFX_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AMVFX"

    def draw(self, context):
        layout = self.layout
        props = context.scene.amvfx
        layout.prop(props, "job_dir")
        layout.prop(props, "prefer_mp4")
        layout.operator("amvfx.build_plate", icon="MATERIAL")
        box = layout.box()
        box.label(text="Z-Depth Displacement", icon="MOD_DISPLACE")
        box.prop(props, "z_depth_enabled")
        col = box.column()
        col.enabled = props.z_depth_enabled
        col.prop(props, "z_depth_strength")
        col.prop(props, "z_depth_midlevel")
        col.prop(props, "subdiv_levels")
        layout.prop(props, "normal_strength")
        layout.operator("amvfx.add_exr_compositor", icon="NODE_COMPOSITING")
        layout.label(text="Tip: the same Z-Depth controls also live on")
        layout.label(text="the AMVFX_PBR group node in the Shader Editor.")


classes = (AMVFXProps, AMVFX_OT_build, AMVFX_OT_compositor, AMVFX_PT_panel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.amvfx = PointerProperty(type=AMVFXProps)


def unregister():
    del bpy.types.Scene.amvfx
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
