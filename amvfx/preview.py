"""Per-pass preview zoom: pick which gallery preview to show full-size.

The Gradio Gallery already enlarges a thumbnail in a lightbox when
clicked (``allow_preview`` defaults to True), but that view is transient.
AMVFX also keeps a persistent full-size viewer under the gallery so an
editor can inspect one pass at full resolution before downloading the
ZIP. This module is the testable core of that viewer: given the
gallery's current value — a list of ``(path, caption)`` tuples — and
the index Gradio's ``SelectData`` reports, it returns the image to show
and a label for it. Pure stdlib, no Gradio import, so the tests run
anywhere.
"""


def select_preview(previews, index):
    """Return ``(image_path, label)`` for the preview at ``index``.

    ``previews`` is the Gallery value: a list of ``(path, caption)``
    tuples (caption may be ``None``). Out-of-range, missing or empty
    input returns ``(None, "No preview selected")`` instead of raising,
    so a stray click can never break the app.
    """
    if not previews:
        return None, "No preview selected"
    try:
        i = int(index)
    except (TypeError, ValueError):
        return None, "No preview selected"
    if i < 0 or i >= len(previews):
        return None, "No preview selected"
    item = previews[i]
    if isinstance(item, (list, tuple)):
        path = item[0] if len(item) > 0 else None
        caption = item[1] if len(item) > 1 else None
    else:
        path, caption = item, None
    if not path:
        return None, "No preview selected"
    label = caption or "Pass preview"
    return path, label
