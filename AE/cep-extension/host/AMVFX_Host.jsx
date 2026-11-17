/*
 * AMVFX CEP extension - host (ExtendScript) side.
 * Called from the panel via CSInterface.evalScript.
 * The panel passes JSON-ish pipe-delimited arguments to keep the bridge
 * simple: amvfxGenerate("amvfxDir|python|src|profile|pass1,pass2,...")
 */

/* Resolve the layer selected in the active comp's timeline to a
 * source file: footage -> its file on disk; a composition (precomp)
 * is rendered to a temp movie via the render queue (whole queue
 * renders; H.264 template when available, else Lossless).
 * Returns "OK:<path>" or "ERROR:<reason>". */
function amvfxSelectedSource() {
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem))
        return "ERROR:Open a composition and select a layer in the timeline first.";
    var sel = comp.selectedLayers;
    if (!sel || sel.length === 0)
        return "ERROR:No layer is selected in the active composition.";
    var layer = sel[0];
    var src = layer.source;
    if (src instanceof FootageItem) {
        if (src.file) return "OK:" + src.file.fsName;
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
            if (tmp.exists) return "OK:" + tmp.fsName;
            return "ERROR:Rendering the selected composition did not produce a file.";
        } catch (e) {
            try { if (rqItem) rqItem.remove(); } catch (e3) {}
            return "ERROR:Could not render the selected composition: " + e.toString();
        }
    }
    return "ERROR:The selected layer is not footage or a composition - solids, text, shapes and cameras can't be a pass source.";
}

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
    var run = '"' + py + '" -m amvfx "' + src + '" --out "' + out.fsName +
              '" --profile ' + profile + ' --passes ' + passes;
    var cmd = isWin
        ? 'cmd /c "cd /d "' + amvfxDir + '" && ' + run + '"'
        : 'cd "' + amvfxDir + '" && ' + run;
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
