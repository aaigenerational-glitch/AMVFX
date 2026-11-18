/*
 * AMVFX CEP extension - host (ExtendScript) side.
 * Called from the panel via CSInterface.evalScript.
 * The panel passes pipe-delimited arguments to keep the bridge
 * simple: amvfxGenerate("amvfxDir|python|src|profile|pass1,pass2,...|
 * startFrame|endFrame") where the frame range (from the selected
 * layer's in/out points, -1/-1 = whole file) is optional.
 */

/* Frame range of a layer's in/out points, in source-frame indices
 * (end exclusive). inPoint/outPoint are composition time in seconds;
 * source time is (compTime - startTime) / stretch. Returns
 * {start: -1, end: -1} for the whole file when the range is unmappable
 * (still images, reversed layers, zero stretch). */
function layerFrameRange(layer, comp) {
    var fps = comp.frameRate || 30;
    var stretch = (layer.stretch || 100) / 100;
    if (!stretch) return {start: -1, end: -1};
    function toFrame(sec) {
        return Math.max(0, Math.round(sec * fps));
    }
    var start = toFrame((layer.inPoint - layer.startTime) / stretch);
    var end = toFrame((layer.outPoint - layer.startTime) / stretch);
    if (end <= start) return {start: -1, end: -1};
    return {start: start, end: end};
}

/* Resolve the layer selected in the active comp's timeline to a
 * source file: footage -> its file on disk; a composition (precomp)
 * is rendered to a temp movie via the render queue (whole queue
 * renders; H.264 template when available, else Lossless).
 * Returns "OK:<path>|<startFrame>|<endFrame>" (frames -1/-1 = whole
 * file) or "ERROR:<reason>". */
function amvfxSelectedSource() {
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem))
        return "ERROR:Open a composition and select a layer in the timeline first.";
    var sel = comp.selectedLayers;
    if (!sel || sel.length === 0)
        return "ERROR:No layer is selected in the active composition.";
    var layer = sel[0];
    var range = layerFrameRange(layer, comp);
    var tail = "|" + range.start + "|" + range.end;
    var src = layer.source;
    if (src instanceof FootageItem) {
        if (src.file) return "OK:" + src.file.fsName + tail;
        return "ERROR:The selected layer's footage has no file on disk (generated or missing footage). Pick a file instead.";
    }
    if (src instanceof CompItem) {
        var safe = src.name.replace(/[^\w\- ]+/g, "_");
        var tmp = new File(Folder.temp.fsName + "/AMVFX_selected_" + safe + ".mp4");
        var rqItem = null;
        try {
            rqItem = app.project.renderQueue.items.add(src);
            var om = rqItem.outputModules[1];
            try { om.applyTemplate("H.264"); }
            catch (e1) {
                try { om.applyTemplate("Lossless"); } catch (e2) {}
                tmp = new File(Folder.temp.fsName + "/AMVFX_selected_" + safe + ".mov");
            }
            om.file = tmp;
            app.project.renderQueue.render();
            rqItem.remove();
            if (tmp.exists) return "OK:" + tmp.fsName + tail;
            return "ERROR:Rendering the selected composition did not produce a file.";
        } catch (e) {
            try { if (rqItem) rqItem.remove(); } catch (e3) {}
            return "ERROR:Could not render the selected composition: " + e.toString();
        }
    }
    return "ERROR:The selected layer is not footage or a composition - solids, text, shapes and cameras can't be a pass source.";
}

/* Quote a path for the shell command: strip embedded double quotes
 * (a " in a folder name would break the cmd /c quoting) and wrap the
 * rest in double quotes, so paths with spaces work. */
function q(p) { return '"' + String(p).replace(/"/g, "") + '"'; }

function amvfxOutFolder(srcPath) {
    var src = new File(srcPath);
    var base = src.name.replace(/\.[^\.]+$/, "");
    return new Folder(src.parent.fsName + "/" + base + "_amvfx");
}

// Comp name for a built pass comp: "AMVFX_<source-stem>", e.g. source
// "shot01.mp4" -> "AMVFX_shot01". (Was "AMVFX_" + the first imported
// layer's name, which produced "AMVFX_AMVFX_source".)
function amvfxCompName(fileName) {
    var base = String(fileName || "").replace(/\.[^\.]+$/, "");
    base = base.replace(/[^\w\- ]+/g, "_").replace(/^\s+|\s+$/g, "");
    if (!base) base = "passes";
    return "AMVFX_" + base;
}

function amvfxGenerate(args) {
    var p = args.split("|");
    var amvfxDir = p[0], py = p[1], src = p[2], profile = p[3], passes = p[4];
    var out = amvfxOutFolder(src);
    var isWin = ($.os.indexOf("Windows") !== -1);
    var run = q(py) + ' -m amvfx ' + q(src) + ' --out ' + q(out.fsName) +
              ' --profile ' + profile + ' --passes ' + passes;
    // Trim to the selected layer's in/out points when the client passed
    // a frame range (fields 6-7, -1/-1 = whole file).
    var startFrame = parseInt(p[5], 10), endFrame = parseInt(p[6], 10);
    if (!isNaN(startFrame) && startFrame >= 0 && !isNaN(endFrame))
        run += " --start-frame " + startFrame + " --end-frame " + endFrame;
    var cmd = isWin
        ? 'cmd /c "cd /d ' + q(amvfxDir) + ' && ' + run + '"'
        : 'cd ' + q(amvfxDir) + ' && ' + run;
    system.callSystem(cmd);
    return new File(out.fsName + "/manifest.json").exists
        ? "OK:" + out.fsName
        : "DONE_NO_MANIFEST:" + out.fsName;
}

function amvfxImport(args) {
    var src = args;
    var out = amvfxOutFolder(src);
    if (!out.exists) return "ERROR:no output folder";
    var PASSES = ["source", "alpha", "depth", "normal", "basecolor",
                  "roughness", "metallic", "specular", "ao"];
    app.beginUndoGroup("AMVFX: import passes");
    var proj = app.project, first = null, layers = [];
    for (var i = 0; i < PASSES.length; i++) {
        var name = PASSES[i], f = null, seq = false;
        var dir = new Folder(out.fsName + "/" + name);
        if (dir.exists) {
            var files = dir.getFiles("*.png");
            if (files.length) { f = files[0]; seq = files.length > 1; }
        }
        var mp4 = new File(out.fsName + "/" + name + ".mp4");
        if (!f && mp4.exists) f = mp4;
        if (!f) continue;
        var io = new ImportOptions(f);
        if (seq) io.sequence = true;
        var item = proj.importFile(io);
        item.name = "AMVFX_" + name;
        layers.push(item);
        if (!first) first = item;
    }
    if (!first) { app.endUndoGroup(); return "ERROR:no pass files"; }
    var srcFile = new File(src);
    var comp = proj.items.addComp(amvfxCompName(srcFile.name), first.width,
        first.height, first.pixelAspect, Math.max(first.duration, 1),
        first.frameRate || 30);
    for (var j = layers.length - 1; j >= 0; j--) comp.layers.add(layers[j]);
    app.endUndoGroup();
    return "OK:" + comp.name;
}
