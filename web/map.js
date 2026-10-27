// The knowledge map: every chunk as a point in 3D (PCA of its embedding), and the question
// flying in to land among the chunks it is closest to. Only for understanding; the full
// answer and sources are always also shown as text.

import * as THREE from "./vendor/three/three.module.js";
import { OrbitControls } from "./vendor/three/OrbitControls.js";
import { citationTag } from "./render.js";

const PALETTE = ["#f2b544", "#6fd3c4", "#b59cff", "#ff9b71", "#8ab4f8", "#e9f08c"];
const SPREAD = 2.4; // map coordinates are in [-1, 1]; scale them up into world units
const VIEW_DIRECTION = new THREE.Vector3(4.2, 2.6, 5.2).normalize(); // overview: from the front, a little above
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const ease = (t) => 1 - Math.pow(1 - t, 3);

export function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGLRenderingContext && (canvas.getContext("webgl2") || canvas.getContext("webgl")));
  } catch {
    return false;
  }
}

export class KnowledgeMap {
  constructor(container, { onHover } = {}) {
    this.container = container;
    this.onHover = onHover || (() => {});
    this.points = [];
    this.byKey = new Map();
    this.colors = new Map();
    this.tweens = [];
    this.links = [];

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.setAttribute("aria-hidden", "true");
    container.append(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x0e1014, 6, 13);
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    this.home = VIEW_DIRECTION.clone().multiplyScalar(7);
    this.camera.position.copy(this.home);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.controls.minDistance = 2.5;
    this.controls.maxDistance = 11;
    this.controls.autoRotate = !reduceMotion.matches;
    this.controls.autoRotateSpeed = 0.35;
    this.controls.addEventListener("start", () => (this.controls.autoRotate = false));

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(3, 5, 4);
    this.scene.add(key);

    this.addGuides();

    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.sphere = new THREE.SphereGeometry(0.075, 20, 14);

    // The question marker: a bright core and a soft halo.
    this.question = new THREE.Group();
    this.question.add(new THREE.Mesh(new THREE.SphereGeometry(0.085, 24, 16), new THREE.MeshBasicMaterial({ color: 0xffffff })));
    this.halo = new THREE.Mesh(
      new THREE.SphereGeometry(0.2, 24, 16),
      new THREE.MeshBasicMaterial({ color: 0xf2b544, transparent: true, opacity: 0.22, depthWrite: false })
    );
    this.question.add(this.halo);
    this.question.visible = false;
    this.scene.add(this.question);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2(9, 9);
    this.hovered = null;
    this.pinned = null; // a chunk the user jumped to from a citation: keeps its label until the pointer moves
    this.renderer.domElement.addEventListener("pointermove", (e) => {
      this.pinned = null;
      this.handlePointer(e);
    });
    this.renderer.domElement.addEventListener("pointerleave", () => {
      this.pointer.set(9, 9);
      this.setHover(null);
    });

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();

    this.renderer.setAnimationLoop(() => this.frame());
  }

  addGuides() {
    const grid = new THREE.GridHelper(SPREAD * 2.4, 12, 0x2a303a, 0x1b1f26);
    grid.position.y = -SPREAD * 1.05;
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    this.scene.add(grid);
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.fitHome();
  }

  // Pick a camera distance that shows every point, whatever the panel's shape (a tall phone strip or a wide desktop panel).
  fitHome() {
    const radius = this.points.length
      ? Math.max(...this.points.map((p) => p.target.length())) + 0.25
      : SPREAD * Math.sqrt(3);
    const vertical = THREE.MathUtils.degToRad(this.camera.fov) / 2;
    const horizontal = Math.atan(Math.tan(vertical) * this.camera.aspect);
    // Distance at which a sphere of this radius just fills the narrower side of the view.
    const distance = radius / Math.tan(Math.min(vertical, horizontal)) + radius * 0.35;
    const atHome = this.camera.position.distanceTo(this.home) < 0.01;
    this.home = VIEW_DIRECTION.clone().multiplyScalar(distance);
    this.controls.maxDistance = Math.max(11, distance * 1.6);
    // Fog only softens the far side of the cloud; it must not swallow the near points.
    this.scene.fog.near = distance - radius * 0.2;
    this.scene.fog.far = distance + radius * 2.2;
    if (atHome || !this.hasFitted) this.camera.position.copy(this.home);
    this.hasFitted = true;
  }

  colorFor(source) {
    if (!this.colors.has(source)) this.colors.set(source, PALETTE[this.colors.size % PALETTE.length]);
    return this.colors.get(source);
  }

  // points: [{ id, source, page, chunk_index, x, y, z, preview }]
  setPoints(points) {
    const previous = new Map(this.points.map((p) => [p.key, p.mesh.position.clone()]));
    this.clearHighlight();
    this.group.clear();
    this.points = [];
    this.byKey.clear();

    for (const p of points) {
      const color = new THREE.Color(this.colorFor(p.source));
      const material = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.35,
        roughness: 0.4,
        transparent: true,
        opacity: 1,
      });
      const mesh = new THREE.Mesh(this.sphere, material);
      const target = new THREE.Vector3(p.x, p.y, p.z).multiplyScalar(SPREAD);
      const key = this.key(p.source, p.page, p.chunk_index);
      const entry = { ...p, key, mesh, target, tag: citationTag(p.source, p.page) };
      mesh.userData.entry = entry;
      // Points grow in from where they were (or from the centre on first load).
      const from = previous.get(key) || new THREE.Vector3(0, 0, 0);
      this.moveTo(mesh, from, target, 900 + Math.random() * 500);
      this.group.add(mesh);
      this.points.push(entry);
      this.byKey.set(key, entry);
    }
    this.hasFitted = false;
    this.fitHome();
  }

  key(source, page, chunkIndex) {
    return `${source}|${page ?? ""}|${chunkIndex ?? ""}`;
  }

  legend() {
    return [...new Set(this.points.map((p) => p.source))].map((source) => ({ source, color: this.colorFor(source) }));
  }

  // ----- the question -----

  // Ease back to the overview, so the next question can be seen arriving.
  resetView(ms = 700) {
    this.moveTo(this.controls.target, this.controls.target.clone(), new THREE.Vector3(0, 0, 0), ms);
    this.moveTo(this.camera.position, this.camera.position.clone(), this.home.clone(), ms);
  }

  startSearching() {
    this.clearHighlight();
    this.resetView();
    this.question.visible = true;
    this.question.position.set(0, SPREAD * 1.0, 0);
    this.searching = true;
  }

  // sources: AskResponse.sources; point: AskResponse.question_point; invalid: tags the model cited wrongly
  showAnswer({ point, sources, invalid = [], abstained }) {
    this.searching = false;
    if (!point) {
      this.question.visible = false;
      return;
    }
    const target = new THREE.Vector3(...point).multiplyScalar(SPREAD);
    this.moveTo(this.question, this.question.position.clone(), target, 1000);

    const retrieved = new Set(sources.map((s) => this.key(s.source, s.page, s.chunk_index)));
    const invalidTags = new Set(invalid);
    for (const entry of this.points) {
      const hit = retrieved.has(entry.key);
      entry.mesh.material.opacity = hit ? 1 : 0.28;
      entry.mesh.material.emissiveIntensity = hit ? 0.9 : 0.2;
      entry.mesh.scale.setScalar(hit ? 1.7 : 1);
    }
    if (abstained) return; // nothing was close enough: no lines to draw

    sources.forEach((s, i) => {
      const entry = this.byKey.get(this.key(s.source, s.page, s.chunk_index));
      if (!entry) return;
      const geometry = new THREE.BufferGeometry().setFromPoints([target, entry.target]);
      const material = new THREE.LineBasicMaterial({
        color: 0xf2b544,
        transparent: true,
        opacity: 0,
      });
      const line = new THREE.Line(geometry, material);
      line.userData.goal = 0.25 + 0.75 * Math.max(0, Math.min(1, s.score));
      line.userData.delay = 900 + i * 160;
      line.userData.born = performance.now();
      this.scene.add(line);
      this.links.push(line);
    });
    // A page the model cited but was never given has no point to light up; the text view explains it.
    this.invalid = invalidTags;
  }

  clearHighlight() {
    if (this.pinned) this.onHover(null);
    this.pinned = null;
    for (const line of this.links) {
      this.scene.remove(line);
      line.geometry.dispose();
      line.material.dispose();
    }
    this.links = [];
    for (const entry of this.points) {
      entry.mesh.material.opacity = 1;
      entry.mesh.material.emissiveIntensity = 0.35;
      entry.mesh.scale.setScalar(1);
    }
  }

  // Fly the camera towards a chunk (clicking a citation or a source row).
  focus(source, page, chunkIndex) {
    const entry =
      this.byKey.get(this.key(source, page, chunkIndex)) ||
      this.points.find((p) => p.source === source && (p.page ?? null) === (page ?? null));
    if (!entry) return false;
    this.controls.autoRotate = false;
    const goal = entry.target.clone();
    const offset = this.camera.position.clone().sub(this.controls.target).setLength(3.2);
    this.moveTo(this.controls.target, this.controls.target.clone(), goal, 700);
    this.moveTo(this.camera.position, this.camera.position.clone(), goal.clone().add(offset), 700);
    this.pulse = { entry, until: performance.now() + 1600 };
    entry.mesh.material.opacity = 1;
    entry.mesh.material.emissiveIntensity = 0.9;
    this.pinned = entry;
    return true;
  }

  // ----- hover -----

  handlePointer(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.pointerPx = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  setHover(entry) {
    if (entry === this.hovered) return;
    this.hovered = entry;
    this.renderer.domElement.style.cursor = entry ? "pointer" : "grab";
    this.onHover(entry, this.pointerPx);
  }

  // ----- animation -----

  moveTo(vector, from, to, ms) {
    const target = vector.position || vector; // a mesh or a plain Vector3
    if (reduceMotion.matches) {
      target.copy(to);
      return;
    }
    this.tweens = this.tweens.filter((t) => t.target !== target);
    target.copy(from);
    this.tweens.push({ target, from, to, start: performance.now(), ms });
  }

  frame() {
    const now = performance.now();
    this.tweens = this.tweens.filter((t) => {
      const k = Math.min(1, (now - t.start) / t.ms);
      t.target.lerpVectors(t.from, t.to, ease(k));
      return k < 1;
    });

    for (const line of this.links) {
      const k = reduceMotion.matches ? 1 : Math.max(0, Math.min(1, (now - line.userData.born - line.userData.delay) / 500));
      line.material.opacity = line.userData.goal * k;
    }

    const t = now / 1000;
    if (this.question.visible && !reduceMotion.matches) {
      const beat = this.searching ? 1 + 0.35 * Math.sin(t * 6) : 1 + 0.12 * Math.sin(t * 2.2);
      this.halo.scale.setScalar(beat);
      if (this.searching) this.question.position.y = SPREAD * 1.0 + 0.08 * Math.sin(t * 3);
    }
    if (this.pulse) {
      const left = this.pulse.until - now;
      const s = left > 0 && !reduceMotion.matches ? 2 + 0.6 * Math.sin(t * 10) : 1.7;
      this.pulse.entry.mesh.scale.setScalar(s);
      if (left <= 0) this.pulse = null;
    }

    if (this.pinned) {
      // Keep the label on the chunk we flew to, following it on screen while the camera moves.
      const v = this.pinned.mesh.position.clone().project(this.camera);
      const { clientWidth: w, clientHeight: h } = this.container;
      this.pointerPx = { x: ((v.x + 1) / 2) * w, y: ((1 - v.y) / 2) * h };
      this.hovered = null;
      this.onHover(this.pinned, this.pointerPx);
    } else if (this.points.length) {
      this.raycaster.setFromCamera(this.pointer, this.camera);
      const hit = this.raycaster.intersectObjects(this.group.children, false)[0];
      this.setHover(hit ? hit.object.userData.entry : null);
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}
