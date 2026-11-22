/* PowerPoint export — measurement, rasterisation, and assembly, in the browser.
 *
 * Produces the same two-layer .pptx that `deck.py export-pptx` does: a full-bleed render
 * of each slide with the editable text left out, plus one native PowerPoint text box per
 * styled run. The design is the browser's own pixels; the text stays editable.
 *
 * This file is the SINGLE SOURCE OF TRUTH for the measurement. `deck.py export-pptx` calls
 * DeckPPTX.plan() rather than carrying its own copy, so the toolbar button and the
 * command can never disagree about what the text layer should be. See docs/pptx-export.md
 * for the Chrome/PowerPoint disagreements this code corrects, and why. Do not "simplify"
 * it without reading that.
 */
(function () {
  'use strict';

  var PX_PER_PT = 2.0;                     // 1920x1080 stage -> 960x540pt slide, exactly
  var SLIDE_W_IN = 13.333, SLIDE_H_IN = 7.5;
  var EDIT_DENY = '.deck-icon,.counter-stat,.chart-bars .bar .value,' +
                  '.chart-bars .bar .label,.chart-donut,[data-noedit]';

  function px(v) { return parseFloat(v) || 0; }

  function styleOf(el) {
    var cs = getComputedStyle(el), fs = px(cs.fontSize);
    return {
      key: [cs.fontFamily, cs.fontSize, cs.fontWeight, cs.fontStyle, cs.color,
            cs.letterSpacing, cs.textTransform].join('|'),
      fontFamily: cs.fontFamily, fontSize: fs, fontWeight: cs.fontWeight,
      italic: cs.fontStyle === 'italic' || cs.fontStyle === 'oblique',
      color: cs.color, transform: cs.textTransform,
      lineHeight: cs.lineHeight === 'normal' ? fs * 1.2 : px(cs.lineHeight),
      letterSpacing: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing)
    };
  }

  function cased(t, tt) {
    if (tt === 'uppercase') return t.toUpperCase();
    if (tt === 'lowercase') return t.toLowerCase();
    if (tt === 'capitalize') return t.replace(/(^|\s)(\S)/g, function (m, a, b) { return a + b.toUpperCase(); });
    return t;
  }

  /* Characters this deck uses that the brand face cannot draw, computed at build time
     from the fonts' own cmaps (window.DeckBrand.pptxMissingGlyphs). The browser
     substitutes them silently from the CSS fallback; a PowerPoint run pinned to the brand
     font would make PowerPoint choose its own substitute instead, and left to itself it
     picks a serif face for a missing arrow. Splitting the run here lets the fallback
     family carry them.

     Measuring coverage in the browser instead (comparing advances against an absent
     family) gives false positives — two fonts can share an advance — so trust the build. */
  var MISSING = null;
  function covered(ch) {
    if (ch.charCodeAt(0) < 0x80) return true;
    if (MISSING === null) {
      MISSING = {};
      var list = (window.DeckBrand && window.DeckBrand.pptxMissingGlyphs) || [];
      for (var i = 0; i < list.length; i++) MISSING[list[i]] = 1;
    }
    return !MISSING[ch.charCodeAt(0)];
  }

  function hasDirectText(el) {
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3 && n.textContent.trim()) return true;
    }
    return false;
  }

  /* Maximal stretches of characters on one visual line sharing one computed style,
     measured where the browser drew them. Per-character rects are what make this work:
     an element is not a styling unit (an agenda <li> holds a 60px accent numeral beside
     its 30px body label), and a flex gap between two runs cannot be reproduced by
     concatenating them — so each run keeps its own rect. */
  function runsOf(el, origin, k) {
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
    var range = document.createRange(), out = [], cur = null, node;
    while ((node = walker.nextNode())) {
      var st = styleOf(node.parentElement), t = node.textContent;
      for (var i = 0; i < t.length; i++) {
        range.setStart(node, i); range.setEnd(node, i + 1);
        var r = range.getBoundingClientRect();
        if (!r.width && !r.height) continue;               // collapsed whitespace
        var cov = covered(t[i]);
        if (!(cur && cur.style.key === st.key && cur.covered === cov &&
              Math.abs(cur.top - r.top) <= 1)) {
          cur = { style: st, covered: cov, top: r.top, left: r.left, right: r.right,
                  bottom: r.bottom, text: '' };
          out.push(cur);
        }
        cur.text += t[i];
        cur.left = Math.min(cur.left, r.left); cur.right = Math.max(cur.right, r.right);
        cur.top = Math.min(cur.top, r.top);   cur.bottom = Math.max(cur.bottom, r.bottom);
      }
    }
    return out.map(function (r) {
      // k un-scales the measurement. On screen the stage is CSS-transformed to fit the
      // window, so every rect comes back scaled; the .pptx is authored in stage px.
      var o = { covered: r.covered,
                text: cased(r.text.trim(), r.style.transform),
                x: (r.left - origin.left) * k, y: (r.top - origin.top) * k,
                w: (r.right - r.left) * k, h: (r.bottom - r.top) * k };
      for (var prop in r.style) o[prop] = r.style[prop];   // not `k` — that is the scale
      return o;
    }).filter(function (r) { return r.text; });
  }

  /* Effective rotation of an element on screen, in whole degrees clockwise: every CSS
     transform up the tree composed, plus the quarter turn a vertical writing-mode adds.
     The stage's fit-to-window scale is in the chain too, but a scale has no angle. */
  function rotationOf(el) {
    var m = new DOMMatrix();
    for (var e = el; e; e = e.parentElement) {
      var tr = getComputedStyle(e).transform;
      if (tr && tr !== 'none') m = new DOMMatrix(tr).multiply(m);
    }
    var deg = Math.round(Math.atan2(m.b, m.a) * 180 / Math.PI);
    if (/^vertical/.test(getComputedStyle(el).writingMode)) deg += 90;
    return ((deg % 360) + 360) % 360;
  }

  /* A label turned a quarter turn (an axis title). Per-character rects would give one
     upright box per letter, stacked. Instead: one run in the element's UNROTATED frame,
     centred where the text sits on screen, and the box carries the rotation. PowerPoint
     rotates a shape about its centre, so the same centre puts it back where it was. */
  function rotatedRun(el, origin, k, rot) {
    var range = document.createRange();
    range.selectNodeContents(el);
    var r = range.getBoundingClientRect(), st = styleOf(el);
    var cx = (r.left + r.right) / 2 - origin.left, cy = (r.top + r.bottom) / 2 - origin.top;
    var len = r.height * k, thick = r.width * k;     // along the text, across it
    var o = { covered: true, text: cased(el.textContent.replace(/\s+/g, ' ').trim(), st.transform),
              x: cx * k - len / 2, y: cy * k - thick / 2, w: len, h: thick, rotate: rot };
    for (var prop in st) o[prop] = st[prop];
    return o.text ? [o] : [];
  }

  /* The editable-text set, defined exactly as the deck's own edit mode defines it:
     the outermost element that directly holds text, minus Deck.EDIT_DENY. */
  /* Which elements become live text. The controller owns this definition — edit mode and
     the export must never disagree — so defer to Deck.editableLeaves and keep a local
     copy only for the injected case, where `deck.py export-pptx` adds this file to a deck
     built before the export existed and no Deck class is present. */
  function leaves(content) {
    if (typeof Deck !== 'undefined' && Deck.editableLeaves) return Deck.editableLeaves(content);
    var deny = EDIT_DENY, out = [];
    Array.prototype.forEach.call(content.querySelectorAll('*'), function (el) {
      if (el.closest(deny) || !hasDirectText(el)) return;
      var p = el.parentElement;
      while (p && p !== content) {
        if (hasDirectText(p)) return;
        p = p.parentElement;
      }
      out.push(el);
    });
    return out;
  }


  function measure() {
    return Array.prototype.map.call(document.querySelectorAll('.slide'), function (slide, i) {
      var sr = slide.getBoundingClientRect();
      var k = sr.width ? 1920 / sr.width : 1;             // undo the fit-to-window scale
      var content = slide.querySelector('.slide-content');
      var items = (content ? leaves(content) : []).map(function (el) {
        el.dataset.pptxText = '1';                        // tag for the hide pass
        var rot = rotationOf(el);
        var runs = (rot === 90 || rot === 270) ? rotatedRun(el, sr, k, rot) : runsOf(el, sr, k);
        return { runs: runs, align: getComputedStyle(el).textAlign };
      }).filter(function (it) { return it.runs.length; });
      return { index: i, title: slide.dataset.title || ('Slide ' + (i + 1)), items: items };
    });
  }

  /* Kill the glyphs but keep every box, background, border and shadow the text sits in.
     Descendants too: a child span carrying its own colour is not covered by an
     !important on its parent, and would stay visible under its own text box. */
  var HIDE_CSS = '[data-pptx-text],[data-pptx-text] *{color:transparent !important;' +
                 '-webkit-text-fill-color:transparent !important;text-shadow:none !important}';

  /* Freeze every slide in its END state, the way the PDF export does.
     _pdfPrep already resolves build-steps and snaps widgets to their final values, and it
     adds body.deck-pdf-export, whose rule kills transitions and animations. That rule cannot
     reach inside the <foreignObject> — there is no <body> there — so restate it. Reveal
     effects are transitions and resolve correctly either way, but anything driven by
     @keyframes would otherwise rasterise at frame 0: half-drawn, mid-fade, weird. */
  var FREEZE_CSS = '*,*::before,*::after{transition:none !important;animation:none !important}';

  function allCss() {
    var css = '';
    for (var i = 0; i < document.styleSheets.length; i++) {
      try {
        var rules = document.styleSheets[i].cssRules;
        for (var j = 0; j < rules.length; j++) css += rules[j].cssText + '\n';
      } catch (e) { /* cross-origin sheet; decks are self-contained so this is unusual */ }
    }
    return css;
  }

  /* Rasterise one slide by serialising it into an SVG <foreignObject> and drawing that to
     a canvas. The deck is self-contained — fonts are base64 inside the CSS — so nothing
     external is fetched and the canvas stays untainted. The clone needs its whole
     ancestor chain (a themed .deck-stage, and .active/.visible on the slide) or it
     renders blank. */
  function rasterise(slide, css, scale) {
    var stage = document.getElementById('deckStage');
    var sClone = slide.cloneNode(true);
    sClone.className = 'slide active visible';
    sClone.style.cssText = 'position:static;width:1920px;height:1080px;transform:none;opacity:1';
    var stClone = document.createElement('main');
    stClone.className = 'deck-stage';
    Array.prototype.forEach.call(stage.attributes, function (a) {
      if (a.name.indexOf('data-') === 0 || a.name === 'lang') stClone.setAttribute(a.name, a.value);
    });
    if (slide.dataset.theme) stClone.setAttribute('data-theme', slide.dataset.theme);
    stClone.setAttribute('style', 'position:static;width:1920px;height:1080px;transform:none;margin:0');
    stClone.appendChild(sClone);
    var holder = document.createElement('div');
    holder.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    holder.appendChild(stClone);

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">' +
              '<foreignObject width="100%" height="100%"><style>' + css + HIDE_CSS + FREEZE_CSS + '</style>' +
              new XMLSerializer().serializeToString(holder) + '</foreignObject></svg>';
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var c = document.createElement('canvas');
        c.width = 1920 * scale; c.height = 1080 * scale;
        var ctx = c.getContext('2d');
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);
        try { resolve(c.toDataURL('image/png')); } catch (e) { reject(e); }
      };
      img.onerror = function () { reject(new Error('slide could not be rasterised')); };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    });
  }

  function rgb(css) {
    var m = css.slice(css.indexOf('(') + 1, css.lastIndexOf(')')).split(',');
    function hex(n) { var h = Math.round(parseFloat(n)).toString(16); return h.length < 2 ? '0' + h : h; }
    return (hex(m[0]) + hex(m[1]) + hex(m[2])).toUpperCase();
  }

  /* Font metrics come from the browser, which has the real face loaded: measure the
     unkerned advance of a run with a canvas using the same family/size/weight. Chrome
     kerns; PowerPoint does not, so the difference is taken out as tracking. */
  var _mctx = null, _adv = {}, _fontCache = {};
  /* Measured in stage px, like run.w — the canvas is not affected by the stage transform
     and fontSize comes from the computed style, which is also pre-transform. */
  function unkernedWidth(run) {
    if (!_mctx) _mctx = document.createElement('canvas').getContext('2d');
    _mctx.font = (run.italic ? 'italic ' : '') + run.fontWeight + ' ' + run.fontSize + 'px ' + run.fontFamily;
    _mctx.letterSpacing = '0px';                       // measure bare advances
    // A character's advance depends only on (font, char), and a deck reuses a handful
    // of styles across thousands of characters — so memoise rather than re-measure.
    var font = _mctx.font, total = 0;
    for (var i = 0; i < run.text.length; i++) {
      var key = font + '\u0000' + run.text[i];
      if (_adv[key] === undefined) _adv[key] = _mctx.measureText(run.text[i]).width;
      total += _adv[key];
    }
    return total;
  }

  function fontFor(run) {
    // Fully determined by these three, and document.fonts.check() is the costly part.
    var ck = run.fontFamily + '|' + run.fontWeight + '|' + run.covered;
    if (_fontCache[ck]) return _fontCache[ck];
    var list = run.fontFamily.split(',').map(function (x) {
      return x.trim().replace(/^['"]|['"]$/g, '');
    });
    var w = parseInt(run.fontWeight, 10) || 400;
    if (run.covered === false) {
      // The brand face has no glyph here; the browser substituted from the CSS fallback.
      // Name a font PowerPoint certainly has rather than leaving it to guess.
      // Skip the pack's own faces as well as the generics: they are precisely the fonts
      // known to lack this glyph, so falling back to one of them just moves the problem.
      var own = {};
      var cfgAll = (window.DeckBrand && window.DeckBrand.pptxFonts) || {};
      Object.keys(cfgAll).forEach(function (k) { own[cfgAll[k].name] = 1; });
      var fb = list.slice(1).filter(function (x) {
        return x && !own[x] && x !== 'system-ui' && x !== 'sans-serif' && x !== 'serif' &&
               (!document.fonts || document.fonts.check('12px "' + x + '"'));
      })[0];
      return (_fontCache[ck] = { name: fb || 'Arial', bold: w >= 600 });
    }
    // Prefer the pack's own faces, keyed by weight. Fall back to the NEAREST weight the
    // pack ships rather than to the CSS family: a stack can name a face the pack does not
    // bundle, and PowerPoint would then have nothing to render with.
    var cfg = (window.DeckBrand && window.DeckBrand.pptxFonts) || null;
    if (cfg) {
      if (cfg[w]) return (_fontCache[ck] = { name: cfg[w].name, bold: !!cfg[w].bold });
      var weights = Object.keys(cfg).map(Number).sort(function (a, b) {
        return Math.abs(a - w) - Math.abs(b - w) || a - b;
      });
      if (weights.length) {
        var c = cfg[weights[0]];
        // A 600 asking for a 700 face keeps that face's own bold flag; a 600 landing on a
        // 400 face still wants to look bold.
        return (_fontCache[ck] = { name: c.name, bold: c.bold || (w >= 600 && weights[0] < 600) });
      }
    }
    // No pack config: use the first family the browser can actually resolve.
    var avail = list.filter(function (x) {
      return x && (!document.fonts || document.fonts.check('12px "' + x + '"'));
    })[0];
    return (_fontCache[ck] = { name: avail || list[0], bold: w >= 600 });
  }

  /* The Brand pack's PowerPoint calibration (brand.json `pptxLead`), calibrated per font
     because the disagreement depends on the face's own metrics. Without it, or without a
     measured natural line height from the pack's own font files, the export applies no
     vertical correction. See docs/pptx-export.md. */
  function halfLeading(run) {
    var brand = window.DeckBrand || {};
    var c = brand.pptxLead, natural = brand.pptxNaturalLineHeight;
    if (!c || !natural) return 0;
    return c[0] * natural * run.fontSize - c[1] * run.lineHeight - c[2];
  }

  var ALIGN = { left: 'left', start: 'left', right: 'right', end: 'right',
                center: 'center', justify: 'justify' };

  /* Lay an element's runs out as PowerPoint shapes.
   *
   * Runs are per-line AND per-style, so one visual line can be several runs — a mid-line
   * size change (an agenda numeral beside its label) or a character the brand font cannot
   * draw. How they are emitted depends on how they sit:
   *
   *   - runs that touch, on one line -> one box, one paragraph, several runs. They flow,
   *     so "Trench -> splice" stays one line however the arrow is styled.
   *   - runs separated by a gap (a flex gap) -> a box each at its measured rect, because
   *     nothing in PowerPoint reproduces that gap.
   *   - one run per line, all one style -> a single box with a paragraph per line, which
   *     keeps the text reflowing when it is edited.
   */
  function planItem(it) {
    var boxes = [];
    var lines = [];                                  // group runs into visual lines
    it.runs.forEach(function (r) {
      var line = lines.filter(function (l) { return Math.abs(l.y - r.y) <= 1; })[0];
      if (!line) { line = { y: r.y, runs: [] }; lines.push(line); }
      line.runs.push(r);
    });
    lines.sort(function (a, b) { return a.y - b.y; });
    lines.forEach(function (l) { l.runs.sort(function (a, b) { return a.x - b.x; }); });

    // A line's runs flow together only if each starts where the previous ended.
    var GAP = 1.5;                                   // px of slack for rounding
    lines.forEach(function (l) {
      l.chunks = [[l.runs[0]]];
      for (var i = 1; i < l.runs.length; i++) {
        var prev = l.runs[i - 1], cur = l.runs[i];
        if (cur.x - (prev.x + prev.w) <= GAP) l.chunks[l.chunks.length - 1].push(cur);
        else l.chunks.push([cur]);
      }
    });

    var oneChunkPerLine = lines.every(function (l) { return l.chunks.length === 1; });
    // Centre/right alignment is only safe when a line is ONE run. With several runs the
    // line can carry a substituted font whose advances differ from the browser's, and
    // centring multiplies that difference into a visible shift ("Trench -> splice" moved
    // 1.8pt). Anchoring such a line at its measured left edge reproduces it regardless.
    var singleRunLines = lines.every(function (l) { return l.runs.length === 1; });
    var oneStyle = Object.keys(it.runs.reduce(function (a, r) { a[r.key] = 1; return a; }, {})).length === 1;
    // Every line a single chunk of one style: keep it as one reflowing box.
    var groups = (oneChunkPerLine && oneStyle)
      ? [lines.map(function (l) { return l.chunks[0]; })]
      : [].concat.apply([], lines.map(function (l) {
          return l.chunks.map(function (c) { return [c]; });
        }));

    groups.forEach(function (g) {                    // g: array of lines, each a run array
      var flat = [].concat.apply([], g);
      var left = Math.min.apply(null, flat.map(function (r) { return r.x; }));
      var top = Math.min.apply(null, flat.map(function (r) { return r.y; }));
      var right = Math.max.apply(null, flat.map(function (r) { return r.x + r.w; }));
      var bottom = Math.max.apply(null, flat.map(function (r) { return r.y + r.h; }));
      // Height first, THEN shift the top. The box is centre-anchored, so folding the
      // leading correction into the height instead moves the text by half of it.
      var height = Math.max(1, bottom - top);
      top += halfLeading(flat[0]);

      var texts = [];
      g.forEach(function (line, li) {
        line.forEach(function (r, ri) {
          var f = fontFor(r), spc = null, nc = r.text.length;
          if (nc > 1) {
            var raw = unkernedWidth(r);
            if (raw) {
              // CSS letter-spacing is added after every character, the last included, so
              // the measured width holds n units of it while only n-1 gaps are visible.
              var ls = r.letterSpacing;
              spc = (ls + (r.w - raw - nc * ls) / (nc - 1)) / PX_PER_PT;
            }
          }
          if (spc === null) spc = r.letterSpacing / PX_PER_PT;
          texts.push({
            text: r.text + (ri < line.length - 1 ? ' ' : ''),
            options: {
              fontFace: f.name, fontSize: r.fontSize / PX_PER_PT, bold: f.bold,
              italic: r.italic, color: rgb(r.color), charSpacing: spc,
              breakLine: ri === line.length - 1 && li < g.length - 1
            }
          });
        });
      });

      boxes.push({
        x: left / PX_PER_PT, y: top / PX_PER_PT,           // points
        // Where the browser drew the text, before the leading correction. Verification
        // needs this: comparing a PowerPoint baseline against the shifted box top would
        // measure the correction itself rather than whether it worked.
        yText: (top - halfLeading(flat[0])) / PX_PER_PT,
        fontSize: flat[0].fontSize / PX_PER_PT,
        w: Math.max(1, right - left) / PX_PER_PT, h: height / PX_PER_PT,
        align: (oneChunkPerLine && oneStyle && singleRunLines) ? (ALIGN[it.align] || 'left') : 'left',
        lineSpacing: flat[0].lineHeight / PX_PER_PT,
        rotate: flat[0].rotate || 0,
        runs: texts
      });
    });
    return boxes;
  }

  /* The whole text layer as plain data, in points, ready for any assembler. Both the
     toolbar button (PptxGenJS) and `deck.py export-pptx` (python-pptx) render this, so
     measurement AND layout live in one place. */
  function plan() {
    return measure().map(function (slide) {
      var boxes = [];
      slide.items.forEach(function (it) { boxes = boxes.concat(planItem(it)); });
      return { index: slide.index, title: slide.title, boxes: boxes };
    });
  }

  /* Build and download the .pptx. Returns {slides, boxes}. */
  async function exportPPTX(opts) {
    opts = opts || {};
    var deck = window.deck;
    if (typeof PptxGenJS !== 'function' && typeof PptxGenJS !== 'object')
      throw new Error('PptxGenJS is not loaded');

    var prepped = false;
    if (deck && deck._pdfPrep && !deck._pdfExporting) { deck._pdfPrep(); prepped = true; }
    // let webfonts settle and widgets reach their end state
    await new Promise(function (r) { setTimeout(r, 250); });
    if (document.fonts && document.fonts.ready) { try { await document.fonts.ready; } catch (e) {} }

    _adv = {}; _fontCache = {};        // a webfont may have loaded since last time
    var slides = document.querySelectorAll('.slide');
    var layout = plan();                        // tags [data-pptx-text] as a side effect
    var css = allCss();

    var pptx = new PptxGenJS();
    pptx.defineLayout({ name: 'DECK', width: SLIDE_W_IN, height: SLIDE_H_IN });
    pptx.layout = 'DECK';
    var boxes = 0;
    for (var i = 0; i < slides.length; i++) {
      var png = await rasterise(slides[i], css, opts.scale || 2);
      var s = pptx.addSlide();
      s.addImage({ data: png, x: 0, y: 0, w: SLIDE_W_IN, h: SLIDE_H_IN });
      layout[i].boxes.forEach(function (b) {
        s.addText(b.runs, { x: b.x / 72, y: b.y / 72, w: b.w / 72, h: b.h / 72,
                            margin: 0, valign: 'middle', wrap: false, autoFit: false,
                            isTextBox: true, align: b.align, lineSpacing: b.lineSpacing,
                            rotate: b.rotate });
        boxes++;
      });
      if (opts.onProgress) opts.onProgress(i + 1, slides.length);
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-pptx-text]'), function (el) {
      delete el.dataset.pptxText;
    });
    if (prepped && deck._teardownPDF) deck._teardownPDF();

    var name = (document.title || 'deck').replace(/\s+/g, '-') + '.pptx';
    await pptx.writeFile({ fileName: opts.fileName || name });
    return { slides: slides.length, boxes: boxes };
  }

  window.DeckPPTX = { measure: measure, plan: plan, rasterise: rasterise, export: exportPPTX,
                      HIDE_CSS: HIDE_CSS, allCss: allCss };
})();
