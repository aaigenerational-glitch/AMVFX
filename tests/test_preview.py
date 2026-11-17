"""Preview-zoom tests: selecting a gallery thumbnail resolves to the
right full-size image and label, and bad input degrades gracefully.
Run: python tests/test_preview.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from amvfx import preview  # noqa: E402

PREVIEWS = [("/tmp/a.png", "source"), ("/tmp/b.png", "alpha"),
            ("/tmp/c.png", None)]


def test_select_first_and_middle():
    assert preview.select_preview(PREVIEWS, 0) == ("/tmp/a.png", "source")
    assert preview.select_preview(PREVIEWS, 1) == ("/tmp/b.png", "alpha")
    print("PASS test_select_first_and_middle")


def test_missing_caption_falls_back_to_generic_label():
    assert preview.select_preview(PREVIEWS, 2) == ("/tmp/c.png",
                                                   "Pass preview")
    print("PASS test_missing_caption_falls_back_to_generic_label")


def test_out_of_range_and_empty_never_raise():
    assert preview.select_preview(PREVIEWS, 3) == (None,
                                                   "No preview selected")
    assert preview.select_preview(PREVIEWS, -1) == (None,
                                                    "No preview selected")
    assert preview.select_preview(PREVIEWS, "nope") == (None,
                                                        "No preview selected")
    assert preview.select_preview([], 0) == (None, "No preview selected")
    assert preview.select_preview(None, 0) == (None, "No preview selected")
    print("PASS test_out_of_range_and_empty_never_raise")


def test_bare_path_without_caption_tuple():
    assert preview.select_preview(["/tmp/x.png"], 0) == ("/tmp/x.png",
                                                        "Pass preview")
    print("PASS test_bare_path_without_caption_tuple")


if __name__ == "__main__":
    test_select_first_and_middle()
    test_missing_caption_falls_back_to_generic_label()
    test_out_of_range_and_empty_never_raise()
    test_bare_path_without_caption_tuple()
    print("test_preview: all PASS")
