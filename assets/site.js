// Shared behaviour for all pages. Every feature runs only if its markup exists.
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const hdr = $('#hdr');

  // Mobile menu (full-screen panel)
  const btn = $('#menuBtn'), nav = $('#mobileNav');
  if (btn && nav) {
    const set = open => {
      nav.hidden = !open;
      hdr.classList.toggle('menu-open', open);
      document.documentElement.style.overflow = open ? 'hidden' : '';
      btn.setAttribute('aria-expanded', String(open));
      btn.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen');
      $('.i-open', btn).hidden = open;
      $('.i-close', btn).hidden = !open;
    };
    btn.addEventListener('click', () => set(nav.hidden));
    $$('a', nav).forEach(a => a.addEventListener('click', () => set(false)));
    addEventListener('keydown', e => { if (e.key === 'Escape' && !nav.hidden) set(false); });
    matchMedia('(min-width: 1024px)').addEventListener('change', e => { if (e.matches) set(false); });
  }

  // Theme picker — 'sand' is the default (no data-theme attribute)
  const THEME_KEY = 'tcw4-theme';
  const themeBtns = document.querySelectorAll('[data-theme-set]');
  const applyTheme = t => {
    if (t === 'sand') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', t);
    themeBtns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.themeSet === t)));
  };
  let savedTheme = 'sand';
  try { savedTheme = localStorage.getItem(THEME_KEY) || 'sand'; } catch (e) {}
  applyTheme(savedTheme);
  themeBtns.forEach(b => b.addEventListener('click', () => {
    const t = b.dataset.themeSet;
    applyTheme(t);
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
  }));

  // Hero quote carousel (home)
  const hc = $('#heroCarousel');
  if (hc) {
    const imgs = $$('.hc-media img', hc), slides = $$('.hc-slide', hc), dots = $$('.hc-dot', hc);
    const toggle = $('.hc-toggle', hc);
    const DUR = 7000;
    let cur = 0, hover = false, focus = false, elapsed = 0, last = performance.now();
    let userPaused = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const sync = () => {
      hc.classList.toggle('paused', userPaused || hover || focus || document.hidden);
      toggle.setAttribute('aria-label', userPaused ? 'Abspielen' : 'Pause');
      // SVG elements have no .hidden property, so toggle the attribute
      $('.i-pause', toggle).toggleAttribute('hidden', userPaused);
      $('.i-play', toggle).toggleAttribute('hidden', !userPaused);
    };
    const go = i => {
      cur = (i + slides.length) % slides.length;
      [imgs, slides, dots].forEach(list => list.forEach((el, k) => el.classList.toggle('is-on', k === cur)));
      dots.forEach((d, k) => k === cur ? d.setAttribute('aria-current', 'true') : d.removeAttribute('aria-current'));
      elapsed = 0;
      dots.forEach(d => $('.hc-fill', d).style.setProperty('--p', 0));
    };
    dots.forEach((d, k) => {
      d.addEventListener('click', () => go(k));
    });
    toggle.addEventListener('click', () => { userPaused = !userPaused; sync(); });
    const inner = $('.hero-inner', hc);
    inner.addEventListener('mouseenter', () => { hover = true; sync(); });
    inner.addEventListener('mouseleave', () => { hover = false; sync(); });
    hc.addEventListener('focusin', () => { focus = true; sync(); });
    hc.addEventListener('focusout', e => { if (!hc.contains(e.relatedTarget)) { focus = false; sync(); } });
    document.addEventListener('visibilitychange', sync);
    let x0 = null;
    hc.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
    hc.addEventListener('touchend', e => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 50) go(cur + (dx < 0 ? 1 : -1));
    });
    hc.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') go(cur + 1);
      if (e.key === 'ArrowLeft') go(cur - 1);
    });
    setInterval(() => {
      const now = performance.now();
      if (!hc.classList.contains('paused')) elapsed += now - last;
      last = now;
      if (elapsed >= DUR) go(cur + 1);
      else $('.hc-fill', dots[cur]).style.setProperty('--p', (elapsed / DUR).toFixed(3));
    }, 100);
    sync();
  }

  // Split fill-text into words
  $$('.fill-text [data-split]').forEach(el => {
    el.innerHTML = el.textContent.trim().split(/\s+/).map(w => `<span class="w">${w}</span>`).join(' ');
  });
  const fills = $$('.fill-text').map(el => ({ el, words: $$('.w', el) }));

  // Header state is needed even with reduced motion
  const headerState = () => hdr && hdr.classList.toggle('scrolled', scrollY > 24);
  addEventListener('scroll', headerState, { passive: true });
  headerState();

  if (reduce) { fills.forEach(f => f.words.forEach(w => w.classList.add('on'))); return; }

  // Reveal on scroll
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      e.target.classList.remove('pre', 'icons-pre');
      io.unobserve(e.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  $$('.rv').forEach(el => {
    if (el.getBoundingClientRect().top > innerHeight * 0.92) el.classList.add('pre');
    io.observe(el);
  });
  if (fx && fx.getBoundingClientRect().top > innerHeight) { fx.classList.add('icons-pre'); io.observe(fx); }

  // Count-up numbers (final value stays in the markup)
  $$('[data-count]').forEach(el => {
    if (el.getBoundingClientRect().top < innerHeight) return;
    const target = +el.dataset.count;
    const cio = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      cio.disconnect();
      const t0 = performance.now(), dur = 1500;
      const step = t => {
        const k = Math.min(1, (t - t0) / dur);
        el.textContent = Math.round(target * (1 - Math.pow(1 - k, 3)));
        if (k < 1) requestAnimationFrame(step);
      };
      el.textContent = '0';
      requestAnimationFrame(step);
    }, { threshold: 1 });
    cio.observe(el);
  });

  // Scroll-linked effects
  const heroImg = $('.hero > img, .hero > picture > img, .hc-media');
  const parallax = $$('.parallax');
  const timelines = $$('[data-timeline]').map(tl => ({ tl, fill: $('.tl-fill', tl), nodes: $$('.tl-node', tl) }));
  timelines.forEach(t => t.nodes.forEach(n => n.classList.remove('on')));
  const progress = $('#progress');
  const secLinks = $$('.secnav a[href^="#"]');
  const secTargets = secLinks.map(a => document.getElementById(a.getAttribute('href').slice(1)));

  let ticking = false;
  function frame() {
    const vh = innerHeight;

    if (heroImg && scrollY < vh * 1.2) heroImg.style.transform = `translate3d(0, ${(scrollY * 0.18).toFixed(1)}px, 0)`;

    parallax.forEach(img => {
      const r = (img.parentElement.closest(':not(picture)') || img.parentElement).getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh) return;
      const c = (r.top + r.height / 2 - vh / 2) / vh;
      img.style.transform = `translate3d(0, ${(-c * (+img.dataset.speed || 0.08) * 100).toFixed(2)}%, 0)`;
    });

    fills.forEach(({ el, words }) => {
      const r = el.getBoundingClientRect();
      const p = clamp((vh * 0.85 - r.top) / (vh * 0.5 + r.height * 0.5));
      const lit = Math.round(p * words.length);
      words.forEach((w, i) => w.classList.toggle('on', i < lit));
    });

    timelines.forEach(({ tl, fill, nodes }) => {
      const r = tl.getBoundingClientRect();
      if (fill) fill.style.setProperty('--p', clamp((vh * 0.6 - r.top) / r.height).toFixed(3));
      nodes.forEach(n => {
        const nr = n.getBoundingClientRect();
        n.classList.toggle('on', nr.top + nr.height / 2 < vh * 0.6);
      });
    });

    if (progress) {
      const max = document.documentElement.scrollHeight - vh;
      progress.style.setProperty('--p', max > 0 ? clamp(scrollY / max).toFixed(4) : 0);
    }

    if (secLinks.length) {
      let idx = 0;
      secTargets.forEach((t, i) => { if (t && t.getBoundingClientRect().top < vh * 0.35) idx = i; });
      secLinks.forEach((a, i) => a.classList.toggle('active', i === idx));
    }
    ticking = false;
  }
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }, { passive: true });
  addEventListener('resize', frame);
  frame();
})();
