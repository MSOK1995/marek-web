// Tailwind theme lives in assets/tw-config.js (shared with the Play-CDN dev setup of html_4).
globalThis.tailwind = {};
require('./assets/tw-config.js');
module.exports = { ...globalThis.tailwind.config, content: [__dirname + '/dist/*.html', __dirname + '/assets/*.js'] };
