/* AMVFX CEP panel logic: collects the form, calls the ExtendScript host. */
(function () {
    var cs = new CSInterface();
    var PASSES = ["source", "alpha", "depth", "normal", "basecolor",
                  "roughness", "metallic", "specular", "ao"];
    var box = document.getElementById("passes");
    PASSES.forEach(function (p) {
        var lab = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox"; cb.value = p; cb.checked = true;
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + p));
        box.appendChild(lab);
    });
    function val(id) { return document.getElementById(id).value.trim(); }
    function status(t) { document.getElementById("status").textContent = t; }
    function chosenPasses() {
        return Array.prototype.slice.call(box.querySelectorAll("input:checked"))
            .map(function (cb) { return cb.value; }).join(",");
    }
    // Frame range from the selected layer's in/out points (-1/-1 =
    // whole file). Set by "Use Selected Clip", cleared when the user
    // types or picks a file by hand.
    var selStart = -1, selEnd = -1;
    document.getElementById("src").addEventListener("change", function () {
        selStart = -1; selEnd = -1;
    });
    document.getElementById("sel").addEventListener("click", function () {
        status("Resolving the selected timeline clip...");
        cs.evalScript("amvfxSelectedSource()", function (res) {
            if (res.indexOf("OK:") === 0) {
                var parts = res.slice(3).split("|");
                document.getElementById("src").value = parts[0];
                selStart = parseInt(parts[1] || "-1", 10);
                selEnd = parseInt(parts[2] || "-1", 10);
                status("Source set from the timeline selection." +
                    (selStart >= 0
                        ? " Frames " + selStart + "-" + (selEnd - 1) + "."
                        : ""));
            } else {
                status(res.replace(/^ERROR:/, ""));
            }
        });
    });
    document.getElementById("gen").addEventListener("click", function () {
        if (!val("src")) { status("Pick a source file first."); return; }
        var args = [val("amvfxDir"), val("py"), val("src"),
                    val("profile"), chosenPasses(), selStart, selEnd].join("|");
        status("Generating... (AE is paused)");
        cs.evalScript('amvfxGenerate("' + args.replace(/"/g, '') + '")',
            function (res) { status(res); });
    });
    document.getElementById("imp").addEventListener("click", function () {
        if (!val("src")) { status("Pick a source file first."); return; }
        status("Importing...");
        cs.evalScript('amvfxImport("' + val("src").replace(/"/g, '') + '")',
            function (res) { status(res); });
    });
})();
