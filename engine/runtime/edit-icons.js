/* === ICON PICKER (edit mode) ===
   In edit mode, click any .deck-icon on a slide to swap it for another icon from the
   embedded DeckIcons set, or remove it. A swap replaces only the element's inner
   SVG (viewBox + paths) and keeps its class/size/tint and fill="currentColor", so the
   new glyph inherits the slide's colour and contrast. Persistence rides on the
   controller's existing .slide-content autosave (deck._save). */
(function () {
  let pop = null, target = null;

  function close() { if (pop) pop.classList.remove('open'); target = null; }
  function save() { if (window.deck) window.deck._save(); }

  function swap(name) {
    const ico = window.DeckIcons && window.DeckIcons[name];
    if (!ico || !target) return;
    target.setAttribute('viewBox', ico.vb);
    target.innerHTML = ico.inner;
    close(); save();
  }
  function remove() { if (target) target.remove(); close(); save(); }

  function build() {
    pop = document.createElement('div');
    pop.className = 'deck-chrome deck-icon-picker';
    const grid = document.createElement('div'); grid.className = 'deck-icon-picker-grid';
    const lib = window.DeckIcons || {};
    Object.keys(lib).forEach(name => {
      const b = document.createElement('button'); b.type = 'button'; b.title = name;
      b.innerHTML = `<svg viewBox="${lib[name].vb}" class="deck-icon" aria-hidden="true">${lib[name].inner}</svg>`;
      b.addEventListener('click', () => swap(name));
      grid.appendChild(b);
    });
    const rm = document.createElement('button');
    rm.type = 'button'; rm.className = 'deck-icon-picker-remove'; rm.textContent = 'Remove icon';
    rm.addEventListener('click', remove);
    pop.appendChild(grid); pop.appendChild(rm);
    document.body.appendChild(pop);
  }

  function openFor(icon) {
    if (!pop) build();
    target = icon;
    const r = icon.getBoundingClientRect();
    pop.style.left = Math.max(8, Math.min(r.left, innerWidth - 320)) + 'px';
    pop.style.top = Math.min(r.bottom + 8, innerHeight - 360) + 'px';
    pop.classList.add('open');
  }

  document.addEventListener('DOMContentLoaded', () => {
    // The icon library is optional in a Brand pack. Without one there is no picker.
    if (!Object.keys(window.DeckIcons || {}).length) {
      document.body.classList.add('deck-no-icons');
      return;
    }
    // Capture phase so we act before the controller's click-away dismiss handler.
    document.addEventListener('click', e => {
      const d = window.deck;
      if (!d || !d.editing) return;
      if (e.target.closest('.deck-icon-picker')) return;     // let picker buttons handle their own clicks
      const icon = e.target.closest('.deck-icon');
      if (icon && d.stage && d.stage.contains(icon)) {
        e.preventDefault(); e.stopPropagation();            // don't toggle edit off, don't place caret
        openFor(icon); return;
      }
      close();                                              // click elsewhere closes the picker
    }, true);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  });
})();
