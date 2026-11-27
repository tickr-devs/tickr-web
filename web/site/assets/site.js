// tickr.bot site: language links, menu, early-access forms (post to /api/waitlist) and the reveal.
// Each page is built in English and in Spanish (web/site/build.py); this file only remembers the
// chosen language and speaks the page's language in the messages it shows.
(function () {
  const root = document.documentElement;
  const lang = root.lang === 'es' ? 'es' : 'en';
  const MSG = {
    en: { sending: 'Sending', invalid: 'That email address does not look right. Please check it.', rate: 'Too many attempts. Please try again in an hour.', error: 'Something went wrong on our side. Please try again later.', confirm: 'Almost done. Check your email and confirm your address.' },
    es: { sending: 'Enviando', invalid: 'Ese correo no parece correcto. Revíselo, por favor.', rate: 'Demasiados intentos. Inténtelo de nuevo en una hora.', error: 'Algo falló de nuestro lado. Inténtelo de nuevo más tarde.', confirm: 'Casi listo. Revise su correo y confirme su dirección.' }
  }[lang];
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Language links: remember the choice, so the next visit opens in it.
  document.querySelectorAll('a[data-lang]').forEach(a => a.addEventListener('click', () => {
    try { localStorage.setItem('tk-lang', a.dataset.lang); } catch (e) { /* storage may be blocked */ }
  }));

  // Menu on narrow screens: grows from its button, closes on Escape, a tap outside or a link.
  const header = document.querySelector('.site-h');
  const menuB = document.querySelector('.menu-b');
  if (header && menuB) {
    const setOpen = (open) => {
      header.classList.toggle('open', open);
      menuB.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
    menuB.addEventListener('click', () => setOpen(!header.classList.contains('open')));
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && header.classList.contains('open')) { setOpen(false); menuB.focus(); }
    });
    document.addEventListener('pointerdown', e => {
      if (header.classList.contains('open') && !header.contains(e.target)) setOpen(false);
    });
    header.querySelectorAll('.nav a').forEach(a => a.addEventListener('click', () => setOpen(false)));
  }

  // Early-access forms: one send at a time; success replaces the field with a quiet confirmation.
  function showStatus(form, status) {
    if (!['ok', 'confirm', 'invalid', 'rate', 'error', 'sending'].includes(status)) status = 'error';
    const msg = form.querySelector('.msg');
    if (status === 'ok' || status === 'confirm') {
      form.classList.add('is-done');
      msg.dataset.state = '';
      const done = form.querySelector('.done');
      if (status === 'confirm') form.querySelector('.done-text').textContent = MSG.confirm;
      done.hidden = false;
      done.focus({ preventScroll: true });
      return;
    }
    msg.dataset.state = status;
    msg.textContent = MSG[status];
  }
  document.querySelectorAll('form.signup').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (form.dataset.busy) return;
      const input = form.elements.namedItem('email');
      if (!input.value.trim() || !input.checkValidity()) { showStatus(form, 'invalid'); input.focus(); return; }
      const button = form.querySelector('button[type=submit]');
      form.dataset.busy = '1';
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      showStatus(form, 'sending');
      try {
        const res = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        showStatus(form, data.status || 'error');
      } catch (err) {
        showStatus(form, 'error');
      } finally {
        delete form.dataset.busy;
        button.disabled = false;
        button.removeAttribute('aria-busy');
      }
    });
  });
  const fromServer = new URLSearchParams(location.search).get('signup');
  const first = document.querySelector('form.signup');
  if (fromServer && first) showStatus(first, fromServer);

  // Reveal (home and Apps only): blocks below the first screen fade up once as they come into view.
  // Blocks that enter together follow each other by STAGGER_MS. CSS hides them only under .js.
  const STAGGER_MS = 50;
  const items = document.querySelectorAll('[data-reveal]');
  if (reduce || !('IntersectionObserver' in window)) {
    items.forEach(el => el.classList.add('in'));
  } else {
    const io = new IntersectionObserver(entries => {
      let n = 0;
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        en.target.style.transitionDelay = (n++ * STAGGER_MS) + 'ms';
        en.target.classList.add('in');
        io.unobserve(en.target);
      });
    }, { threshold: 0.12 });
    items.forEach(el => io.observe(el));
  }
})();
