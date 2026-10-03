// Rebuilds a GeoGuessr avatar from its parts and renders one animation frame.
// Driven from Python via window.renderAvatar(spec); see renderer.py for the spec shape.

import * as THREE from 'three';
import { GLTFLoader } from './vendor/GLTFLoader.js';
import { DRACOLoader } from './vendor/DRACOLoader.js';
import { clone as cloneSkinned } from './vendor/SkeletonUtils.js';

const dracoLoader = new DRACOLoader().setDecoderPath('./vendor/draco/');
const gltfLoader = new GLTFLoader().setDRACOLoader(dracoLoader);
const textureLoader = new THREE.TextureLoader();

const gltfCache = new Map();
const textureCache = new Map();

function loadGltf(url) {
  if (!gltfCache.has(url)) {
    const p = gltfLoader.loadAsync(url);
    p.catch(() => gltfCache.delete(url));
    gltfCache.set(url, p);
  }
  return gltfCache.get(url);
}

function loadTexture(url) {
  if (!textureCache.has(url)) {
    const p = textureLoader.loadAsync(url);
    p.catch(() => textureCache.delete(url));
    textureCache.set(url, p);
  }
  return textureCache.get(url);
}

// --- Materials ------------------------------------------------------------------
// Toon look matching GeoGuessr's avatar shader: a soft two-tone diffuse from a
// view-space light on the left, a pinkish shadow tint, a slight saturation boost and
// an olive rim light.

const RIM_COLOR = new THREE.Color(0.374, 0.378, 0.241);

const toonVertex = /* glsl */ `
  #include <common>
  #include <morphtarget_pars_vertex>
  #include <skinning_pars_vertex>
  varying vec2 vUv;
  varying vec3 vViewNormal;
  varying vec3 vViewPosition;
  void main() {
    vUv = uv;
    #include <beginnormal_vertex>
    #include <skinbase_vertex>
    #include <skinnormal_vertex>
    #include <begin_vertex>
    #include <morphtarget_vertex>
    #include <skinning_vertex>
    vec4 mvPosition = modelViewMatrix * vec4(transformed, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    vViewNormal = normalMatrix * objectNormal;
    vViewPosition = mvPosition.xyz;
  }
`;

const toonFragment = /* glsl */ `
  uniform sampler2D tex;
  uniform vec2 repeat;
  uniform vec3 rimColor;
  uniform float rimIntensity;
  uniform float opacity;
  varying vec2 vUv;
  varying vec3 vViewNormal;
  varying vec3 vViewPosition;

  const vec3 LIGHT_DIR = vec3(-1.0, 0.0, 0.0);
  const vec3 SHADOW_TINT = vec3(0.950, 0.896, 0.929);
  const float SATURATION = -0.1;

  void main() {
    vec3 rgb = texture2D(tex, vUv * repeat).rgb;
    float mid = 0.5 * (min(min(rgb.r, rgb.g), rgb.b) + max(max(rgb.r, rgb.g), rgb.b));
    rgb = mix(rgb, vec3(mid), SATURATION);

    vec3 n = normalize(vViewNormal);
    float nDotL = dot(LIGHT_DIR, n);
    float lit = smoothstep(-0.90, -0.42, nDotL);
    vec3 color = rgb * lit + SHADOW_TINT * rgb * (1.0 - lit);

    #ifdef FIXED_VIEW_DIR
      vec3 viewDir = vec3(0.0, 0.0, 1.0);
    #else
      vec3 viewDir = normalize(-vViewPosition);
    #endif
    // pow() of a negative base is undefined in GLSL; GPUs effectively yield no rim there.
    float rim = smoothstep(0.33, 0.71, (1.0 - dot(n, viewDir)) * pow(max(nDotL, 0.0), rimIntensity));

    gl_FragColor = vec4(color + rim * rimColor, 1.0) * opacity;
  }
`;

function toonMaterial(texture, { skinned = true } = {}) {
  return new THREE.ShaderMaterial({
    uniforms: {
      tex: { value: texture },
      repeat: { value: new THREE.Vector2(1, 1) },
      rimColor: { value: RIM_COLOR },
      rimIntensity: { value: 0.42 },
      opacity: { value: 1 },
    },
    defines: skinned ? { FIXED_VIEW_DIR: '' } : {},
    vertexShader: toonVertex,
    fragmentShader: toonFragment,
  });
}

async function toonTexture(url) {
  if (!url) return null;
  const t = (await loadTexture(url)).clone();
  t.flipY = false;
  t.needsUpdate = true;
  return t;
}

async function faceTexture(url) {
  if (!url) return null;
  const t = (await loadTexture(url)).clone();
  t.colorSpace = THREE.SRGBColorSpace;
  t.flipY = false;
  t.premultiplyAlpha = true;
  t.needsUpdate = true;
  return t;
}

// --- Scene assembly ---------------------------------------------------------------

function skinnedMeshes(root) {
  const out = [];
  root.traverse((o) => {
    if (o.isSkinnedMesh && !Array.isArray(o.material)) out.push(o);
  });
  return out;
}

// GeoGuessr re-binds every clothing mesh to the head's skeleton with an identity bind
// matrix, so we do the same rather than keeping each GLB's own skeleton.
function rebind(source, skeleton, material) {
  const mesh = new THREE.SkinnedMesh(source.geometry, material);
  mesh.skeleton = skeleton;
  mesh.frustumCulled = false;
  if (source.morphTargetDictionary) {
    mesh.morphTargetDictionary = source.morphTargetDictionary;
    mesh.morphTargetInfluences = [...source.morphTargetInfluences];
  }
  return mesh;
}

function applyMorphTargets(mesh, enabled) {
  if (!mesh.morphTargetDictionary) return;
  for (const [key, index] of Object.entries(mesh.morphTargetDictionary)) {
    const name = key.substring(key.indexOf('.') + 1);
    mesh.morphTargetInfluences[index] = enabled.includes(name) ? 1 : 0;
  }
}

async function buildAvatar(spec) {
  const group = new THREE.Group();
  const head = cloneSkinned((await loadGltf(spec.head)).scene);
  group.add(head);

  const byMaterial = {};
  for (const m of skinnedMeshes(head)) {
    byMaterial[m.material.name.toUpperCase()] = m;
    m.visible = false;
  }
  const headSkin = byMaterial.M_SKIN;
  const skeleton = headSkin.skeleton;

  const skinMaterial = toonMaterial(await toonTexture(spec.skin));
  const eyesMaterial = new THREE.MeshBasicMaterial({ transparent: true, fog: false, map: await faceTexture(spec.eyes) });
  const mouthMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, map: await faceTexture(spec.mouth) });

  if (!spec.hideHead) {
    group.add(rebind(headSkin, skeleton, skinMaterial));
    if (eyesMaterial.map) group.add(rebind(byMaterial.M_EYES, skeleton, eyesMaterial));
    if (mouthMaterial.map) group.add(rebind(byMaterial.M_MOUTH, skeleton, mouthMaterial));
  }

  const handhelds = [];
  for (const item of spec.items) {
    const [gltf, texture] = await Promise.all([loadGltf(item.mesh), toonTexture(item.texture)]);
    const itemMaterial = toonMaterial(texture);
    for (const source of skinnedMeshes(gltf.scene)) {
      const isSkin = source.material.name.toLowerCase().includes('skin');
      const mesh = rebind(source, skeleton, isSkin ? skinMaterial : itemMaterial);
      if (item.handheld) handhelds.push(mesh);
      else applyMorphTargets(mesh, spec.morphTargets);
      group.add(mesh);
    }
  }

  return { group, skeleton, eyesMaterial, mouthMaterial, handhelds };
}

// --- Animation --------------------------------------------------------------------

// The clip stores the face expression as a rotation: Euler X (degrees) is the UV offset
// into the eyes sprite strip and Euler Y the offset into the mouth strip, in 1/8 steps.
function faceOffsets(track, time) {
  if (!track) return [0, 0];
  let i = track.times.findIndex((t) => t > time);
  if (i < 0) i = track.times.length - 1;
  const v = track.values;
  const q = new THREE.Quaternion(v[4 * i], v[4 * i + 1], v[4 * i + 2], v[4 * i + 3]);
  const e = new THREE.Euler().setFromQuaternion(q);
  const step = (rad) => Math.round(8 * THREE.MathUtils.radToDeg(rad)) / 8;
  // A few clips (UPSET, UPSET_MORE) carry face data from another rig that points far
  // outside the 8-cell strips, which would render a blank face. Show the neutral one.
  const cell = (offset) => (offset >= 0 && offset < 1 ? offset : 0);
  return [cell(step(e.x)), cell(step(e.y))];
}

async function applyClip(spec, avatar) {
  const info = { duration: 0, time: 0 };
  if (!spec.clip) return info;

  const gltf = await loadGltf(spec.clip.glb);
  const source = gltf.animations[0];
  if (!source) throw new Error(`no animation in ${spec.clip.glb}`);

  info.duration = source.duration;
  let t = spec.time ?? (spec.progress != null ? spec.progress * source.duration : Math.max(0, source.duration - 1));
  t = THREE.MathUtils.clamp(t, 0, source.duration);
  info.time = t;

  let bodyTracks = source.tracks.filter((tr) => !tr.name.includes('PROP'));
  const mixer = new THREE.AnimationMixer(avatar.skeleton.bones[0]);

  // During basic animations a held item's own clip drives the right hand (its grip),
  // replacing the body clip's right-hand tracks.
  if (spec.clip.basic && spec.handheld) {
    const grip = (await loadGltf(spec.handheld)).animations[0];
    const gripTracks = grip ? grip.tracks.filter((tr) => tr.name.includes('RightHand')) : [];
    if (gripTracks.length) {
      bodyTracks = bodyTracks.filter((tr) => !tr.name.includes('RightHand'));
      mixer.clipAction(new THREE.AnimationClip('grip', grip.duration, gripTracks)).play();
    }
  }

  const action = mixer.clipAction(new THREE.AnimationClip(source.name, source.duration, bodyTracks));
  action.setLoop(THREE.LoopOnce, 1);
  action.clampWhenFinished = true;
  action.play();
  mixer.setTime(t);

  const [eyes, mouth] = faceOffsets(source.tracks.find((tr) => tr.name === 'FACE_EXPRESSIONS.quaternion'), t);
  avatar.eyesMaterial.map?.offset.set(eyes, 0);
  avatar.mouthMaterial.map?.offset.set(mouth, 0);

  // Win-animation assets can ship props (chairs, ...) animated by their own tracks.
  const propTracks = source.tracks.filter((tr) => tr.name.includes('PROP') && !tr.name.includes('Group'));
  const propTexture = await toonTexture(spec.clip.texture);
  const props = [];
  gltf.scene.traverse((o) => {
    if (o.type === 'Mesh' && o.name.includes('PROP')) props.push(o);
  });
  for (const original of props) {
    const prop = original.clone();
    prop.material = toonMaterial(propTexture, { skinned: false });
    avatar.group.add(prop);
    const ownTracks = propTracks.filter((tr) => THREE.PropertyBinding.parseTrackName(tr.name).nodeName === prop.name);
    const propMixer = new THREE.AnimationMixer(prop);
    const propAction = propMixer.clipAction(new THREE.AnimationClip('prop', source.duration, ownTracks));
    propAction.setLoop(THREE.LoopOnce, 1);
    propAction.clampWhenFinished = true;
    propAction.play();
    propMixer.setTime(t);
  }

  // Held items shrink away (morph weight 1) while a non-basic animation plays.
  for (const m of avatar.handhelds) {
    if (m.morphTargetInfluences?.length) m.morphTargetInfluences[0] = spec.clip.basic ? 0 : 1;
  }
  return info;
}

// --- Framing ----------------------------------------------------------------------

function posedBounds(group, skeleton) {
  group.updateMatrixWorld(true);
  skeleton.update();
  const box = new THREE.Box3();
  group.traverse((o) => {
    if (!o.visible || !(o.isMesh || o.isSkinnedMesh) || !o.geometry) return;
    if (o.isSkinnedMesh) {
      o.computeBoundingBox();
      box.union(o.boundingBox.clone().applyMatrix4(o.matrixWorld));
    } else {
      o.geometry.computeBoundingBox();
      box.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld));
    }
  });
  return box;
}

function placeCamera(camera, spec, box) {
  const c = spec.camera;
  const halfTan = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  let centerX, centerY, height;
  if (c.mode === 'fit') {
    const size = box.getSize(new THREE.Vector3());
    centerX = (box.min.x + box.max.x) / 2;
    centerY = (box.min.y + box.max.y) / 2;
    height = Math.max(size.y, size.x / camera.aspect) * (1 + 2 * c.margin);
  } else {
    centerX = 0;
    centerY = c.centerY;
    height = c.height;
  }
  const front = c.mode === 'fit' ? box.max.z : 0;
  const distance = height / 2 / halfTan + front;
  camera.position.set(centerX, centerY, distance);
  camera.lookAt(centerX, centerY, 0);
  camera.updateProjectionMatrix();
}

// --- Entry point ------------------------------------------------------------------

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

window.renderAvatar = async (spec) => {
  const scene = new THREE.Scene();
  const avatar = await buildAvatar(spec);
  scene.add(avatar.group);
  const info = await applyClip(spec, avatar);
  const box = posedBounds(avatar.group, avatar.skeleton);

  renderer.setPixelRatio(spec.supersample);
  renderer.setSize(spec.width, spec.height, false);
  if (spec.background) renderer.setClearColor(new THREE.Color(spec.background), 1);
  else renderer.setClearColor(0x000000, 0);

  const camera = new THREE.PerspectiveCamera(spec.camera.fov, spec.width / spec.height, 0.05, 100);
  placeCamera(camera, spec, box);
  renderer.render(scene, camera);

  const png = await downscalePng(spec);
  scene.traverse((o) => o.material?.dispose?.());
  return { png, ...info, bounds: { min: box.min.toArray(), max: box.max.toArray() } };
};

// Render happens at width*supersample; scale down on a 2D canvas for smooth edges.
async function downscalePng(spec) {
  const out = document.createElement('canvas');
  out.width = spec.width;
  out.height = spec.height;
  const ctx = out.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(canvas, 0, 0, spec.width, spec.height);
  return out.toDataURL('image/png');
}

window.rendererReady = true;
