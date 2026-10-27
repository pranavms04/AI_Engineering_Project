# three.js (vendored)

- Package: `three` **0.186.1** from npm (released 2026-09-24), MIT licence (see `LICENSE`).
- Tarball sha1 `6d50f70c2c437f844179bbb56d6f5b774e1ca38a` (matches `npm view three@0.186.1 dist.shasum`).
- Files copied unchanged: `build/three.module.js`, `build/three.core.js`.
- `examples/jsm/controls/OrbitControls.js`: one line changed, `from 'three'` →
  `from './three.module.js'`, so the browser can load it without an import map
  (an inline import map would need a CSP exception).

Kept in the repo on purpose: the app must work offline and never load code from a CDN.
