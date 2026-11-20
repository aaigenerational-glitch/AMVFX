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

* Scene planning (camera-from-plate, ground plane, depth-layer stage):
  the add-on can also build a camera matched to the plate, a ground
  plane at the plate's bottom edge, and a 2.5D parallax stage — the
  plate split into depth bands on separate planes spaced along Z, so
  editors can preview camera moves against the shot before committing.

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
    "version": (0, 5, 0),
    "blender": (3, 6, 0),    "location": "3D Viewport > Sidebar > AMVFX",
    "description": "Build a relightable PBR plate (with optional Z-depth "
                   "displacement) from an AMVFX job folder, plus a camera "
                   "matched to the plate, a ground plane and a depth-layer "
                   "parallax stage for planning moves and light direction.",
    "category": "Material",
}

CAM_NAME = "AMVFX_Camera"
GROUND_NAME = "AMVFX_Ground"
GROUND_MAT_NAME = "AMVFX_Ground"
LAYER_PREFIX = "AMVFX_Layer"
LAYER_MAT_PREFIX = "AMVFX_LayerMat"
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
    ground_depth: FloatProperty(
        name="Ground Plane Depth",
        description="How far the ground plane extends from the plate "
                    "toward the camera (Blender units)",
        default=4.0, min=0.5, max=20.0)
    depth_layers: IntProperty(
        name="Depth Layers",
        description="How many depth bands the parallax stage splits the "
                    "plate into (2-6)",
        default=4, min=2, max=6)
    depth_spread: FloatProperty(
        name="Depth Spread",
        description="Total Z distance between the nearest and farthest "
                    "stage layers (Blender units)",
        default=1.5, min=0.2, max=5.0)


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


def build_camera(context):
    """Camera-from-plate (roadmap backlog #2): a camera matched to the
    source plate, so editors can plan moves against the shot.

    * creates (or reuses) an AMVFX_Camera and makes it the scene camera,
    * sets the render resolution to the plate's pixel size,
    * shows the source plate as the camera's background image
      (FIT frame method, full opacity, behind the scene),
    * frames the 2-unit plate plane from the camera's vertical FOV.
    """
    import math

    props = context.scene.amvfx
    job = bpy.path.abspath(props.job_dir)
    if not job or not os.path.isdir(job):
        return None, "Pick an AMVFX job folder first."

    frame_count = 1
    manifest_path = os.path.join(job, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path) as f:
                frame_count = int(json.load(f).get("frames", 1))
        except Exception:
            pass

    # plate image: prefer the per-pass movie, else the PNG sequence
    img = None
    if props.prefer_mp4:
        mp4 = os.path.join(job, "source.mp4")
        if os.path.isfile(mp4):
            img = bpy.data.images.load(mp4)
            img.source = "MOVIE"
    if img is None:
        files = _pass_files(job, "source") or _pass_files(job, "basecolor") \
            or _pass_files(job, "depth")
        if not files:
            return None, "No source plate found in the job folder."
        img = bpy.data.images.load(files[0])
        if len(files) > 1:
            img.source = "SEQUENCE"
            img.frame_duration = max(1, frame_count)
    if not img.size[0] or not img.size[1]:
        return None, "Source plate has no size - cannot match a camera."
    width, height = img.size[0], img.size[1]

    cam_data = bpy.data.cameras.get(CAM_NAME) or \
        bpy.data.cameras.new(CAM_NAME)
    cam_data.show_background_images = True
    # replace any earlier AMVFX background image on this camera
    for bg in list(cam_data.background_images):
        if bg.image is not None and bg.image.name == img.name:
            cam_data.background_images.remove(bg)
    bg = cam_data.background_images.new()
    bg.image = img
    bg.frame_method = "FIT"
    bg.alpha = 1.0
    bg.depth = "BACK"

    obj = bpy.data.objects.get(CAM_NAME)
    if obj is None:
        obj = bpy.data.objects.new(CAM_NAME, cam_data)
        context.collection.objects.link(obj)
    else:
        obj.data = cam_data
    context.scene.camera = obj

    scene = context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    # frame the plate plane (2 units tall, centred on the origin):
    # distance so the plane height fits the vertical FOV, +10% margin
    angle = cam_data.angle  # vertical field of view, radians
    dist = 1.1 / math.tan(angle / 2.0)
    obj.location = (0.0, 0.0, dist)
    obj.rotation_euler = (0.0, 0.0, 0.0)  # looks down -Z, at the plate
    cam_data.clip_end = max(100.0, dist * 10.0)
    return (obj, f"Camera from plate: {width}x{height}, "
                 f"background = {img.name}, distance {dist:.2f}.")


def build_ground_plane(context):
    """Ground plane (roadmap camera-rig track, next stone after
    camera-from-plate): a horizontal floor at the plate's bottom edge,
    so editors can stand the shot on something and judge light
    direction and contact shadows against the plate.

    * creates (or reuses) an AMVFX_Ground object,
    * width matches the plate (2 * aspect), depth from the panel prop,
    * sits at y = -1 (the plate plane is 2 units tall, centred on the
      origin) and extends from the plate toward the camera (+Z),
    * gets a simple dark, fully rough Principled material.
    """
    import math

    props = context.scene.amvfx
    plate = bpy.data.objects.get(OBJ_NAME)
    aspect = 16.0 / 9.0
    if plate is not None and plate.scale[0]:
        aspect = plate.scale[0]  # the plate's X scale is its aspect ratio
    depth = max(0.5, props.ground_depth)

    obj = bpy.data.objects.get(GROUND_NAME)
    if obj is None:
        bpy.ops.mesh.primitive_plane_add(size=2.0,
                                         location=(0.0, -1.0, depth / 2.0))
        obj = context.active_object
        obj.name = GROUND_NAME
    # -90 deg about X: the face normal points up (+Y) and the plane's
    # local Y extent runs along world Z, toward the camera.
    obj.rotation_euler = (-math.pi / 2.0, 0.0, 0.0)
    obj.location = (0.0, -1.0, depth / 2.0)
    obj.scale = (aspect, depth / 2.0, 1.0)

    mat = bpy.data.materials.get(GROUND_MAT_NAME) or \
        bpy.data.materials.new(GROUND_MAT_NAME)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1.0)
        rough = bsdf.inputs.get("Roughness")
        if rough is not None:
            rough.default_value = 1.0
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat
    return (obj, f"Ground plane: {2.0 * aspect:.2f} wide, {depth:.1f} "
                 f"deep, at the plate's bottom edge.")


def _layer_band_mask(nt, depth_node, lo, hi, feather):
    """Alpha mask for one depth band, as shader nodes.

    Ramps up from lo to lo+feather and back down from hi-feather to hi
    (two clamped Map Range nodes multiplied), so neighbouring layers
    overlap softly instead of cutting a hard line through the subject.
    Returns the Math (MULTIPLY) node whose Value output is the mask.
    """
    nodes, links = nt.nodes, nt.links
    up = nodes.new("ShaderNodeMapRange")
    up.label = "Band ramp up"
    up.clamp = True
    up.inputs["Value"].default_value = 0.0
    up.inputs["From Min"].default_value = lo
    up.inputs["From Max"].default_value = lo + feather
    up.inputs["To Min"].default_value = 0.0
    up.inputs["To Max"].default_value = 1.0
    links.new(depth_node.outputs["Color"], up.inputs["Value"])
    down = nodes.new("ShaderNodeMapRange")
    down.label = "Band ramp down"
    down.clamp = True
    down.inputs["Value"].default_value = 0.0
    down.inputs["From Min"].default_value = hi - feather
    down.inputs["From Max"].default_value = hi
    down.inputs["To Min"].default_value = 1.0
    down.inputs["To Max"].default_value = 0.0
    links.new(depth_node.outputs["Color"], down.inputs["Value"])
    mult = nodes.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    mult.label = "Band mask"
    links.new(up.outputs["Result"], mult.inputs[0])
    links.new(down.outputs["Result"], mult.inputs[1])
    return mult


def _clear_layers():
    """Remove earlier AMVFX_Layer_* objects and materials (re-run reuse)."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith(LAYER_PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mat in list(bpy.data.materials):
        if mat.name.startswith(LAYER_MAT_PREFIX):
            bpy.data.materials.remove(mat)


def build_depth_layers(context):
    """Depth-layer parallax stage (roadmap camera-rig track, next stone
    after the ground plane): split the plate into N depth bands, each
    on its own plane spaced along Z, so a camera move shows real
    parallax — the standard 2.5D photo workflow (3-5 layers, space on
    Z, rescale pushed layers by the distance ratio, animate the camera
    only).

    * each layer's material shows the source plate masked to its depth
      band (soft Map Range ramps on the depth pass, so bands overlap
      instead of cutting hard lines),
    * AMVFX depth is disparity-like (1 = near): near bands sit closer
      to the camera (+Z) and far bands behind the plate,
    * every layer is rescaled by (camera distance - z) / camera
      distance, so the framing matches the original plate — a layer
      pushed back looks the same size, it just moves slower,
    * re-running clears the old layers first (no duplicates),
    * needs the source + depth passes in the job folder (PNG sequence
      or per-pass MP4; video jobs animate with the frame).
    """
    props = context.scene.amvfx
    job = bpy.path.abspath(props.job_dir)
    if not job or not os.path.isdir(job):
        return None, "Pick an AMVFX job folder first."

    frame_count = 1
    manifest_path = os.path.join(job, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path) as f:
                frame_count = int(json.load(f).get("frames", 1))
        except Exception:
            pass

    src_img = _load_pass_image(job, "source", frame_count, props.prefer_mp4)
    depth_img = _load_pass_image(job, "depth", frame_count, props.prefer_mp4)
    if src_img is None:
        return None, "No source plate found in the job folder."
    if depth_img is None:
        return None, ("No depth pass found in the job folder — generate "
                      "the depth pass first.")
    if not src_img.size[0] or not src_img.size[1]:
        return None, "Source plate has no size - cannot build the stage."
    aspect = src_img.size[0] / float(src_img.size[1])

    # Camera distance for the framing rescale: the AMVFX camera's if it
    # exists, else the same framing distance build_camera() computes
    # for a default 50mm lens (~3.0 units for a 2-unit-tall plate).
    cam = bpy.data.objects.get(CAM_NAME)
    dist = float(cam.location.z) if cam is not None and cam.location.z > 0.5 \
        else 3.0

    n = max(2, props.depth_layers)
    spread = max(0.2, props.depth_spread)
    width = 1.0 / n
    feather = width * 0.25

    _clear_layers()
    made = []
    for i in range(n):
        # Band centre: depth 1 = near, so layer 0 is the nearest band.
        centre = 1.0 - (i + 0.5) / n
        lo, hi = centre - width / 2.0, centre + width / 2.0
        z = (centre - 0.5) * spread
        # Rescale so the layer still fills the frame from the camera:
        # nearer layers shrink, farther layers grow (distance ratio).
        factor = max(0.05, (dist - z) / dist)

        mat_name = f"{LAYER_MAT_PREFIX}_{i:02d}"
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        texcoord = nt.nodes.new("ShaderNodeTexCoord")
        texcoord.location = (-700, 0)
        src_node = nt.nodes.new("ShaderNodeTexImage")
        src_node.image = src_img
        src_node.label = "Source (original plate)"
        src_node.location = (-450, 200)
        try:
            src_node.image.colorspace_settings.name = "sRGB"
        except Exception:
            pass
        depth_node = nt.nodes.new("ShaderNodeTexImage")
        depth_node.image = depth_img
        depth_node.label = "Depth (Z)"
        depth_node.location = (-450, -200)
        try:
            depth_node.image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass
        for tex_node in (src_node, depth_node):
            nt.links.new(texcoord.outputs["Generated"],
                         tex_node.inputs["Vector"])
            if tex_node.image.source in ("SEQUENCE", "MOVIE"):
                tex_node.image_user.frame_duration = max(1, frame_count)
                tex_node.image_user.use_auto_refresh = True
        mask = _layer_band_mask(nt, depth_node, lo, hi, feather)
        mask.location = (-150, -200)
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (150, 100)
        nt.links.new(src_node.outputs["Color"],
                     bsdf.inputs["Base Color"])
        nt.links.new(mask.outputs["Value"], bsdf.inputs["Alpha"])
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (450, 100)
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        # Transparent planes: same render method as the plate material.
        for attr, val in (("blend_method", "BLEND"),
                          ("surface_render_method", "DITHERED")):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass

        obj_name = f"{LAYER_PREFIX}_{i:02d}"
        bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, 0.0, z))
        obj = context.active_object
        obj.name = obj_name
        obj.scale = (aspect * factor, factor, 1.0)
        obj.data.materials.append(mat)
        made.append(obj)
    return (made, f"Depth-layer stage: {n} layers, spread {spread:.1f}, "
                  f"camera distance {dist:.2f} (layers rescaled to hold "
                  f"the plate framing).")


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


class AMVFX_OT_camera(Operator):
    bl_idname = "amvfx.add_camera"
    bl_label = "Add Camera from Plate"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        result, msg = build_camera(context)
        if result is None:
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class AMVFX_OT_ground_plane(Operator):
    bl_idname = "amvfx.add_ground_plane"
    bl_label = "Add Ground Plane"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        result, msg = build_ground_plane(context)
        if result is None:
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class AMVFX_OT_depth_layers(Operator):
    bl_idname = "amvfx.add_depth_layers"
    bl_label = "Add Depth-Layer Stage"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        result, msg = build_depth_layers(context)
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
        plan_box = layout.box()
        plan_box.label(text="Scene Planning", icon="CAMERA_DATA")
        plan_box.operator("amvfx.add_camera", icon="CAMERA_DATA")
        plan_box.operator("amvfx.add_ground_plane", icon="MESH_PLANE")
        plan_box.prop(props, "ground_depth")
        plan_box.operator("amvfx.add_depth_layers", icon="RENDERLAYERS")
        plan_box.prop(props, "depth_layers")
        plan_box.prop(props, "depth_spread")
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


classes = (AMVFXProps, AMVFX_OT_build, AMVFX_OT_camera,
           AMVFX_OT_ground_plane, AMVFX_OT_depth_layers,
           AMVFX_OT_compositor, AMVFX_PT_panel)


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
