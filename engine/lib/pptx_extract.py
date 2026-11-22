"""Extract text, images and notes from a .pptx into JSON.

Writes <out_dir>/extracted-slides.json and <out_dir>/assets/slideN_imgM.ext (only when the
file has images). Needs python-pptx.
"""
import json
import os

from .common import DeckError, ensure_outside_skill

PICTURE = 13  # MSO_SHAPE_TYPE.PICTURE


def extract(path, out="."):
    from pptx import Presentation
    prs = Presentation(str(path))
    assets = os.path.join(str(out), "assets")
    slides, n_images = [], 0
    for i, slide in enumerate(prs.slides):
        d = {"number": i + 1, "title": "", "content": [], "images": [], "notes": ""}
        for sh in slide.shapes:
            if sh.has_text_frame:
                if sh == slide.shapes.title:
                    d["title"] = sh.text
                else:
                    d["content"].append(sh.text)
            if sh.shape_type == PICTURE:
                os.makedirs(assets, exist_ok=True)  # created only when needed
                img = sh.image
                name = f"slide{i + 1}_img{len(d['images']) + 1}.{img.ext}"
                with open(os.path.join(assets, name), "wb") as f:
                    f.write(img.blob)
                d["images"].append(f"assets/{name}")
                n_images += 1
        if slide.has_notes_slide:
            d["notes"] = slide.notes_slide.notes_text_frame.text
        slides.append(d)
    return slides, n_images


def run(src, out):
    try:
        import pptx  # noqa: F401
    except ImportError:
        raise DeckError("extract-pptx needs python-pptx. Install it with: "
                        "python3 -m pip install python-pptx")
    if not src.is_file():
        raise DeckError(f"file not found: {src}")
    if src.suffix.lower() not in (".pptx", ".pptm"):
        raise DeckError(f"not a .pptx file: {src}")
    ensure_outside_skill(out, "extracted output")
    out.mkdir(parents=True, exist_ok=True)

    data, n_images = extract(src, out)
    json_path = out / "extracted-slides.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Extracted {len(data)} slide(s).")
    print(f"Wrote {json_path}")
    if n_images:
        print(f"Wrote {n_images} image(s) to {out / 'assets'}")
    print("(extracted-slides.json and assets/ are working inputs: clean them up after building the deck.)")
    for s in data:
        print(f"  {s['number']}: {s['title'] or '(no title)'}, {len(s['images'])} image(s)")
