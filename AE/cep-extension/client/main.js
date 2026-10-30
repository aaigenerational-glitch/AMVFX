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
    document.getElementById("gen").addEventListener("click", function () {
        if (!val("src")) { status("Pick a source file first."); return; }
        var args = [val("amvfxDir"), val("py"), val("src"),
                    val("profile"), chosenPasses()].join("|");
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
