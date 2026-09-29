// Cookie consent — no third-party tool. The choice is stored in localStorage ("tcw-consent")
// for 12 months; changing CONSENT_VERSION asks everyone again (e.g. after adding a new service).
//
// Gate a script behind a category:
//   <script type="text/plain" data-consent="statistics" src="https://…"></script>
//   <script type="text/plain" data-consent="marketing">/* inline code */</script>
// Other code can ask:  window.tcwConsent.has('statistics')   or listen to the
// 'tcw:consent' event on document (detail = current choice).
(() => {
  const KEY = 'tcw-consent';
  const CONSENT_VERSION = 1;
  const MAX_AGE = 365 * 24 * 60 * 60 * 1000;
  const CATS = ['preferences', 'statistics', 'marketing'];
  const box = document.getElementById('consent');
  if (!box) return;

  const read = () => {
    try {
      const c = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (c && c.v === CONSENT_VERSION && Date.now() - c.t < MAX_AGE) return c;
    } catch (e) {}
    return null;
  };
  let choice = read();

  const activate = () => {
    document.querySelectorAll('script[type="text/plain"][data-consent]').forEach(old => {
      if (!choice || !choice[old.dataset.consent]) return;
      const s = document.createElement('script');
      [...old.attributes].forEach(a => { if (a.name !== 'type' && a.name !== 'data-consent') s.setAttribute(a.name, a.value); });
      s.text = old.text;
      old.replaceWith(s);
    });
  };

  const store = values => {
    choice = { v: CONSENT_VERSION, t: Date.now(), functional: true, ...values };
    try { localStorage.setItem(KEY, JSON.stringify(choice)); } catch (e) {}
    document.dispatchEvent(new CustomEvent('tcw:consent', { detail: choice }));
    activate();
    close();
  };

  const cats = box.querySelector('.consent-cats');
  const btn = a => box.querySelector(`[data-consent-action="${a}"]`);
  const boxes = [...box.querySelectorAll('input[data-cat]')];

  const showPrefs = on => {
    cats.hidden = !on;
    btn('view').hidden = on;
    btn('save').hidden = !on;
  };
  const open = (prefs = false) => {
    boxes.forEach(b => { b.checked = !!(choice && choice[b.dataset.cat]); });
    showPrefs(prefs);
    box.hidden = false;
    requestAnimationFrame(() => box.classList.add('is-open'));
  };
  const close = () => {
    box.classList.remove('is-open');
    box.hidden = true;
  };

  btn('accept').addEventListener('click', () => store(Object.fromEntries(CATS.map(c => [c, true]))));
  btn('deny').addEventListener('click', () => store(Object.fromEntries(CATS.map(c => [c, false]))));
  btn('view').addEventListener('click', () => { showPrefs(true); boxes[0].focus(); });
  btn('save').addEventListener('click', () => store(Object.fromEntries(boxes.map(b => [b.dataset.cat, b.checked]))));
  box.querySelectorAll('.consent-more').forEach(b => b.addEventListener('click', () => {
    const d = document.getElementById(b.getAttribute('aria-controls'));
    const on = b.getAttribute('aria-expanded') !== 'true';
    b.setAttribute('aria-expanded', String(on));
    d.hidden = !on;
  }));
  // "Manage consent" links (footer) reopen the dialog with the categories visible
  document.querySelectorAll('[data-consent-open]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault(); open(true); btn('save').focus();
  }));

  window.tcwConsent = { has: cat => cat === 'functional' || !!(choice && choice[cat]), open: () => open(true) };
  if (choice) activate(); else open(false);
})();
