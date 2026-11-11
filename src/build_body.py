"""Pack the body skeleton and organs for the full-body mode.

Body frame (mm): +X subject's left, +Y up, +Z forward. Each part is stored in the local frame it is posed in:
  torso  - relative to the midpoint of the hip joints; posed by one affine map from shoulders and hips
  seg    - origin at joint A, +Y along the bone towards joint B; posed between two tracked joints
  tri    - relative to an origin joint; posed by an affine map from three tracked points (hand, foot)
"""
import trimesh, numpy as np, json, base64, re, sys, os
import fast_simplification as fs

RAW, PARTS, SEL, OUT = sys.argv[1:5]
names = dict(l.rstrip('\n').split('\t') for l in open(PARTS))
inv = {v: k for k, v in names.items()}
sel = open(SEL).read().split()


def conv(p):
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1)


def load(i):
    m = trimesh.load(f'{RAW}/{i}.stl', process=True)
    return conv(np.asarray(m.vertices, dtype=np.float64)), np.asarray(m.faces, dtype=np.int64)


def simp(v, f, target):
    if len(f) <= target:
        return v, f
    v2, f2 = fs.simplify(v.astype(np.float32), f.astype(np.uint32), target_reduction=1.0 - target / len(f))
    return np.asarray(v2, dtype=np.float64), np.asarray(f2, dtype=np.int64)


def merge(lst):
    vs, fs_, off = [], [], 0
    for v, f in lst:
        vs.append(v); fs_.append(f + off); off += len(v)
    return np.vstack(vs), np.vstack(fs_)


blob = bytearray()


def pack(v, f):
    lo = v.min(0); hi = v.max(0)
    q = np.round((v - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype('<u2')
    while len(blob) % 4:
        blob.append(0)
    vo = len(blob); blob.extend(q.tobytes())
    while len(blob) % 4:
        blob.append(0)
    io = len(blob)
    if len(v) < 65536:
        blob.extend(f.astype('<u2').tobytes()); it = 16
    else:
        blob.extend(f.astype('<u4').tobytes()); it = 32
    return dict(vo=vo, nv=int(len(v)), io=io, ni=int(f.size), it=it, lo=[round(float(x), 3) for x in lo], hi=[round(float(x), 3) for x in hi])


RAWV = {}


def V(name):
    i = inv[name]
    if i not in RAWV:
        RAWV[i] = load(i)
    return RAWV[i][0]


def cen_q(v, axis, lo, hi):
    t = v[:, axis]; a, b = np.quantile(t, lo), np.quantile(t, hi)
    return v[(t >= a) & (t <= b)].mean(0)


J = {}
for s in ('left', 'right'):
    hum, fem, tib = V(f'{s} humerus'), V(f'{s} femur'), V(f'{s} tibia')
    J[f'sh_{s}'] = cen_q(hum, 1, 0.90, 1.0)
    J[f'el_{s}'] = cen_q(hum, 1, 0.0, 0.05)
    J[f'wr_{s}'] = (cen_q(V(f'{s} radius'), 1, 0.0, 0.04) + cen_q(V(f'{s} ulna'), 1, 0.0, 0.04)) / 2
    top = fem[fem[:, 1] >= np.quantile(fem[:, 1], 0.91)]
    med = top[np.abs(top[:, 0]) <= np.median(np.abs(top[:, 0]))]
    J[f'hip_{s}'] = med.mean(0)
    J[f'kn_{s}'] = (cen_q(fem, 1, 0.0, 0.05) + cen_q(tib, 1, 0.95, 1.0)) / 2
    J[f'an_{s}'] = V(f'{s} talus').mean(0)
    J[f'heel_{s}'] = cen_q(V(f'{s} calcaneus'), 2, 0.0, 0.08)
    J[f'toe_{s}'] = cen_q(V(f'distal phalanx of {s} big toe'), 2, 0.9, 1.0)
    J[f'idx_{s}'] = cen_q(V(f'{s} second metacarpal bone'), 1, 0.0, 0.06)
    J[f'pky_{s}'] = cen_q(V(f'{s} fifth metacarpal bone'), 1, 0.0, 0.06)
ORIGIN = (J['hip_left'] + J['hip_right']) / 2
for k, v in J.items():
    print(k, np.round(v, 0))

# MediaPipe pose landmark indices
LM = dict(sh_left=11, sh_right=12, el_left=13, el_right=14, wr_left=15, wr_right=16, pky_left=17, pky_right=18, idx_left=19, idx_right=20,
          hip_left=23, hip_right=24, kn_left=25, kn_right=26, an_left=27, an_right=28, heel_left=29, heel_right=30, toe_left=31, toe_right=32)

parts, labels = [], []
used = set()


def take(rx, target):
    out = []
    for i in sel:
        n = names[i]
        if i in used or not re.search(rx, n):
            continue
        used.add(i)
        v, f = load(i)
        out.append(simp(v, f, target(n) if callable(target) else target))
    assert out, rx
    return merge(out)


def front_anchor(v, side=0):
    if side:
        v = v[v[:, 0] * side > 0]
    c = v.mean(0)
    return v[np.argmax(v[:, 2] - 0.6 * np.linalg.norm(v[:, :2] - c[:2], axis=1))]


def add_torso(pid, layer, rx, target, col=None, label=None, side=0):
    v, f = take(rx, target)
    v = v - ORIGIN
    d = dict(id=pid, kind='torso', layer=layer, mesh=pack(v, f))
    if col:
        d['col'] = col
    parts.append(d)
    if label:
        for name, lrx, ls in (label if isinstance(label, list) else [(label, None, side)]):
            src = v if lrx is None else merge([(load(i)[0] - ORIGIN, np.zeros((0, 3), int)) for i in sel if re.search(lrx, names[i])])[0]
            labels.append(dict(name=name, layer=layer, part=len(parts) - 1, p=[round(float(x), 1) for x in front_anchor(src, ls)]))
    print(pid, len(v), len(f))


def add_seg(pid, rx, target, a, b, umode, label=None):
    v, f = take(rx, target)
    A, B = J[a], J[b]
    ln = np.linalg.norm(B - A); y = (B - A) / ln
    u = np.array([1.0, 0, 0]); x = u - (u @ y) * y; x /= np.linalg.norm(x); z = np.cross(x, y)
    loc = np.stack([(v - A) @ x, (v - A) @ y, (v - A) @ z], 1)
    parts.append(dict(id=pid, kind='seg', layer='skull', mesh=pack(loc, f), a=LM[a], b=LM[b], len=round(float(ln), 2), u=umode))
    for name, lrx in (label or []):
        src = merge([(load(i)[0], np.zeros((0, 3), int)) for i in sel if re.search(lrx, names[i])])[0]
        c = src.mean(0) - A
        labels.append(dict(name=name, layer='skull', part=len(parts) - 1, p=[round(float(c @ x), 1), round(float(c @ y), 1), round(float(c @ z), 1)]))
    print(pid, len(v), len(f), 'len', round(ln))


def add_tri(pid, rx, target, o, i, j, label):
    v, f = take(rx, target)
    O = J[o]
    parts.append(dict(id=pid, kind='tri', layer='skull', mesh=pack(v - O, f), o=LM[o], i=LM[i], j=LM[j],
                      ti=[float(x) for x in J[i] - O], tj=[float(x) for x in J[j] - O]))
    c = (v - O).mean(0)
    labels.append(dict(name=label, layer='skull', part=len(parts) - 1, p=[round(float(x), 1) for x in c]))
    print(pid, len(v), len(f))


def tb(n):   # triangle budget for torso bones
    if 'rib' in n: return 360
    if 'costal cartilage' in n: return 220
    if 'disk' in n: return 70
    if 'vertebra' in n: return 420
    if n == 'sacrum': return 1500
    if 'hip bone' in n: return 2600
    if 'scapula' in n: return 1500
    if 'clavicle' in n: return 500
    return 600


CERV = r'^atlas$|^axis$|(third|fourth|fifth|sixth|seventh) cervical vertebra$|intervertebral disk of (axis|(third|fourth|fifth|sixth|seventh) cervical vertebra)$'
# neck first so the torso pattern below does not swallow the cervical vertebrae
vN, fN = take(CERV, lambda n: 70 if 'disk' in n else 380)
C7 = V('seventh cervical vertebra').mean(0); ATLAS = V('atlas').mean(0)
lnN = np.linalg.norm(ATLAS - C7); yN = (ATLAS - C7) / lnN
xN = np.array([1.0, 0, 0]); xN = xN - (xN @ yN) * yN; xN /= np.linalg.norm(xN); zN = np.cross(xN, yN)
locN = np.stack([(vN - C7) @ xN, (vN - C7) @ yN, (vN - C7) @ zN], 1)
parts.append(dict(id='neck', kind='seg', layer='skull', mesh=pack(locN, fN), a='neck', b='atlas', len=round(float(lnN), 2), u='lat'))
labels.append(dict(name='Cervical vertebrae (neck)', layer='skull', part=0, p=[0, round(float(lnN / 2), 1), 0]))

add_torso('torso', 'skull', r'vertebra$|^sacrum$|intervertebral disk|\brib$|sternum|^manubrium$|xiphoid|costal cartilage|(left|right) (clavicle|scapula|hip bone)$', tb,
          label=[('Clavicle (collarbone)', r'left clavicle', 1), ('Scapula (shoulder blade)', r'right scapula', -1), ('Sternum (breastbone)', r'body of sternum', 0),
                 ('Ribs', r'(fifth|sixth|seventh) rib', 1), ('Lumbar vertebrae', r'(third|fourth) lumbar vertebra$', 0),
                 ('Hip bone (pelvis)', r'right hip bone', -1), ('Sacrum', r'^sacrum$', 0)])

for s in ('left', 'right'):
    lab = s == 'left'
    add_seg(f'upperarm_{s}', rf'^{s} humerus$', 1500, f'sh_{s}', f'el_{s}', 'arm', [('Humerus', 'left humerus')] if lab else None)
    add_seg(f'forearm_{s}', rf'^{s} (radius|ulna)$', 800, f'el_{s}', f'wr_{s}', 'arm', [('Radius', 'left radius'), ('Ulna', 'left ulna')] if lab else None)
    add_tri(f'hand_{s}', rf'^{s} (.*metacarpal bone|scaphoid|lunate|triquetral|pisiform|trapezium|trapezoid|capitate|hamate)$|phalanx of {s} (thumb|index finger|middle finger|ring finger|little finger)$',
            130, f'wr_{s}', f'idx_{s}', f'pky_{s}', 'Hand: carpals, metacarpals, phalanges')
    add_seg(f'thigh_{s}', rf'^{s} femur$', 1800, f'hip_{s}', f'kn_{s}', 'leg', [('Femur (thigh bone)', 'left femur')] if lab else None)
    add_seg(f'shank_{s}', rf'^{s} (tibia|fibula|patella)$', lambda n: 1200 if 'tibia' in n else 600 if 'fibula' in n else 220, f'kn_{s}', f'an_{s}', 'leg',
            [('Patella (kneecap)', 'left patella'), ('Tibia (shin bone)', 'left tibia'), ('Fibula', 'left fibula')] if lab else None)
    add_tri(f'foot_{s}', rf'^{s} (talus|calcaneus|cuboid bone|.*cuneiform bone|.*metatarsal bone)$|navicular bone of {s} foot|phalanx of {s} (big|second|third|fourth|little) toe$',
            150, f'heel_{s}', f'an_{s}', f'toe_{s}', 'Foot: tarsals, metatarsals, phalanges')
labels[:] = [l for l in labels if not (l['name'].startswith(('Hand:', 'Foot:')) and parts[l['part']]['id'].endswith('right'))]

ORG = [
    ('lungs', r'lobe of .*lung', 1500, ('#f3a6b4', '#ffb3c4'), 'Lungs', 1),
    ('airways', r'^trachea$|^bronchus$', 900, ('#bfe3ee', '#aee6ff'), 'Trachea (windpipe)', 0),
    ('heart', r'^wall of heart$|aorta$', lambda n: 4000 if 'heart' in n else 600, ('#c0392b', '#ff6b5e'), [('Heart', r'^wall of heart$', 0)], 0),
    ('liver', r'^liver$|^gallbladder$', lambda n: 3000 if n == 'liver' else 300, ('#8e4b32', '#e08a5a'), [('Liver', r'^liver$', -1)], 0),
    ('stomach', r'^stomach$|^esophagus$', lambda n: 1500 if n == 'stomach' else 500, ('#e2a07a', '#ffc08a'), [('Stomach', r'^stomach$', 1)], 0),
    ('spleen', r'^spleen$|^pancreas, nsn$', 800, ('#7d5a8c', '#c69be0'), [('Spleen', r'^spleen$', 1)], 0),
    ('kidneys', r'(left|right) (kidney|ureter|adrenal gland)$|^urinary bladder$', lambda n: 900 if 'kidney' in n else 600 if 'bladder' in n else 220, ('#9b6a4f', '#ffd27a'),
     [('Kidney', r'left kidney', 1), ('Urinary bladder', r'^urinary bladder$', 0)], 0),
    ('small_intestine', r'^duodenum$|^jejunum$|^ileum$', lambda n: 800 if n == 'duodenum' else 3500, ('#e7b9a6', '#ffcbb5'), [('Small intestine', r'^jejunum$', 0)], 0),
    ('colon', r'^colon, nsn$|^appendix$|^rectum$', lambda n: 4000 if 'colon' in n else 300, ('#c99477', '#f0b090'), [('Large intestine (colon)', r'^colon, nsn$', -1)], 0),
]
for pid, rx, target, col, label, side in ORG:
    add_torso(pid, 'organs', rx, target, col=list(col), label=label, side=side)

left = [names[i] for i in sel if i not in used]
print('unused:', left)

# head-build constants, to carry the top of the neck into the head's coordinate frame
ev = load(inv['eyeball'])[0]   # conv frame: Y up, Z forward
eye_y = (ev[:, 1].min() + ev[:, 1].max()) / 2; cornea_z = ev[:, 2].max()
dz = (ATLAS[1] - eye_y) * 0.1
atlas_canon = [float((ATLAS[0] + 0.6) * 0.1 * 1.06), float((dz * 1.12 if dz < 0 else dz * 1.06) + 2.62), float((ATLAS[2] - cornea_z) * 0.1 * 1.06 + 4.1)]

meta = dict(parts=parts, labels=labels,
            torso=dict(shL=[float(x) for x in J['sh_left'] - ORIGIN], shR=[float(x) for x in J['sh_right'] - ORIGIN],
                       hipL=[float(x) for x in J['hip_left'] - ORIGIN], hipR=[float(x) for x in J['hip_right'] - ORIGIN],
                       neck=[float(x) for x in C7 - ORIGIN]),
            head=dict(atlas=atlas_canon, earL=[7.664182, 0.673132, -2.435867], earR=[-7.664182, 0.673132, -2.435867], nose=[0, -1.126865, 7.475604]),
            joints={k: [round(float(x), 1) for x in v - ORIGIN] for k, v in J.items()}, lm=LM)
open(OUT, 'w').write('window.XRAY_BODY=' + json.dumps(meta, separators=(',', ':')) + ';\nwindow.XRAY_BODY_B64="' + base64.b64encode(bytes(blob)).decode() + '";\n')
print('atlas canon', np.round(atlas_canon, 2), 'tris', sum(p['mesh']['ni'] // 3 for p in parts), 'blob MB', len(blob) / 1e6, 'file MB', os.path.getsize(OUT) / 1e6)
