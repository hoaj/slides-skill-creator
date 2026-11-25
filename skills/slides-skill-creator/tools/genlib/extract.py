"""Read the unambiguous brand facts in a PowerPoint template.

Theme colours and fonts, embedded font names, the slide size, the layout names, the colours the
slides use most, and the images on the masters and layouts (logo candidates, copied out). Every
value names the part of the file it came from, so the brand card can show its source.
Standard library only.
"""
import collections
import pathlib
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

from .common import GenError, write_json

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
SCHEME = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5",
          "accent6", "hlink", "folHlink")
EMU_PER_PX = 9525  # at 96 px per inch
IMAGE_TYPE = "/image"
SRGB = re.compile(rb'<a:srgbClr val="([0-9A-Fa-f]{6})"')


def _xml(zf, name):
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None
    except ET.ParseError as e:
        raise GenError(f"{name} in the .pptx is not valid XML ({e})")


def _rels(zf, part):
    """[(type, absolute target)] for a part's relationships."""
    folder, name = posixpath.split(part)
    root = _xml(zf, posixpath.join(folder, "_rels", name + ".rels"))
    if root is None:
        return []
    out = []
    for rel in root.findall("rel:Relationship", NS):
        if rel.get("TargetMode") == "External":
            continue
        target = posixpath.normpath(posixpath.join(folder, rel.get("Target", "")))
        out.append((rel.get("Type", ""), target, rel.get("Id")))
    return out


def _colour(element):
    srgb = element.find("a:srgbClr", NS)
    if srgb is not None:
        return "#" + srgb.get("val", "").upper()
    sys_clr = element.find("a:sysClr", NS)
    if sys_clr is not None and sys_clr.get("lastClr"):
        return "#" + sys_clr.get("lastClr").upper()
    return None


def _theme(zf, part):
    root = _xml(zf, part)
    if root is None:
        return None
    scheme = root.find(".//a:clrScheme", NS)
    colours = {}
    if scheme is not None:
        for key in SCHEME:
            el = scheme.find(f"a:{key}", NS)
            value = _colour(el) if el is not None else None
            if value:
                colours[key] = {"value": value, "source": f"{part} clrScheme {key}"}
    fonts = {}
    for role, tag in (("headings", "majorFont"), ("body", "minorFont")):
        latin = root.find(f".//a:fontScheme/a:{tag}/a:latin", NS)
        if latin is not None and latin.get("typeface"):
            fonts[role] = {"value": latin.get("typeface"), "source": f"{part} fontScheme {tag}"}
    return {"part": part, "name": root.get("name"),
            "colourScheme": scheme.get("name") if scheme is not None else None,
            "colours": colours, "fonts": fonts}


def facts(src, out):
    """Write <out>/pptx-facts.json and <out>/media/, and return the facts."""
    src, out = pathlib.Path(src), pathlib.Path(out)
    if not src.is_file():
        raise GenError(f"file not found: {src}")
    if src.suffix.lower() not in (".pptx", ".potx", ".pptm"):
        raise GenError(f"not a PowerPoint file (.pptx, .potx): {src}")
    try:
        zf = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise GenError(f"not a valid PowerPoint file: {src}")
    with zf:
        pres = _xml(zf, "ppt/presentation.xml")
        if pres is None:
            raise GenError(f"no ppt/presentation.xml, so this is not a PowerPoint file: {src}")
        size = pres.find("p:sldSz", NS)
        slide_size = None
        if size is not None:
            cx, cy = int(size.get("cx", 0)), int(size.get("cy", 0))
            slide_size = {"widthPx": round(cx / EMU_PER_PX), "heightPx": round(cy / EMU_PER_PX),
                          "aspect": f"{cx / cy:.3f}" if cy else None,
                          "source": "ppt/presentation.xml sldSz"}
        embedded = [f.get("typeface") for f in pres.findall("p:embeddedFontLst/p:embeddedFont/p:font", NS)
                    if f.get("typeface")]

        pres_rels = {rid: target for _, target, rid in _rels(zf, "ppt/presentation.xml")}
        masters, images, seen = [], [], {}
        for master_id in pres.findall("p:sldMasterIdLst/p:sldMasterId", NS):
            part = pres_rels.get(master_id.get(f"{{{NS['r']}}}id"))
            if not part:
                continue
            rels = _rels(zf, part)
            theme_part = next((t for typ, t, _ in rels if typ.endswith("/theme")), None)
            layouts = []
            for typ, layout_part, _ in rels:
                if not typ.endswith("/slideLayout"):
                    continue
                root = _xml(zf, layout_part)
                name = root.find("p:cSld", NS).get("name") if root is not None else None
                layouts.append({"name": name, "part": layout_part})
                _collect_images(zf, layout_part, images, seen)
            _collect_images(zf, part, images, seen)
            masters.append({"part": part, "theme": _theme(zf, theme_part) if theme_part else None,
                            "layouts": layouts})

        counts = collections.Counter()
        for name in zf.namelist():
            if re.match(r"ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$", name):
                counts.update(v.decode().upper() for v in SRGB.findall(zf.read(name)))

        if images:
            (out / "media").mkdir(parents=True, exist_ok=True)
            for image in images:
                target = out / "media" / image["file"]
                target.write_bytes(zf.read(image.pop("part")))
                image["file"] = f"media/{image['file']}"

    result = {
        "source": str(src),
        "slideSize": slide_size,
        "masters": masters,
        "embeddedFonts": embedded,
        "colourUse": [{"value": f"#{c}", "count": n, "source": "srgbClr in slides, layouts and masters"}
                      for c, n in counts.most_common(12)],
        "images": images,
        "notes": [
            "A logo must be an SVG. When an image here is only PNG, JPEG or EMF, ask for an SVG.",
            "Embedded fonts in a .pptx are not usable font files. Ask for the .woff2, .ttf or .otf files.",
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "pptx-facts.json", result)
    result["written"] = str(out / "pptx-facts.json")
    return result


def _collect_images(zf, part, images, seen):
    for typ, target, _ in _rels(zf, part):
        if not typ.endswith(IMAGE_TYPE) or target not in zf.namelist():
            continue
        if target in seen:
            seen[target]["usedBy"].append(part)
            continue
        entry = {"file": posixpath.basename(target), "part": target, "usedBy": [part],
                 "svg": target.lower().endswith(".svg")}
        seen[target] = entry
        images.append(entry)
