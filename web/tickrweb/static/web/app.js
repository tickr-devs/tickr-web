// tickr.bot web app: small touches on top of plain HTML forms (every page works without this file).
// One send per press, row selection on Early access, the phone menu, the wrong-code shake and the
// edge fade on wide tables. Loaded with defer from base.html; the CSP allows only 'self' scripts.
(function () {
  const root = document.documentElement;
  root.classList.add('js');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // One send per press: after a form is sent, its button shows our spinner and further presses do
  // nothing until the next page. The button is not disabled, so its name and value are still sent.
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (e.defaultPrevented || !(form instanceof HTMLFormElement)) return;
    if (form.dataset.busy) { e.preventDefault(); return; }
    form.dataset.busy = '1';
    const button = e.submitter;
    if (button) { button.setAttribute('aria-busy', 'true'); button.setAttribute('aria-disabled', 'true'); }
  });
  // Coming back with the browser's Back button shows the page as it was left: make it pressable again.
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[data-busy]').forEach(f => delete f.dataset.busy);
    document.querySelectorAll('[aria-busy=true]').forEach(b => { b.removeAttribute('aria-busy'); b.removeAttribute('aria-disabled'); });
  });

  // Early access: a tap anywhere on a row ticks it; the button counts the ticked rows.
  document.querySelectorAll('table.pick').forEach(table => {
    const form = table.closest('form');
    const button = form && form.querySelector('button[data-count-label]');
    const boxes = Array.from(table.querySelectorAll('input[type=checkbox]'));
    const update = () => {
      const n = boxes.filter(b => b.checked).length;
      boxes.forEach(b => b.closest('tr').classList.toggle('on', b.checked));
      if (!button) return;
      button.disabled = n === 0;
      button.querySelector('.lbl-t').textContent = n === 0 ? button.dataset.emptyLabel : button.dataset.countLabel.replace('{count}', n);
    };
    boxes.forEach(b => {
      const row = b.closest('tr');
      row.classList.add('tap');
      row.addEventListener('click', (e) => {
        if (e.target === b || e.target.closest('a,button,label')) return;
        b.checked = !b.checked;
        update();
      });
      b.addEventListener('change', update);
    });
    update();
  });

  // Phone menu (a <details>): grows from its button, shrinks back on close; closes on Escape or a
  // tap outside it.
  const CLOSE_MS = 180;
  document.querySelectorAll('.mtop details').forEach(menu => {
    const summary = menu.querySelector('summary');
    const close = () => {
      if (!menu.open || menu.classList.contains('closing')) return;
      if (reduce) { menu.open = false; return; }
      menu.classList.add('closing');
      setTimeout(() => { menu.open = false; menu.classList.remove('closing'); }, CLOSE_MS);
    };
    summary.addEventListener('click', (e) => { if (menu.open) { e.preventDefault(); close(); } });
    document.addEventListener('pointerdown', (e) => { if (!menu.contains(e.target)) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.open) { close(); summary.focus(); } });
  });

  // A wrong code: the field shakes once (CSS) and its digits are selected, ready to type again.
  const wrong = document.querySelector('input.code[aria-invalid=true]');
  if (wrong) { wrong.focus(); wrong.select(); }

  // Wide tables scroll sideways without a scroll bar; a soft fade at the edge says there is more.
  document.querySelectorAll('.scroll').forEach(box => {
    const edge = () => {
      const more = box.scrollLeft + box.clientWidth < box.scrollWidth - 1;
      box.classList.toggle('more-r', more);
      box.classList.toggle('more-l', box.scrollLeft > 0);
    };
    box.addEventListener('scroll', edge, { passive: true });
    window.addEventListener('resize', edge);
    edge();
  });
})();
