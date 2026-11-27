// tickr.bot site: language switch, menu, early-access forms (post to /api/waitlist) and gentle reveal.
// English lives in the HTML. Spanish comes from this file (shared parts) and window.TK_ES (the page).
(function () {
  const COMMON_ES = window.TK_COMMON_ES || {};
  const ES = Object.assign({}, COMMON_ES, window.TK_ES || {});
  const MSG = {
    en: { sending: 'Sending', invalid: 'That email address does not look right. Please check it.', rate: 'Too many attempts. Please try again in an hour.', error: 'Something went wrong on our side. Please try again later.' },
    es: { sending: 'Enviando', invalid: 'Ese correo no parece correcto. Revíselo, por favor.', rate: 'Demasiados intentos. Inténtelo de nuevo en una hora.', error: 'Algo falló de nuestro lado. Inténtelo de nuevo más tarde.' }
  };
  const CONFIRM_EN = 'Almost done. Check your email and confirm your address.';
  const ATTRS = { 'data-i18n-aria': 'aria-label', 'data-i18n-ph': 'placeholder', 'data-i18n-alt': 'alt' };
  const original = new Map();
  const forms = Array.from(document.querySelectorAll('form.signup'));
  let lang = 'en';

  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage may be blocked */ } }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  function setLang(next) {
    lang = next === 'es' ? 'es' : 'en';
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(el => {
      if (!original.has(el)) original.set(el, el.innerHTML);
      const v = lang === 'es' ? ES[el.dataset.i18n] : undefined;
      el.innerHTML = v !== undefined ? v : original.get(el);
    });
    Object.entries(ATTRS).forEach(([data, attr]) => {
      document.querySelectorAll('[' + data + ']').forEach(el => {
        const key = '__' + attr;
        if (!el[key]) el[key] = el.getAttribute(attr) || '';
        const v = lang === 'es' ? ES[el.getAttribute(data)] : undefined;
        el.setAttribute(attr, v !== undefined ? v : el[key]);
      });
    });
    if (ES.__title && lang === 'es') document.title = ES.__title;
    else if (document.documentElement.dataset.title) document.title = document.documentElement.dataset.title;
    document.querySelectorAll('button[data-lang]').forEach(b => b.setAttribute('aria-pressed', b.dataset.lang === lang ? 'true' : 'false'));
    forms.forEach(f => {
      f.elements.namedItem('lang').value = lang;
      if (f.dataset.status && f.dataset.status !== 'ok' && f.dataset.status !== 'confirm') showStatus(f, f.dataset.status);
    });
    store('tk-lang', lang);
  }
  document.querySelectorAll('[data-i18n]').forEach(el => original.set(el, el.innerHTML));
  document.documentElement.dataset.title = document.title;
  document.querySelectorAll('button[data-lang]').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
  const saved = read('tk-lang');
  const initial = saved || ((navigator.language || '').toLowerCase().startsWith('es') ? 'es' : 'en');
  if (initial === 'es') setLang('es');

  // Menu on narrow screens.
  const header = document.querySelector('.site-h');
  const menuB = document.querySelector('.menu-b');
  if (header && menuB) {
    menuB.addEventListener('click', () => {
      const open = header.classList.toggle('open');
      menuB.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && header.classList.contains('open')) { header.classList.remove('open'); menuB.setAttribute('aria-expanded', 'false'); menuB.focus(); }
    });
  }

  // Early-access forms: success replaces the field with a quiet confirmation; no second send is offered.
  function showStatus(form, status) {
    if (!['ok', 'confirm', 'invalid', 'rate', 'error', 'sending'].includes(status)) status = 'error';
    form.dataset.status = status;
    const msg = form.querySelector('.msg');
    if (status === 'ok' || status === 'confirm') {
      form.classList.add('is-done');
      msg.dataset.state = '';
      const done = form.querySelector('.done');
      const text = form.querySelector('.done-text');
      text.dataset.i18n = status;
      if (status === 'confirm') original.set(text, CONFIRM_EN);
      text.innerHTML = lang === 'es' ? ES[status] : original.get(text);
      done.hidden = false;
      done.focus({ preventScroll: true });
      return;
    }
    msg.dataset.state = status;
    msg.textContent = MSG[lang][status];
  }
  forms.forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = form.elements.namedItem('email');
      if (!input.value.trim() || !input.checkValidity()) { showStatus(form, 'invalid'); input.focus(); return; }
      const button = form.querySelector('button[type=submit]');
      button.disabled = true;
      showStatus(form, 'sending');
      try {
        const res = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        showStatus(form, data.status || 'error');
      } catch (err) {
        showStatus(form, 'error');
      } finally {
        button.disabled = false;
      }
    });
  });
  const fromServer = new URLSearchParams(location.search).get('signup');
  if (fromServer && forms.length) showStatus(forms[0], fromServer);

  // Reveal: elements marked data-reveal fade up once when they enter the view.
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const items = document.querySelectorAll('[data-reveal]');
  if (reduce || !('IntersectionObserver' in window)) {
    items.forEach(el => el.classList.add('in'));
  } else {
    const io = new IntersectionObserver(entries => entries.forEach(en => {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    }), { threshold: 0.12 });
    items.forEach(el => io.observe(el));
  }
  window.tkReduceMotion = reduce;
})();
