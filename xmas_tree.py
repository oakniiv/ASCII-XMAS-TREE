#!/usr/bin/env python3
import math, random, shutil, sys, time

TAU = math.tau
CYCLE = 20.0          # seconds per loop
FPS = 20
SPIN = 0.5            # radians / second
D = 3.0               # camera distance
CT, ST = math.cos(0.40), math.sin(0.40)      # camera tilt (looking down onto the presents)
LX, LY, LZ = -0.35, 0.75, -0.56              # light from upper-left-front (unit vector)
AMB = 0.22                                   # ambient light
STAR_R, STAR_T, STAR_Y = 0.095, 0.035, 1.05  # star radius, half-thickness, centre height

# colour sets, dark -> bright (xterm-256, deliberately muted)
GREENS = (22, 22, 22, 28, 28, 64, 65, 71, 108)
RED, GOLD, BLUE = (52, 88, 124, 160), (94, 136, 178, 222), (24, 25, 67, 110)
PLUM, TEAL = (53, 90, 96, 139), (23, 23, 30, 73)
SILVER, CREAM = (240, 246, 252, 231), (137, 180, 223, 230)
WARM = (160, 172, 178, 67, 133)              # fairy lights
BULBS = (160, 178, 28, 26, 166)              # 90s string lights: red gold green blue orange

SNOWMAN = (
    "    _____    ",
    "  __|___|__  ",
    "    (o o)    ",
    "    ( > )    ",
    " \\-(  :  )-/ ",
    "  (   :   )  ",
    " (    :    ) ",
    "  '-.___.-'  ",
)
FLOOR = ". _  .  ~ .   _ . "   # sparse, so it reads as soft snow rather than static
rng = random.Random(7)
NOISE = [rng.random() for _ in range(4096)]


def mat(chars, cols, cull=True, blink=False, falls=False):
    """Material: a dark->bright ramp of (char, colour) plus flags.
    cull = skip points facing away from the camera (solid objects)."""
    ramp = tuple((ch, cols[i * len(cols) // len(chars)]) for i, ch in enumerate(chars))
    return (ramp, cull, blink, falls)


FOLIAGE = mat(".:^vx%&W#", GREENS, cull=False)   # back needles show through gaps = depth
TRUNK = mat("||H##", (58, 94, 130), cull=False)
GARLAND = mat("-~~==$$", (94, 136, 178, 220))   # $ = glitter
STAR = mat("+x##@@@", (136, 172, 178, 220, 220, 229, 230))
BALLS = [mat(".:ooooOOOOO@", (a, a, b, b, c, c, c, d, d, d, d, hi))   # hi = small specular highlight
         for (a, b, c, d), hi in ((RED, 217), (GOLD, 230), (BLUE, 153), (PLUM, 182), (SILVER, 231))]
LIGHTS = [mat("*", (c,), cull=False, blink=True) for c in WARM]
GIFTS = (  # angle, distance from trunk, half width / height / depth, yaw, paper, ribbon
    (0.3, 0.50, 0.090, 0.072, 0.090, 0.5, RED, GOLD),
    (1.5, 0.52, 0.070, 0.100, 0.070, 1.1, BLUE, SILVER),
    (2.8, 0.49, 0.105, 0.055, 0.078, 0.2, GOLD, RED),
    (4.0, 0.51, 0.080, 0.080, 0.080, 0.9, PLUM, CREAM),
    (5.2, 0.50, 0.095, 0.062, 0.072, 1.4, TEAL, GOLD),
)


def radius(u):
    """Tree radius at u (0 = tip, 1 = bottom), with 5 sawtooth tiers."""
    return 0.01 + 0.46 * u * (0.72 + 0.28 * ((u * 5) % 1))


def sphere(pts, cx, cy, cz, r, n, t0, m):
    for i in range(n):                                      # Fibonacci lattice
        ny = 1 - (2 * i + 1) / n
        k, phi = math.sqrt(1 - ny * ny), i * 2.39996
        nx, nz = math.cos(phi) * k, math.sin(phi) * k
        pts.append((cx + nx * r, cy + ny * r, cz + nz * r, nx, ny, nz, t0, m, 0.0))


def gift(pts, a, dist, hx, hy, hz, yaw, paper, ribbon, t0, N=20, LID=0.008):
    """Gift box: 5 lit faces, an overhanging lid with a shadow under its lip, ribbon cross, bow."""
    px, pz = math.cos(a) * dist, math.sin(a) * dist
    c, s = math.cos(a + yaw), math.sin(a + yaw)
    body, band = mat("xxxx%%##", paper, falls=True), mat("::==++@@", ribbon, falls=True)

    def add(lx, ly, lz, nx, ny, nz, m, jit=0.0):            # box-local -> world
        pts.append((px + lx * c - lz * s, ly, pz + lx * s + lz * c,
                    nx * c - nz * s, ny, nx * s + nz * c, t0, m, jit))

    for i in range(N):
        for j in range(N):                                  # jittered grid = even coverage
            u, v = 2 * (i + rng.random()) / N - 1, 2 * (j + rng.random()) / N - 1
            tied = abs(u) < 0.17
            cross = tied or abs(v) < 0.17
            add(u * (hx + LID), 2 * hy + 0.004 * cross, v * (hz + LID), 0, 1, 0, band if cross else body)
            lid = v > 0.5                                   # top quarter of each side is the lid
            out = LID * lid + 0.004 * tied
            jit = 0.0 if tied else 0.12 if lid else -0.3 if v > 0.2 else 0.0
            m = band if tied else body
            for n in (-1, 1):
                add(u * hx, (v + 1) * hy, n * (hz + out), 0, 0, n, m, jit)
                add(n * (hx + out), (v + 1) * hy, u * hz, n, 0, 0, m, jit)
    r = min(hx, hz) * 0.3
    for k in (-1, 0, 1):                                    # bow: two loops and a knot
        q = r * (0.6 if k == 0 else 1)
        sphere(pts, px + k * r * c, 2 * hy + q * 0.8, pz + k * r * s, q, 50, t0, band)


def build():
    # point: (x, y, z, nx, ny, nz, appear_time, material, brightness jitter / blink phase)
    pts = []
    height = lambda u: 0.14 + (1 - u) * 0.86
    grow = lambda u: 0.5 + (1 - u) * 3.5                    # bottom (u=1) first, tip last

    for _ in range(300):                                    # trunk, 0-0.5s
        y, phi = rng.random() * 0.14, rng.random() * TAU
        c, s = math.cos(phi), math.sin(phi)
        pts.append((c * 0.05, y, s * 0.05, c, 0, s, y / 0.14 * 0.5, TRUNK, rng.uniform(-0.1, 0.1)))

    for _ in range(9000):                                   # foliage, 0.5-4s
        u, phi, deep = math.sqrt(rng.random()), rng.random() * TAU, rng.random()
        r = radius(u) * (1 - 0.4 * deep)
        c, s = math.cos(phi), math.sin(phi)
        # darker deep inside and at the top of each tier (shaded by the tier above)
        jit = rng.uniform(-0.15, 0.15) - 0.2 * deep + 0.25 * ((u * 5) % 1 - 0.6)
        pts.append((c * r, height(u), s * r, c * 0.87, 0.5, s * 0.87, grow(u), FOLIAGE, jit))

    for tier in range(1, 5):                                # baubles hang from the tier tips
        n = 2 * tier + 1
        for j in range(n):
            u = (tier + rng.uniform(0.6, 0.95)) / 5
            phi = (j + rng.uniform(-0.25, 0.25)) / n * TAU + tier
            r, br = radius(u) + 0.005, 0.03 + 0.004 * tier
            sphere(pts, math.cos(phi) * r, height(u) - br * 0.5, math.sin(phi) * r, br, 140,
                   grow(u), BALLS[(j + tier) % len(BALLS)])

    for i in range(1500):                                   # tinsel garland: a swagged tube, climbs 4-7s
        u = 0.04 + 0.96 * i / 1500
        phi = u * TAU * 5
        c, s = math.cos(phi), math.sin(phi)
        r, y = 0.02 + 0.44 * u, height(u) - 0.04 * abs(math.sin(phi * 1.5))   # 3 swags per turn
        for a in (-1.0, 0.0, 1.0):                          # 3 strands around the tube
            k, ny = math.cos(a), math.sin(a)
            pts.append((c * (r + 0.016 * k), y + 0.016 * ny, s * (r + 0.016 * k), c * k, ny, s * k,
                        4 + (1 - u) * 3, GARLAND, rng.uniform(-0.12, 0.12)))

    for _ in range(160):                                    # blinking fairy lights, climb with garland
        u, phi = math.sqrt(rng.random()), rng.random() * TAU
        r = radius(u) * 1.05
        pts.append((math.cos(phi) * r, height(u), math.sin(phi) * r, 0, 0, 0,
                    4 + (1 - u) * 3, rng.choice(LIGHTS), rng.random() + 0.01))

    # star: 5 points, ridged (thick in the middle, sharp at the edges) -> 10 flat facets per side
    V = [(math.cos(a) * r, math.sin(a) * r) for k in range(10)
         for a, r in [(math.pi / 2 + k * math.pi / 5, STAR_R * (1 if k % 2 == 0 else 0.42))]]
    for k in range(10):
        (x1, y1), (x2, y2) = V[k], V[(k + 1) % 10]
        for side in (-1, 1):
            nx, ny, nz = STAR_T * (y2 - y1), STAR_T * (x1 - x2), side * (x1 * y2 - y1 * x2)
            ln = math.sqrt(nx * nx + ny * ny + nz * nz)
            for _ in range(60):
                a, b = rng.random(), rng.random()
                if a + b > 1:
                    a, b = 1 - a, 1 - b
                py = a * y1 + b * y2
                pts.append((a * x1 + b * x2, STAR_Y + py, side * STAR_T * (1 - a - b),
                            nx / ln, ny / ln, nz / ln, 7.2 + (py + STAR_R) / STAR_R * 0.2, STAR, 0.2))   # +0.2: it glows a bit

    for i, g in enumerate(GIFTS):                           # presents, drop in from 8s
        gift(pts, *g, 8 + i * 0.5)
    return pts


PTS = build()
SNOW = [(rng.random(), rng.random(), rng.uniform(0.03, 0.1), rng.random() * TAU,
         rng.choice("..++*"), rng.choice((240, 244, 248, 252))) for _ in range(1500)]


def render(t, W, H):
    tc = t % CYCLE
    ca, sa = math.cos(t * SPIN), math.sin(t * SPIN)
    S = min(H / 1.7, W / 2.7)            # rows per world unit (chars are ~2x tall)
    gy, cx = H - 1 - 0.32 * S, W / 2
    zb, cells = [1e9] * (W * H), [None] * (W * H)

    def put(x, y, ch, col):              # background layer: only where nothing is yet
        if 0 <= x < W and 0 <= y < H and cells[y * W + x] is None:
            cells[y * W + x] = (ch, col)

    # --- 3D scene: every point is rotated, culled, projected, z-tested and lit ---
    for x, y, z, nx, ny, nz, t0, (ramp, cull, blink, falls), jit in PTS:
        if tc < t0:
            continue
        nxr, nzr = nx * ca + nz * sa, nz * ca - nx * sa
        if cull and nzr * CT - ny * ST > 0.2:      # facing away from the camera
            continue
        if falls:
            y += max(0.0, t0 + 0.5 - tc) * 2
        xr, zr = x * ca + z * sa, z * ca - x * sa
        d = zr * CT - y * ST
        f = D / (D + d)
        sx, sy = int(cx + xr * f * S * 2), int(gy - (y * CT + zr * ST) * f * S)
        if 0 <= sx < W and 0 <= sy < H and d < zb[sy * W + sx]:
            i = sy * W + sx
            zb[i] = d
            if blink and math.sin(t * 3 + jit * 40) < -0.2:
                cells[i] = (ramp[0][0], 236)       # fairy light in its "off" blink
            else:
                b = AMB + (1 - AMB) * max(0.0, nxr * LX + ny * LY + nzr * LZ) + jit
                cells[i] = ramp[max(0, min(len(ramp) - 1, int(b * len(ramp))))]

    # --- glint: rays flash whenever the star's face swings toward the camera ---
    g = int((abs(ca) - 0.9) * 40)        # 0..4 ray segments
    if tc >= 7.6 and g > 0:
        f = D / (D - STAR_Y * ST)
        sx, sy, e = int(cx), int(gy - STAR_Y * CT * f * S), int(STAR_R * f * S) + 1
        rays = [(sx, sy - e - k, "|") for k in range(1, g + 1)]
        rays += [(sx + sgn * (2 * e + k), sy, "-") for sgn in (-1, 1) for k in range(1, 2 * g + 1)]
        for x, y, ch in rays:
            if 0 <= x < W and 0 <= y < H and zb[y * W + x] == 1e9:
                cells[y * W + x] = (ch, 229)

    # --- snowman, right side, a bit behind the tree ---
    x0, y0 = min(W - 15, int(cx + S * 1.45)), int(gy - 0.1 * S) - len(SNOWMAN) + 1
    for dy, line in enumerate(SNOWMAN):
        for dx in range(len(line) - len(line.lstrip()), len(line.rstrip())):
            ch = line[dx]
            col = 244 if dy < 2 else 208 if ch == ">" else 94 if dy == 4 and ch in "\\/-" else 252
            put(x0 + dx, y0 + dy, ch, col)

    # --- string lights swagged across the top, chasing ---
    seg, sag = W / max(2, W // 45), max(2.0, H * 0.1)
    for x in range(W):
        p = (x % seg) / seg
        y = int(1 + sag * 4 * p * (1 - p))
        if x % 4:
            put(x, y, "-", 236)
        elif (x // 4 + int(t * 1.5)) % 3:
            put(x, y, "O", BULBS[x // 4 % 5])
        else:
            put(x, y, "o", 238)

    # --- snowy floor with a drifted edge ---
    for x in range(W):
        top = int(gy - 0.2 * S + 0.6 * math.sin(x * 0.11) + 0.4 * math.sin(x * 0.037 + 1))
        for y in range(max(0, top), H):
            n = NOISE[(x * 73 + y * 151) % 4096]
            put(x, y, "_" if y == top and n < 0.7 else FLOOR[int(n * len(FLOOR))], 255 if n > 0.5 else 250)

    # --- falling snow in whatever sky is left ---
    for xs, ys, sp, ph, ch, col in SNOW[: W * H // 40]:
        put(int((xs + 0.02 * math.sin(t * 0.7 + ph)) % 1 * W), int((ys + sp * t) % 1 * H), ch, col)

    rows, last = [], None
    for r in range(H):
        row = []
        for cell in cells[r * W:(r + 1) * W]:
            if cell is None or cell[0] == " ":
                row.append(" ")
            else:
                if cell[1] != last:
                    last = cell[1]
                    row.append(f"\x1b[38;5;{last}m")
                row.append(cell[0])
        rows.append("".join(row))
    return "\x1b[H" + "\n".join(rows)


def main():
    w = sys.stdout.write
    w("\x1b[?1049h\x1b[?25l\x1b[2J")     # alt screen, hide cursor
    start = time.monotonic()
    try:
        while True:
            tick = time.monotonic()
            W, H = shutil.get_terminal_size()
            w(render(tick - start, W, H))
            sys.stdout.flush()
            time.sleep(max(0.0, 1 / FPS - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        w("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
