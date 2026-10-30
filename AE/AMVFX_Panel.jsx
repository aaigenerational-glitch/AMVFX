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
 *      image/video you pick. AE pauses while the passes generate.
 *   2. Imports the generated passes (PNG sequences / MP4s / EXR sequence)
 *      and builds a comp with the source plate at the bottom and every
 *      pass stacked above it, named and ready for relight/comp work.
 */
(function (thisObj) {
    var PASSES = ["source", "alpha", "depth", "normal", "basecolor",
                  "roughness", "metallic", "specular", "ao"];
    var isWin = ($.os.indexOf("Windows") !== -1);

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
            if (f) srcPath.text = f.fsName;
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
            var cd = 'cd /d "' + amvfxDir.text + '"';
            var run = '"' + pyCmd.text + '" -m amvfx "' + srcPath.text +
                      '" --out "' + out.fsName + '" --profile ' +
                      profile.selection.text + ' --passes ' +
                      chosen.join(",");
            if (isWin) cmd = 'cmd /c "' + cd + " && " + run + '"';
            else cmd = 'cd "' + amvfxDir.text + '" && ' + run;
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
            var comp = proj.items.addComp("AMVFX_" + first.name, first.width,
                first.height, first.pixelAspect,
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

    var panel = buildUI(thisObj);
    if (panel instanceof Window) {
        panel.center();
        panel.show();
    }
})(this);
