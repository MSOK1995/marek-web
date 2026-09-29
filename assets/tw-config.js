// Tailwind Play CDN config — shared by every page.
// Colours come from CSS variables in assets/site.css (one block per theme),
// so the theme picker can switch them at runtime. Token names are kept from
// the first palette so the page markup did not need to change:
//   bronze = small accent text, lemon = buttons, night = brand band,
//   onband = text on the band.
const v = name => `rgb(var(--c-${name}) / <alpha-value>)`;
tailwind.config = {
  theme: {
    extend: {
      colors: {
        paper: v('paper'), sand: v('sand'), blush: v('blush'), line: v('line'),
        ink: v('ink'), muted: v('muted'),
        bronze: v('accent'), bronzedeep: v('accent-deep'), bronzesoft: v('accent-soft'),
        lemon: v('btn'), lemondeep: v('btn-deep'),
        night: v('brand'), nightline: v('brand-line'), nightmuted: v('brand-soft'), onband: v('on-brand')
      },
      fontFamily: {
        sans: ['Archivo', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        quote: ['Newsreader', 'Georgia', 'serif']
      },
      maxWidth: { page: '80rem' }
    }
  }
};
