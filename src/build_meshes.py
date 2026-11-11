import trimesh, numpy as np, json, base64, re, sys, os
import fast_simplification as fs

RAW = sys.argv[1]
names = dict(l.rstrip('\n').split('\t') for l in open(sys.argv[2]))
sel = open(sys.argv[3]).read().split()
OUT = sys.argv[4]

# ---- alignment: BodyParts3D (mm; +x subject left, -y forward, +z up) -> MediaPipe canonical face (cm; +x left, +y up, +z forward)
X0 = -0.6
SX, SY, SZ = 1.06, 1.24, 1.06   # SY applies below eye level and brings the bony chin to about 0.7 cm inside the reference chin
S_TOP = 1.06
DZ_INC = -6.312          # upper incisor edge, cm below the eye centre in the source data
MOUTH_Y = -4.2
S_MID = (2.62 - MOUTH_Y) / 6.312
S_LOW = 1.40


def load(i):
    m = trimesh.load(f'{RAW}/{i}.stl', process=True)
    return np.asarray(m.vertices, dtype=np.float64), np.asarray(m.faces, dtype=np.int64)


def simp(v, f, target):
    if len(f) <= target:
        return v, f
    red = 1.0 - target / len(f)
    v2, f2 = fs.simplify(v.astype(np.float32), f.astype(np.uint32), target_reduction=red)
    return np.asarray(v2, dtype=np.float64), np.asarray(f2, dtype=np.int64)


def area(v, f):
    a = v[f[:, 1]] - v[f[:, 0]]; b = v[f[:, 2]] - v[f[:, 0]]
    return 0.5 * np.linalg.norm(np.cross(a, b), axis=1).sum()


def classify(i):
    n = names[i]
    if 'tooth' in n:
        return 'skull', ('lower' in n)
    if n == 'mandible':
        return 'skull', True
    if re.search(r'bone|ethmoid|vomer|maxilla|concha|nasal cartilages', n) and not re.search('metacarpal', n):
        return 'skull', False
    if n == 'eyeball':
        return 'eyes', False
    if re.search(r'frontalis|occipitalis|temporoparietalis|orbicularis|corrugator|levator|zygomaticus|depressor|mentalis|buccinator|risorius|procerus|nasalis|masseter|temporalis', n):
        return 'muscles', bool(re.search(r'mentalis|depressor labii|depressor anguli', n))
    if re.search(r'metacarpal|phalanx|scaphoid|lunate|triquetral|pisiform|trapezium|trapezoid|capitate|hamate', n):
        return 'hand', False
    if re.search(r'ventricle|aqueduct|septum|habenula|pineal|tuber|geniculate|colliculus|caudate|putamen|pallidus|amygdala|hippocampus\b|thalamus|hypothalamus', n):
        return None, False
    return 'brain', False


parts = {}
for i in sel:
    layer, jaw = classify(i)
    if layer is None:
        continue
    v, f = load(i)
    parts[i] = dict(name=names[i], layer=layer, jaw=jaw, v=v, f=f)

# eye reference
ev = parts['FMA12513']['v']
eye_c = np.array([X0, (ev[:, 1].min() + ev[:, 1].max()) / 2, (ev[:, 2].min() + ev[:, 2].max()) / 2])
cornea_y = ev[:, 1].min()
print('eye centre', eye_c, 'cornea y', cornea_y)
# canonical anchors: eye centre height 2.62, cornea depth 4.1
ANCH_Y, ANCH_Z = 2.62, 4.1


def to_canon(p):
    q = np.empty_like(p)
    q[:, 0] = (p[:, 0] - X0) * 0.1 * SX
    dz = (p[:, 2] - eye_c[2]) * 0.1
    # Piecewise vertical map. The reference skull has a short lower face, and most of the shortfall is between the teeth and the chin:
    # eyes -> upper incisor edge lands on the lip line (y = MOUTH_Y); incisor edge -> chin lands about 1.2 cm inside the reference chin.
    y_mid = np.where(dz < 0, dz * S_MID, dz * S_TOP)
    q[:, 1] = np.where(dz < DZ_INC, DZ_INC * S_MID + (dz - DZ_INC) * S_LOW, y_mid) + ANCH_Y
    q[:, 2] = -(p[:, 1] - cornea_y) * 0.1 * SZ + ANCH_Z
    return q


budget = dict(skull=64000, brain=52000, muscles=30000, eyes=1800)
tot_area = {}
for p in parts.values():
    if p['layer'] in budget:
        p['area'] = area(p['v'], p['f'])
        tot_area[p['layer']] = tot_area.get(p['layer'], 0) + p['area']

groups = {}
labels_src = {}
for i, p in parts.items():
    L = p['layer']
    if L == 'hand':
        continue
    target = int(max(120, budget[L] * p['area'] / tot_area[L]))
    if 'tooth' in p['name']:
        target = 140
    v, f = simp(p['v'], p['f'], target)
    v = to_canon(v)
    p['cv'], p['cf'] = v, f
    key = L + ('_jaw' if p['jaw'] else '_lip' if p['name'] == 'orbicularis oris' else '')   # the lip ring is kept apart so its lower half can follow the jaw
    groups.setdefault(key, []).append((v, f))


def merge(lst):
    vs, fs_, off = [], [], 0
    for v, f in lst:
        vs.append(v); fs_.append(f + off); off += len(v)
    return np.vstack(vs), np.vstack(fs_)


blob = bytearray()
meta = dict(meshes={}, labels=[], hand={}, mouthY=MOUTH_Y)


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
    return dict(vo=vo, nv=int(len(v)), io=io, ni=int(f.size), it=it, lo=[round(float(x), 4) for x in lo], hi=[round(float(x), 4) for x in hi])


for key, lst in groups.items():
    v, f = merge(lst)
    meta['meshes'][key] = pack(v, f)
    print(key, len(v), len(f))

# jaw pivot from mandible condyles (canonical coords)
mv = parts['FMA52748']['cv']
piv = []
for side in (-1, 1):
    s = mv[(mv[:, 0] * side > 0) & (mv[:, 2] < np.percentile(mv[:, 2], 25))]
    piv.append(s[np.argmax(s[:, 1])])
pivot = (piv[0] + piv[1]) / 2
meta['jawPivot'] = [round(float(x), 3) for x in pivot]
print('condyles', piv, 'chin', mv[np.argmin(mv[:, 1])])


# ---- labels
def anchor(ids, side=0, mode='front'):
    vs = np.vstack([parts[i]['cv'] for i in ids if i in parts])
    if side:
        vs = vs[vs[:, 0] * side > 0]
    c = vs.mean(0)
    if mode == 'centroid':
        d = np.linalg.norm(vs - c, axis=1); return vs[np.argmin(d)]
    if mode == 'side':
        score = np.abs(vs[:, 0]) - 0.6 * np.linalg.norm(vs[:, 1:] - c[1:], axis=1)
    else:
        score = vs[:, 2] - 0.6 * np.linalg.norm(vs[:, :2] - c[:2], axis=1)
    return vs[np.argmax(score)]


def find(rx):
    return [i for i, p in parts.items() if re.search(rx, p['name'])]


LAB = [
    ('Frontal bone', 'skull', find(r'^frontal bone'), 1, 'front', False),
    ('Parietal bone', 'skull', find(r'parietal bone'), -1, 'side', False),
    ('Temporal bone', 'skull', find(r'temporal bone'), -1, 'side', False),
    ('Occipital bone', 'skull', find(r'occipital bone'), -1, 'side', False),
    ('Nasal bone', 'skull', find(r'nasal bone'), 1, 'front', False),
    ('Zygomatic bone (cheekbone)', 'skull', find(r'zygomatic bone'), -1, 'front', False),
    ('Maxilla (upper jaw)', 'skull', find(r'maxilla'), -1, 'front', False),
    ('Mandible (lower jaw)', 'skull', find(r'^mandible'), 1, 'front', True),
    ('Teeth', 'skull', find(r'upper .*incisor'), 1, 'front', False),
    ('Frontal lobe', 'brain', find(r'(superior|middle) frontal gyrus|orbital gyri'), 1, 'front', False),
    ('Parietal lobe', 'brain', find(r'postcentral|supramarginal|angular|parietal lobule'), -1, 'side', False),
    ('Temporal lobe', 'brain', find(r'temporal gyrus'), -1, 'side', False),
    ('Occipital lobe', 'brain', find(r'occipital lobe'), -1, 'side', False),
    ('Cerebellum', 'brain', find(r'cerebellum'), -1, 'side', False),
    ('Pons (brainstem)', 'brain', find(r'^pons'), 1, 'front', False),
    ('Medulla oblongata', 'brain', find(r'medulla'), -1, 'front', False),
    ('Frontalis', 'muscles', find(r'frontalis'), -1, 'front', False),
    ('Temporalis', 'muscles', find(r'temporalis'), -1, 'side', False),
    ('Orbicularis oculi', 'muscles', find(r'orbital part of .* orbicularis oculi'), -1, 'front', False),
    ('Nasalis', 'muscles', find(r'nasalis'), 1, 'front', False),
    ('Zygomaticus major', 'muscles', find(r'zygomaticus major'), -1, 'front', False),
    ('Masseter', 'muscles', find(r'superficial part of .* masseter'), -1, 'side', False),
    ('Orbicularis oris', 'muscles', find(r'orbicularis oris'), 1, 'front', False),
    ('Depressor anguli oris', 'muscles', find(r'depressor anguli oris'), -1, 'front', True),
    ('Mentalis', 'muscles', find(r'mentalis'), 1, 'front', True),
    ('Eyeball', 'eyes', find(r'eyeball'), -1, 'front', False),
]
for name, layer, ids, side, mode, jaw in LAB:
    assert ids, name
    a = anchor(ids, side, mode)
    meta['labels'].append(dict(name=name, layer=layer, jaw=jaw, p=[round(float(x), 2) for x in a]))

# ---- hand (right hand template, mm)
H = {i: p for i, p in parts.items() if p['layer'] == 'hand'}
carp_ids = [i for i, p in H.items() if not re.search('metacarpal|phalanx', p['name'])]
carp_c = np.vstack([H[i]['v'] for i in carp_ids]).mean(0)


def ends(v):
    c = v.mean(0)
    u, s, vt = np.linalg.svd(v - c, full_matrices=False)
    ax = vt[0]; t = (v - c) @ ax
    a = c + ax * np.percentile(t, 1.5); b = c + ax * np.percentile(t, 98.5)
    if np.linalg.norm(a - carp_c) > np.linalg.norm(b - carp_c):
        a, b = b, a
    return a, b


FING = ['thumb', 'index finger', 'middle finger', 'ring finger', 'little finger']
ORD = ['first', 'second', 'third', 'fourth', 'fifth']
bone = {}
for fi, (fn, on) in enumerate(zip(FING, ORD)):
    def one(rx):
        r = [i for i, p in H.items() if re.search(rx, p['name'])]
        assert len(r) == 1, (rx, r); return r[0]
    bone[(fi, 'meta')] = one(f'right {on} metacarpal')
    bone[(fi, 'prox')] = one(f'proximal phalanx of right {fn}$')
    bone[(fi, 'dist')] = one(f'distal phalanx of right {fn}$')
    if fi:
        bone[(fi, 'mid')] = one(f'middle phalanx of right {fn}$')
E = {k: ends(H[i]['v']) for k, i in bone.items()}
T5 = E[(1, 'meta')][1]; T9 = E[(2, 'meta')][1]; T13 = E[(3, 'meta')][1]; T17 = E[(4, 'meta')][1]
lun = H[[i for i in carp_ids if 'lunate' in H[i]['name']][0]]['v'].mean(0)
sca = H[[i for i in carp_ids if 'scaphoid' in H[i]['name']][0]]['v'].mean(0)
T0 = (lun + sca) / 2
T0 = T0 + (T0 - T9) / np.linalg.norm(T0 - T9) * 6.0   # wrist landmark sits a little proximal to the carpal row
u_t = (T5 - T17) / np.linalg.norm(T5 - T17)
print('hand T0', T0, 'T5', T5, 'T17', T17, 'len0-9', np.linalg.norm(T9 - T0))

# landmark index pairs for free bones
PAIR = {(0, 'meta'): (1, 2), (0, 'prox'): (2, 3), (0, 'dist'): (3, 4)}
for fi in range(1, 5):
    b = 5 + (fi - 1) * 4
    PAIR[(fi, 'prox')] = (b, b + 1); PAIR[(fi, 'mid')] = (b + 1, b + 2); PAIR[(fi, 'dist')] = (b + 2, b + 3)

free = []
for k, (a, b) in PAIR.items():
    i = bone[k]
    v, f = simp(H[i]['v'], H[i]['f'], 420 if k[1] != 'dist' else 260)
    p0, p1 = E[k]
    ln = np.linalg.norm(p1 - p0); y = (p1 - p0) / ln
    x = u_t - (u_t @ y) * y; x /= np.linalg.norm(x); z = np.cross(x, y)
    loc = np.stack([(v - p0) @ x, (v - p0) @ y, (v - p0) @ z], 1)
    d = pack(loc, f); d.update(a=a, b=b, len=round(float(ln), 2), name=names[i])
    free.append(d)
# palm group: carpals + metacarpals 2..5, in template mm relative to T0
pl = []
for i in carp_ids + [bone[(fi, 'meta')] for fi in range(1, 5)]:
    v, f = simp(H[i]['v'], H[i]['f'], 420)
    pl.append((v - T0, f))
pv, pf = merge(pl)
n_t = np.cross(T5 - T0, T17 - T0); n_t /= np.linalg.norm(n_t)
meta['hand'] = dict(free=free, palm=pack(pv, pf), t5=[float(x) for x in T5 - T0], t17=[float(x) for x in T17 - T0], nt=[float(x) for x in n_t])
print('palm', len(pv), len(pf), 'free tris', sum(d['ni'] // 3 for d in free))

open(OUT, 'w').write('window.XRAY_META=' + json.dumps(meta, separators=(',', ':')) + ';\nwindow.XRAY_B64="' + base64.b64encode(bytes(blob)).decode() + '";\n')
print('blob MB', len(blob) / 1e6, 'file MB', os.path.getsize(OUT) / 1e6)
