/*
 * AMVFX CEP extension - host (ExtendScript) side.
 * Called from the panel via CSInterface.evalScript.
 * The panel passes JSON-ish pipe-delimited arguments to keep the bridge
 * simple: amvfxGenerate("amvfxDir|python|src|profile|pass1,pass2,...")
 */

function amvfxOutFolder(srcPath) {
    var src = new File(srcPath);
    var base = src.name.replace(/\.[^\.]+$/, "");
    return new Folder(src.parent.fsName + "/" + base + "_amvfx");
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
    var comp = proj.items.addComp("AMVFX_" + first.name, first.width,
        first.height, first.pixelAspect, Math.max(first.duration, 1),
        first.frameRate || 30);
    for (var j = layers.length - 1; j >= 0; j--) comp.layers.add(layers[j]);
    app.endUndoGroup();
    return "OK:" + comp.name;
}
