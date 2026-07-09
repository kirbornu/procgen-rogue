#!/usr/bin/env python3
"""Noise Lab export. Standard library only.
generate(seed) -> 2D list of brightness in [0, 1] (rows of length = size).
generate(0) reproduces the Noise Lab view; other seeds reseed the whole stack.
"""
import math, json

CONFIG = json.loads(r'''
{
  "app": "noise-lab",
  "version": 3,
  "res": 128,
  "mode": "tiles",
  "water": 0,
  "wall": 0.4,
  "cave": 2,
  "layers": [
    {
      "on": true,
      "noise": "worley",
      "seed": 162841,
      "scale": 9,
      "oct": 8,
      "lac": 2.45,
      "per": 0.32,
      "ridged": true,
      "warp": 0.2,
      "warpF": 1,
      "blend": "normal",
      "weight": 1,
      "op": {
        "gain": 0.65,
        "offset": 0.44,
        "gamma": 2.25,
        "invert": true
      },
      "geom": {
        "on": false,
        "shape": "rect",
        "cmp": "below",
        "thr": 0.35,
        "minSize": 0
      },
      "mask": {
        "on": true,
        "low": 0,
        "high": 1,
        "feather": 0.08
      }
    },
    {
      "on": true,
      "noise": "value",
      "seed": 753815,
      "scale": 8,
      "oct": 4,
      "lac": 2.35,
      "per": 0.34,
      "ridged": false,
      "warp": 2,
      "warpF": 0.3,
      "blend": "subtract",
      "weight": 1,
      "op": {
        "gain": 1.15,
        "offset": 0.06,
        "gamma": 2.3,
        "invert": true
      },
      "geom": {
        "on": false,
        "shape": "rect",
        "cmp": "above",
        "thr": 0.6,
        "minSize": 12
      },
      "mask": {
        "on": true,
        "low": 0,
        "high": 0.42,
        "feather": 0.08
      }
    },
    {
      "on": true,
      "noise": "value",
      "seed": 770605,
      "scale": 24,
      "oct": 5,
      "lac": 1.8,
      "per": 0.54,
      "ridged": false,
      "warp": 2,
      "warpF": 1.1,
      "blend": "min",
      "weight": 1,
      "op": {
        "gain": 1,
        "offset": 0,
        "gamma": 1,
        "invert": false
      },
      "geom": {
        "on": true,
        "shape": "rect",
        "cmp": "below",
        "thr": 0.36,
        "minSize": 0
      },
      "mask": {
        "on": false,
        "low": 0,
        "high": 1,
        "feather": 0.08
      }
    },
    {
      "on": true,
      "noise": "value",
      "seed": 335433,
      "scale": 5,
      "oct": 1,
      "lac": 3.5,
      "per": 0.36,
      "ridged": false,
      "warp": 2,
      "warpF": 1.5,
      "blend": "max",
      "weight": 1,
      "op": {
        "gain": 1.4,
        "offset": 0.1,
        "gamma": 4,
        "invert": false
      },
      "geom": {
        "on": false,
        "shape": "rect",
        "cmp": "above",
        "thr": 0.6,
        "minSize": 12
      },
      "mask": {
        "on": false,
        "low": 0,
        "high": 0.3,
        "feather": 0.08
      }
    }
  ]
}
''')

M32 = 0xFFFFFFFF
def _imul(a, b): return ((a & M32) * (b & M32)) & M32
def _hash2(x, y, seed):
    h = (seed ^ _imul(x, 0x1657f5) ^ _imul(y, 0x27d4eb2f)) & M32
    h = _imul(h ^ (h >> 13), 0x5bd1e995)
    h = (h ^ (h >> 15)) & M32
    return h / 4294967296.0
def _fade(t): return t * t * t * (t * (t * 6 - 15) + 10)
def _lerp(a, b, t): return a + (b - a) * t
def _clamp01(v): return 0.0 if v < 0 else 1.0 if v > 1 else v
def _value(x, y, seed):
    x0 = math.floor(x); y0 = math.floor(y)
    u = _fade(x - x0); v = _fade(y - y0)
    a = _lerp(_hash2(x0, y0, seed), _hash2(x0 + 1, y0, seed), u)
    b = _lerp(_hash2(x0, y0 + 1, seed), _hash2(x0 + 1, y0 + 1, seed), u)
    return _lerp(a, b, v) * 2 - 1
def _grad_dot(ix, iy, x, y, seed):
    ang = _hash2(ix, iy, seed) * 6.28318530718
    return math.cos(ang) * (x - ix) + math.sin(ang) * (y - iy)
def _perlin(x, y, seed):
    x0 = math.floor(x); y0 = math.floor(y)
    u = _fade(x - x0); v = _fade(y - y0)
    a = _lerp(_grad_dot(x0, y0, x, y, seed), _grad_dot(x0 + 1, y0, x, y, seed), u)
    b = _lerp(_grad_dot(x0, y0 + 1, x, y, seed), _grad_dot(x0 + 1, y0 + 1, x, y, seed), u)
    return _lerp(a, b, v) * 1.41421356
def _worley(x, y, seed):
    xi = math.floor(x); yi = math.floor(y); f1 = float("inf")
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = xi + ox; cy = yi + oy
            px = cx + _hash2(cx, cy, seed)
            py = cy + _hash2(cx, cy, seed ^ 0x9e3779b9)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < f1: f1 = d
    return min(1.0, math.sqrt(f1)) * 2 - 1
def _base(x, y, seed, kind):
    if kind == "perlin": return _perlin(x, y, seed)
    if kind == "worley": return _worley(x, y, seed)
    return _value(x, y, seed)
def _fbm(x, y, ly):
    amp = 1.0; freq = 1.0; s = 0.0; norm = 0.0
    for o in range(int(ly["oct"])):
        n = _base(x * freq, y * freq, (ly["seed"] + o * 1013) & M32, ly["noise"])
        if ly["ridged"]:
            n = 1 - abs(n); n = n * n * 2 - 1
        s += n * amp; norm += amp; amp *= ly["per"]; freq *= ly["lac"]
    return s / (norm if norm else 1)
def _sample(x, y, ly):
    if ly["warp"] > 0:
        qx = _fbm(x + 4.7, y + 2.3, ly); qy = _fbm(x + 1.9, y + 8.1, ly)
        x += ly["warp"] * qx; y += ly["warp"] * qy
    return _fbm(x, y, ly)
def _smoothstep(e0, e1, x):
    if e0 == e1: return 0.0 if x < e0 else 1.0
    t = _clamp01((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t)
def _mask_factor(a, m):
    lo = m["low"]; hi = m["high"]
    if lo > hi: lo, hi = hi, lo
    f = m["feather"]
    if f <= 0: return 1.0 if (lo <= a <= hi) else 0.0
    return _smoothstep(lo - f, lo, a) * (1 - _smoothstep(hi, hi + f, a))
def _blend(mode, a, v, w):
    if mode == "add": r = a + v * w
    elif mode == "subtract": r = a - v * w
    elif mode == "multiply": r = a * (1 - w + v * w)
    elif mode == "screen": r = a + (1 - (1 - a) * (1 - v) - a) * w
    elif mode == "max": r = a + (max(a, v) - a) * w
    elif mode == "min": r = a + (min(a, v) - a) * w
    else: r = a + (v - a) * w
    return _clamp01(r)
def _apply_ops(fld, op):
    inv = op["invert"]; gain = op["gain"]; off = op["offset"]; gamma = op["gamma"]
    for k in range(len(fld)):
        v = fld[k]
        if inv: v = 1 - v
        v = _clamp01(v * gain + off)
        if gamma != 1: v = v ** gamma
        fld[k] = v
def _geometrize(fld, N, g):
    above = g["cmp"] == "above"; thr = g["thr"]; min_size = int(g["minSize"])
    binm = [1 if ((fld[k] > thr) if above else (fld[k] < thr)) else 0 for k in range(N * N)]
    out = list(fld); visited = [0] * (N * N)
    for sj in range(N):
        for si in range(N):
            start = sj * N + si
            if not binm[start] or visited[start]: continue
            minx = maxx = si; miny = maxy = sj; area = 0
            stack = [start]; visited[start] = 1
            while stack:
                c = stack.pop(); area += 1
                cx = c % N; cy = c // N
                if cx < minx: minx = cx
                if cx > maxx: maxx = cx
                if cy < miny: miny = cy
                if cy > maxy: maxy = cy
                if cx > 0 and binm[c - 1] and not visited[c - 1]: visited[c - 1] = 1; stack.append(c - 1)
                if cx < N - 1 and binm[c + 1] and not visited[c + 1]: visited[c + 1] = 1; stack.append(c + 1)
                if cy > 0 and binm[c - N] and not visited[c - N]: visited[c - N] = 1; stack.append(c - N)
                if cy < N - 1 and binm[c + N] and not visited[c + N]: visited[c + N] = 1; stack.append(c + N)
            if area < min_size: continue
            if g["shape"] == "ellipse":
                cx0 = (minx + maxx) / 2; cy0 = (miny + maxy) / 2
                rx = max(0.5, (maxx - minx) / 2); ry = max(0.5, (maxy - miny) / 2)
                for y in range(miny, maxy + 1):
                    for x in range(minx, maxx + 1):
                        if ((x - cx0) / rx) ** 2 + ((y - cy0) / ry) ** 2 <= 1: out[y * N + x] = thr
            else:
                for y in range(miny, maxy + 1):
                    for x in range(minx, maxx + 1): out[y * N + x] = thr
    return out
def _layer_field(ly, N, seed_off):
    ly = dict(ly); ly["seed"] = (ly["seed"] + seed_off) & M32
    fld = [0.0] * (N * N); mn = float("inf"); mx = float("-inf"); f = ly["scale"]
    for j in range(N):
        for i in range(N):
            v = _sample((i / N) * f, (j / N) * f, ly)
            fld[j * N + i] = v
            if v < mn: mn = v
            if v > mx: mx = v
    rng = (mx - mn) or 1
    for k in range(len(fld)): fld[k] = (fld[k] - mn) / rng
    _apply_ops(fld, ly["op"])
    if ly["geom"]["on"]: fld = _geometrize(fld, N, ly["geom"])
    return fld
def generate(seed=0, size=None):
    """Return a 2D list (rows) of brightness in [0, 1]."""
    N = int(size if size is not None else CONFIG["res"])
    acc = None
    for ly in CONFIG["layers"]:
        if not ly["on"]: continue
        fld = _layer_field(ly, N, int(seed))
        if acc is None:
            acc = fld; continue
        w = ly["weight"]; use_mask = ly["mask"]["on"]
        for k in range(N * N):
            wk = w * _mask_factor(acc[k], ly["mask"]) if use_mask else w
            if wk > 0: acc[k] = _blend(ly["blend"], acc[k], fld[k], wk)
    if acc is None: acc = [0.0] * (N * N)
    mn = min(acc); mx = max(acc); rng = (mx - mn) or 1
    acc = [(v - mn) / rng for v in acc]
    return [acc[j * N:(j + 1) * N] for j in range(N)]
def save_pgm(grid, path="noise.pgm"):
    N = len(grid); W = len(grid[0]) if N else 0
    with open(path, "wb") as fh:
        fh.write(("P5\n%d %d\n255\n" % (W, N)).encode())
        fh.write(bytes(max(0, min(255, int(v * 255))) for row in grid for v in row))
if __name__ == "__main__":
    import sys
    s = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    g = generate(s)
    print("seed=%d  size=%dx%d" % (s, len(g[0]), len(g)))
    save_pgm(g); print("saved noise.pgm")
