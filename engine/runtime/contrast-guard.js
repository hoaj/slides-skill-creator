/* === CONTRAST GUARD ===
   Keeps slide text legible when a background is switched. Themes remap the semantic
   tokens (--text, --accent) automatically, but content that pins a raw palette colour
   does not adapt, so it can vanish on a new background. This guard runs whenever a theme
   is applied: it measures each text element's colour against the real colour behind it
   and, only when contrast fails, swaps in a palette colour that passes. It never invents
   a colour: it stays inside the Brand pack's palette (window.DeckBrand.guard), snapping
   neutrals to the theme's --text and demoting unreadable accents.

   Vivid accents are display colours: they tend to read on dark backgrounds but fail at
   text sizes on light ones, so on a light background an accent used as body text drops
   to --text. Deliberate low-contrast graphics (a giant hero number, say) opt out with
   data-keep-color on the element or any ancestor.

   Self-installing: include this file AFTER deck-controller.js. It wraps deck.go, the
   Background <select> and _serialize (so saved files keep their authored colours; the
   guard re-derives them on every load). */
(function () {
  'use strict';

  // The palette and theme maps come from the Brand pack's `guard` block. The build has
  // already checked that every theme has a base colour and a text colour.
  var B = window.DeckBrand.guard;
  var DEFAULT_THEME = window.DeckBrand.defaultTheme;
  var PAL = B.palette;
  var NEUTRALS = B.neutrals;
  var VIVIDS = B.vivids;
  // The lightest and darkest neutral names: the two candidates when snapping text to a
  // readable neutral for a local surface (dark text on a dark accent panel, say).
  var LIGHT = B.lightNeutral;
  var DARK = B.darkNeutral;
  // Solid base colour painted by each theme (gradient themes use their base colour).
  var THEME_BG = B.themeBg;
  // The --text colour each theme resolves to.
  var THEME_TEXT = B.themeText;

  // --- colour maths --------------------------------------------------------
  function lin(c) { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function lum(rgb) { return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]); }
  function contrast(a, b) { var la = lum(a), lb = lum(b), hi = Math.max(la, lb), lo = Math.min(la, lb); return (hi + 0.05) / (lo + 0.05); }
  function parse(str) {
    if (!str) return null;
    var m = str.match(/rgba?\(([^)]+)\)/i);
    if (!m) return null;
    var p = m[1].split(',').map(function (x) { return parseFloat(x); });
    if (p.length < 3 || p.some(isNaN)) return null;
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function over(top, bottom) { var a = top[3] == null ? 1 : top[3]; return [0, 1, 2].map(function (k) { return top[k] * a + bottom[k] * (1 - a); }); }
  function dist2(a, b) { var dr = a[0] - b[0], dg = a[1] - b[1], db = a[2] - b[2]; return dr * dr + dg * dg + db * db; }
  function hue(rgb) {
    var r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    if (d === 0) return -1; // achromatic
    var h;
    if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
    h *= 60; return h < 0 ? h + 360 : h;
  }
  function hueDist(a, b) { var ha = hue(a), hb = hue(b); if (ha < 0 || hb < 0) return 360; var d = Math.abs(ha - hb); return d > 180 ? 360 - d : d; }
  function nearestName(rgb) {
    var best = null, bd = Infinity;
    for (var n in PAL) { var d = dist2(rgb, PAL[n]); if (d < bd) { bd = d; best = n; } }
    return best;
  }

  // The real colour behind an element: composite every background layer from the
  // element up to its slide, over the opaque theme base. Handles cards/blocks/bars
  // (translucent --surface, solid colour panels) — not just the slide background.
  function effectiveBg(el, baseRgb) {
    var layers = [], n = el;
    while (n && n.nodeType === 1) {
      var bc = parse(getComputedStyle(n).backgroundColor);
      if (bc && (bc[3] == null || bc[3] > 0)) layers.push(bc);
      if (n.classList && n.classList.contains('slide')) break;
      n = n.parentElement;
    }
    var base = [baseRgb[0], baseRgb[1], baseRgb[2]];
    for (var i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  }

  // The readable neutral for THIS background. Prefer the theme's --text (coherent and
  // stays live for later theme flips) when it passes against the *local* surface; else
  // fall back to whichever of the light and dark neutral contrasts the surface. This is
  // what saves dark text sitting on a hardcoded or --accent dark panel.
  function bestNeutral(bg, themeTextRgb, target) {
    if (contrast(themeTextRgb, bg) >= target) return 'var(--text)';
    return contrast(PAL[LIGHT], bg) >= contrast(PAL[DARK], bg)
      ? rgbToHex(PAL[LIGHT]) : rgbToHex(PAL[DARK]);
  }

  // Pick a palette-faithful replacement, or null to keep the authored colour.
  function chooseColor(col, bg, isLarge, themeTextRgb) {
    var target = isLarge ? 3.0 : 4.5;
    if (contrast(col, bg) >= target) return null;            // already legible
    var name = nearestName(col);
    if (NEUTRALS.indexOf(name) !== -1) return bestNeutral(bg, themeTextRgb, target);  // neutral → readable neutral for this surface
    if (!isLarge) return bestNeutral(bg, themeTextRgb, target);                       // vivid as body text is off-brand → neutralise
    // Large vivid (a display accent / hero graphic): keep the accent if any passes,
    // choosing the closest hue so intent survives; otherwise fall back to a neutral.
    var passing = VIVIDS.filter(function (v) { return contrast(PAL[v], bg) >= 3.0; });
    if (!passing.length) return bestNeutral(bg, themeTextRgb, target);
    passing.sort(function (a, b) { return hueDist(col, PAL[a]) - hueDist(col, PAL[b]); });
    return rgbToHex(PAL[passing[0]]);
  }
  function rgbToHex(rgb) {
    return '#' + rgb.map(function (c) { var h = Math.round(c).toString(16); return h.length < 2 ? '0' + h : h; }).join('').toUpperCase();
  }

  // --- per-element guard (idempotent: always re-derives from authored colour) ---
  var SEL = 'h1,h2,h3,h4,h5,h6,p,li,span,a,b,strong,em,td,th,dt,dd,blockquote,figcaption,div,label';
  function guardEl(el, baseRgb, themeTextRgb) {
    if (el.closest('[data-keep-color]')) return;
    // restore the authored inline colour before measuring (idempotency)
    if (el.dataset.deckOriginalColor !== undefined) el.style.color = el.dataset.deckOriginalColor;
    // only elements that directly render text
    var hasText = false;
    for (var i = 0; i < el.childNodes.length; i++) {
      var c = el.childNodes[i];
      if (c.nodeType === 3 && c.nodeValue.trim()) { hasText = true; break; }
    }
    if (!hasText) { if (el.dataset.deckOriginalColor !== undefined) delete el.dataset.deckOriginalColor; return; }
    var cs = getComputedStyle(el);
    var col = parse(cs.color);
    if (!col || (col[3] != null && col[3] < 0.5)) { if (el.dataset.deckOriginalColor !== undefined) delete el.dataset.deckOriginalColor; return; }
    var fs = parseFloat(cs.fontSize) || 16;
    var bold = (parseInt(cs.fontWeight, 10) || 400) >= 600;
    var isLarge = fs >= 32 || (bold && fs >= 24);   // WCAG large-text threshold (internal 1920×1080 px)
    var bg = effectiveBg(el, baseRgb);
    var repl = chooseColor(col, bg, isLarge, themeTextRgb);
    if (repl == null) { if (el.dataset.deckOriginalColor !== undefined) delete el.dataset.deckOriginalColor; return; }
    if (el.dataset.deckOriginalColor === undefined) el.dataset.deckOriginalColor = el.style.color;  // remember authored inline ('' if none)
    el.style.color = repl;
  }

  function themeOf(slide, stage) { return (slide && slide.dataset.theme) || (stage && stage.dataset.theme) || DEFAULT_THEME; }
  function guardSlide(slide, stage) {
    if (!slide) return;
    var theme = themeOf(slide, stage);
    var base = PAL[THEME_BG[theme]];
    var themeText = PAL[THEME_TEXT[theme]];
    if (!base || !themeText) return;   // not one of this Brand pack's themes
    // Scope to the slide itself — the persistent chrome lives outside .slide, so it
    // is never touched here (it inherits --text and is always legible by design).
    var els = slide.querySelectorAll(SEL);
    for (var i = 0; i < els.length; i++) guardEl(els[i], base, themeText);
  }

  // --- install onto the live deck -----------------------------------------
  function install() {
    var deck = window.deck;
    if (!deck || !deck.stage || !deck.slides) return false;
    var stage = deck.stage;

    var origGo = deck.go.bind(deck);
    deck.go = function (i) { origGo(i); guardSlide(deck.slides[deck.current], stage); };

    // Run after the controller's own change handler has set dataset.theme.
    if (deck.themeSelect) {
      deck.themeSelect.addEventListener('change', function () { guardSlide(deck.slides[deck.current], stage); });
    }

    // Keep saved source authoring-clean: restore authored colours, serialize, re-guard.
    if (typeof deck._serialize === 'function') {
      var origSer = deck._serialize.bind(deck);
      deck._serialize = function () {
        var guarded = stage.querySelectorAll('[data-deck-original-color]');
        for (var i = 0; i < guarded.length; i++) { guarded[i].style.color = guarded[i].dataset.deckOriginalColor; delete guarded[i].dataset.deckOriginalColor; }
        var html = origSer();
        guardSlide(deck.slides[deck.current], stage);
        return html;
      };
    }

    guardSlide(deck.slides[deck.current], stage);  // initial pass (go(0) already ran in the constructor)
    window.DeckContrast = { guard: guardSlide, contrast: contrast, palette: PAL };
    return true;
  }
  document.addEventListener('DOMContentLoaded', function () { if (!install()) setTimeout(install, 0); });
})();
