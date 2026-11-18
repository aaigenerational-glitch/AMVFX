/*
 * AMVFX for After Effects - ScriptUI dockable panel.
 *
 * Install: copy this file to
 *   (Windows) C:\Program Files\Adobe\Adobe After Effects <ver>\Support Files\Scripts\ScriptUI Panels\
 *   (macOS)   /Applications/Adobe After Effects <ver>/Scripts/ScriptUI Panels/
 * then restart AE and open Window > AMVFX_Panel.jsx.
 *
 * What it does:
 *   1. Runs your local AMVFX install (python -m amvfx ...) on a source
 *      image/video you pick - or on the clip currently SELECTED in the
 *      timeline ("Use Selected Clip"): a footage layer resolves to its
 *      file on disk, and a composition (precomp) is rendered to a temp
 *      movie through the render queue first. The layer's in/out points
 *      are honoured: generation is trimmed to that range
 *      (--start-frame/--end-frame) instead of the whole file.
 *      AE pauses while the passes generate.
 *   2. Imports the generated passes (PNG sequences / MP4s / EXR sequence)
 *      and builds a comp with the source plate at the bottom and every
 *      pass stacked above it, named and ready for relight/comp work.
 */
(function (thisObj) {
    var PASSES = ["source", "alpha", "depth", "normal", "basecolor",
                  "roughness", "metallic", "specular", "ao"];
    var isWin = ($.os.indexOf("Windows") !== -1);

    // Quote a path for the shell command: strip embedded double quotes
    // (a " in a folder name would break the cmd /c quoting) and wrap
    // the rest in double quotes, so paths with spaces work.
    function q(p) { return '"' + String(p).replace(/"/g, "") + '"'; }

    // Comp name for a built pass comp: "AMVFX_<source-stem>", e.g.
    // source "shot01.mp4" -> "AMVFX_shot01". (Was "AMVFX_" + the first
    // imported layer's name, which produced "AMVFX_AMVFX_source".)
    function amvfxCompName(fileName) {
        var base = String(fileName || "").replace(/\.[^\.]+$/, "");
        base = base.replace(/[^\w\- ]+/g, "_").replace(/^\s+|\s+$/g, "");
        if (!base) base = "passes";
        return "AMVFX_" + base;
    }

    function buildUI(thisObj) {
        var pal = (thisObj instanceof Panel)
            ? thisObj
            : new Window("palette", "AMVFX", undefined, {resizeable: true});
        pal.orientation = "column";
        pal.alignChildren = ["fill", "top"];
        pal.spacing = 8;
        pal.margins = 10;

        pal.add("statictext", undefined, "AMVFX - VFX Passes Generator");
        var g1 = pal.add("group");
        g1.orientation = "column";
        g1.alignChildren = ["fill", "top"];
        g1.add("statictext", undefined, "AMVFX install folder:");
        var amvfxDir = g1.add("edittext", undefined,
            isWin ? "C:\\AMVFX" : "~/AMVFX");
        amvfxDir.characters = 42;
        var gPy = pal.add("group");
        gPy.add("statictext", undefined, "Python:");
        var pyCmd = gPy.add("edittext", undefined, isWin ? "py" : "python3");
        pyCmd.characters = 12;

        var g2 = pal.add("group");
        g2.add("statictext", undefined, "Source file:");
        var srcPath = g2.add("edittext", undefined, "");
        srcPath.characters = 30;
        var btnSrc = g2.add("button", undefined, "Browse...");
        btnSrc.onClick = function () {
            var f = File.openDialog("Pick an image or video");
            if (f) {
                srcPath.text = f.fsName;
                selRange = {start: -1, end: -1};  // hand-picked file: whole file
                status.text = "Source file picked (whole file).";
            }
        };
        // Frame range from the selected layer's in/out points; -1/-1
        // means "whole file" (set by "Use Selected Clip" below).
        var selRange = {start: -1, end: -1};
        var btnSel = pal.add("button", undefined,
            "Use Selected Clip (timeline selection)");
        btnSel.onClick = function () {
            var r = resolveSelectedClip();
            if (r.error) { alert(r.error); return; }
            srcPath.text = r.path;
            selRange = {start: r.startFrame, end: r.endFrame};
            status.text = "Source from timeline: " + r.label +
                (r.startFrame >= 0
                    ? " (frames " + r.startFrame + "-" + (r.endFrame - 1) + ")"
                    : " (whole file)");
        };

        var g3 = pal.add("group");
        g3.add("statictext", undefined, "Profile:");
        var profile = g3.add("dropdownlist", undefined, ["lite", "gpu"]);
        profile.selection = 0;

        var grp = pal.add("panel", undefined, "Passes");
        grp.orientation = "row";
        grp.alignChildren = "left";
        var checks = {};
        for (var i = 0; i < PASSES.length; i++) {
            checks[PASSES[i]] = grp.add("checkbox", undefined, PASSES[i]);
            checks[PASSES[i]].value = true;
        }

        var status = pal.add("statictext", undefined,
            "Ready. Generation runs locally; AE pauses meanwhile.");
        status.characters = 46;

        var btnGen = pal.add("button", undefined,
            "1) Generate Passes (local AMVFX)");
        var btnImp = pal.add("button", undefined,
            "2) Import Passes + Build Comp");

        function outFolder() {
            var src = new File(srcPath.text);
            var base = src.name.replace(/\.[^\.]+$/, "");
            return new Folder(src.parent.fsName + "/" + base + "_amvfx");
        }

        btnGen.onClick = function () {
            if (!srcPath.text) { alert("Pick a source file first."); return; }
            var chosen = [];
            for (var i = 0; i < PASSES.length; i++)
                if (checks[PASSES[i]].value) chosen.push(PASSES[i]);
            var out = outFolder();
            var cmd;
            var cd = 'cd /d ' + q(amvfxDir.text);
            var run = q(pyCmd.text) + ' -m amvfx ' + q(srcPath.text) +
                      ' --out ' + q(out.fsName) + ' --profile ' +
                      profile.selection.text + ' --passes ' +
                      chosen.join(",");
            // Trim to the selected layer's in/out points when set.
            if (selRange.start >= 0)
                run += " --start-frame " + selRange.start +
                       " --end-frame " + selRange.end;
            if (isWin) cmd = 'cmd /c "' + cd + " && " + run + '"';
            else cmd = 'cd ' + q(amvfxDir.text) + ' && ' + run;
            status.text = "Generating... (AE is paused)";
            pal.update();
            system.callSystem(cmd);
            var manifest = new File(out.fsName + "/manifest.json");
            status.text = manifest.exists
                ? "Done: " + out.fsName
                : "Finished - check output (manifest.json not found).";
        };

        btnImp.onClick = function () {
            var out = outFolder();
            if (!out.exists) { alert("No AMVFX output folder yet."); return; }
            app.beginUndoGroup("AMVFX: import passes");
            var proj = app.project;
            var first = null, layers = [];
            function importPass(name) {
                var f = null, seq = false;
                var mp4 = new File(out.fsName + "/" + name + ".mp4");
                var dir = new Folder(out.fsName + "/" + name);
                if (dir.exists) {
                    var files = dir.getFiles("*.png");
                    if (files.length) { f = files[0]; seq = files.length > 1; }
                }
                if (!f && mp4.exists) f = mp4;
                if (!f) return null;
                var io = new ImportOptions(f);
                if (seq && io.canImportAs(ImportAsType.FOOTAGE))
                    io.sequence = true;
                var item = proj.importFile(io);
                item.name = "AMVFX_" + name;
                return item;
            }
            var i, item;
            for (i = 0; i < PASSES.length; i++) {
                item = importPass(PASSES[i]);
                if (item) { layers.push(item); if (!first) first = item; }
            }
            // multi-layer EXR sequence, if present
            var exrDir = new Folder(out.fsName + "/exr");
            if (exrDir.exists) {
                var exrs = exrDir.getFiles("*.exr");
                if (exrs.length) {
                    var ioE = new ImportOptions(exrs[0]);
                    if (exrs.length > 1) ioE.sequence = true;
                    var exrItem = proj.importFile(ioE);
                    exrItem.name = "AMVFX_multilayer_EXR";
                }
            }
            if (!first) {
                alert("No pass files found in " + out.fsName);
                app.endUndoGroup();
                return;
            }
            var srcFile = new File(srcPath.text);
            var comp = proj.items.addComp(amvfxCompName(srcFile.name),
                first.width, first.height, first.pixelAspect,
                Math.max(first.duration, 1), first.frameRate || 30);
            // source at the bottom, remaining passes stacked above it
            for (i = layers.length - 1; i >= 0; i--)
                comp.layers.add(layers[i]);
            status.text = "Comp built: " + comp.name + " (" +
                          layers.length + " pass layers)";
            app.endUndoGroup();
        };

        pal.layout.resize();
        return pal;
    }

    // Frame range of a layer's in/out points, in source-frame indices
    // (end exclusive). inPoint/outPoint are composition time in seconds;
    // source time is (compTime - startTime) / stretch. Returns
    // {start: -1, end: -1} for the whole file when the range is
    // unmappable - still images, reversed layers (inPoint > outPoint),
    // or a zero stretch.
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

    // Resolve the layer selected in the active comp's timeline to a
    // source file AMVFX can process. Footage -> its file on disk.
    // Composition -> rendered to a temp movie via the render queue
    // (the whole queue renders; H.264 template when available, else
    // Lossless). Anything else -> a plain-language error.
    // Returns {path, label, startFrame, endFrame}; the frame range is
    // the layer's in/out points mapped to source frames (-1/-1 = whole
    // file).
    function resolveSelectedClip() {
        var comp = app.project.activeItem;
        if (!(comp instanceof CompItem))
            return {error: "Open a composition and select a layer in " +
                           "the timeline first."};
        var sel = comp.selectedLayers;
        if (!sel || sel.length === 0)
            return {error: "No layer is selected in the active " +
                           "composition."};
        var layer = sel[0];
        var range = layerFrameRange(layer, comp);
        var src = layer.source;
        if (src instanceof FootageItem) {
            if (src.file)
                return {path: src.file.fsName,
                        label: layer.name + " (" + src.name + ")",
                        startFrame: range.start, endFrame: range.end};
            return {error: "The selected layer's footage has no file " +
                           "on disk (generated or missing footage). " +
                           "Pick a file instead."};
        }
        if (src instanceof CompItem) {
            var safe = src.name.replace(/[^\w\- ]+/g, "_");
            var tmp = new File(Folder.temp.fsName +
                               "/AMVFX_selected_" + safe + ".mp4");
            var rqItem = null;
            try {
                rqItem = app.project.renderQueue.items.add(src);
                var om = rqItem.outputModules[1];
                try { om.applyTemplate("H.264"); }
                catch (e1) {
                    try { om.applyTemplate("Lossless"); } catch (e2) {}
                    tmp = new File(Folder.temp.fsName +
                                   "/AMVFX_selected_" + safe + ".mov");
                }
                om.file = tmp;
                app.project.renderQueue.render();
                rqItem.remove();
                if (tmp.exists)
                    return {path: tmp.fsName,
                            label: layer.name + " (rendered comp: " +
                                   src.name + ")",
                            startFrame: range.start, endFrame: range.end};
                return {error: "Rendering the selected composition " +
                               "did not produce a file."};
            } catch (e) {
                try { if (rqItem) rqItem.remove(); } catch (e3) {}
                return {error: "Could not render the selected " +
                               "composition: " + e.toString()};
            }
        }
        return {error: "The selected layer is not footage or a " +
                       "composition - solids, text, shapes and cameras " +
                       "can't be a pass source. Select a video layer " +
                       "or a precomp."};
    }

    var panel = buildUI(thisObj);
    if (panel instanceof Window) {
        panel.center();
        panel.show();
    }
})(this);
