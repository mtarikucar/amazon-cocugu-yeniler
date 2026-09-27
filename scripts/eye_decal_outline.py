"""Göz iris decal'inin tam ölçüsünü ve kontur şeklini STL'den hesaplar.

Adımlar (her göz için):
  1. Göz yüzeyinin montajda kafa dışında kalan kısmından bakış yönü bulunur.
  2. İris kubbesine küre oturtulur (tepe çevresi, iteratif en küçük kareler).
  3. Kubbe tabanındaki içbükey kıvrım kenarları toplanır; kürenin üzerindeki
     taban dairesi (eksen + yarım açı) bu kıvrıma oturtulur. Sol gözde kıvrım
     iki yaydan oluştuğu için eksen ve açı birlikte bulunur; sağ gözde tek yay
     olduğundan aynı açı sabit tutulup yalnızca eksen oturtulur.
  4. Kubbe bölgesi incelip (≤0.04 mm kenar) ARAP ile düzleme açılır; bu,
     filmin en az gerildiği/sıkıştığı düz şekildir. Bozulma raporlanır.
  5. Her tepe noktasının görünürlüğü montajlı kafa + saç + bere ile 9 bakış
     yönünden ışın atılarak bulunur. Decal = kubbe ∩ (görünen + taşma payı).

Çıktı JSON'u waterslide_eye_decal.py decal konturu olarak kullanır.
Kullanım: python scripts/eye_decal_outline.py <STL_klasörü> <çıktı.json> [açınım_debug_klasörü]
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy.sparse as sp
import trimesh
from scipy.interpolate import LinearNDInterpolator
from scipy.optimize import least_squares
from scipy.sparse.linalg import factorized
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from shapely.ops import unary_union
from skimage import measure

OCCLUDERS = ["15_Kafa", "18_Sac", "19_Bere"]
BLEED = 0.15            # mm, görünen sınırdan kapak altına taşma payı
CONE_DEG = 20           # bakış konisi yarım açısı
CREASE_MIN_DEG = 12     # kıvrım sayılacak en küçük içbükey dihedral açı
MAX_EDGE = 0.04         # mm, açınım için inceltme


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def axis_from(p):
    return np.array([np.cos(p[1]) * np.cos(p[0]), np.cos(p[1]) * np.sin(p[0]), np.sin(p[1])])


def angles_of(a):
    return [np.arctan2(a[1], a[0]), np.arcsin(np.clip(a[2], -1, 1))]


def visible_dir(eye, head):
    c, n = eye.triangles_center, eye.face_normals
    _, ray = head.ray.intersects_id(c + n * 0.05, n, multiple_hits=False)
    vis = np.ones(len(c), bool)
    vis[ray] = False
    return unit((n[vis] * eye.area_faces[vis, None]).sum(0))


def fit_sphere(V, view):
    apex = V[np.argmax(V @ view)]
    sel = np.linalg.norm(V - apex, axis=1) < 1.8
    for _ in range(20):
        P = V[sel]
        s = np.linalg.lstsq(np.c_[2 * P, np.ones(len(P))], (P ** 2).sum(1), rcond=None)[0]
        c = s[:3]
        R = float(np.sqrt(s[3] + c @ c))
        res = np.abs(np.linalg.norm(V - c, axis=1) - R)
        new = (res < 0.02) & (((V - c) @ view) > 0) & (np.linalg.norm(V - apex, axis=1) < 4)
        if (new == sel).all():
            break
        sel = new
    return c, R, float(res[sel].mean())


def crease_points(eye, view):
    ang = np.degrees(eye.face_adjacency_angles)
    fn = eye.face_normals[eye.face_adjacency]
    sel = (~eye.face_adjacency_convex) & ((fn @ view) > 0).all(1) & (ang > CREASE_MIN_DEG)
    return eye.vertices[eye.face_adjacency_edges[sel]].mean(1)


def fit_cap_circle(u, a0, theta=None):
    """Birim küre üzerindeki u noktalarına daire (eksen a, yarım açı θ) oturtur."""
    best = None
    for d1 in np.radians(np.arange(-30, 31, 10)):
        for d2 in np.radians(np.arange(-30, 31, 10)):
            p0 = [angles_of(a0)[0] + d1, angles_of(a0)[1] + d2]
            if theta is None:
                f = lambda p: np.arccos(np.clip(u @ axis_from(p[:2]), -1, 1)) - p[2]
                r = least_squares(f, [*p0, np.radians(40)], loss="soft_l1", f_scale=np.radians(2))
            else:
                f = lambda p: np.arccos(np.clip(u @ axis_from(p), -1, 1)) - theta
                r = least_squares(f, p0, loss="soft_l1", f_scale=np.radians(2))
            if best is None or r.cost < best.cost:
                best = r
    a = axis_from(best.x[:2])
    th = best.x[2] if theta is None else theta
    res = np.degrees(np.arccos(np.clip(u @ a, -1, 1)) - th)
    return a, float(th), float(np.median(np.abs(res)))


def arap_flatten(V, F, iters=60):
    """Serbest sınırlı ARAP parametrizasyonu (Liu vd. 2008), LSCM benzeri başlangıçla."""
    nF = len(F)
    # her üçgenin kendi düzlemindeki izometrik 2B koordinatları
    e1 = V[F[:, 1]] - V[F[:, 0]]
    e2 = V[F[:, 2]] - V[F[:, 0]]
    l1 = np.linalg.norm(e1, axis=1)
    x2 = (e1 * e2).sum(1) / l1
    y2 = np.linalg.norm(np.cross(e1, e2), axis=1) / l1
    X = np.zeros((nF, 3, 2))
    X[:, 1, 0] = l1
    X[:, 2, 0], X[:, 2, 1] = x2, y2
    # kotanjant ağırlıkları
    cot = np.zeros((nF, 3))
    for i in range(3):
        a, b = X[:, (i + 1) % 3] - X[:, i], X[:, (i + 2) % 3] - X[:, i]
        cot[:, i] = (a * b).sum(1) / np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
    n = len(V)
    rows, cols, vals = [], [], []
    for i in range(3):
        j, k = (i + 1) % 3, (i + 2) % 3
        w = 0.5 * cot[:, i]  # kenar (j,k) karşısındaki açı
        for p, q in [(j, k), (k, j)]:
            rows += [F[:, p], F[:, p]]
            cols += [F[:, q], F[:, p]]
            vals += [-w, w]
    L = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    L = (L + sp.eye(n) * 1e-9).tocsc()
    # başlangıç: tepe teğet düzlemine dik izdüşüm (kubbe sığ, yeterli)
    ctr = V.mean(0)
    nrm = unit(np.linalg.svd(V - ctr, full_matrices=False)[2][2])
    t0 = unit(np.cross(nrm, [0, 0, 1]))
    t1 = np.cross(nrm, t0)
    U = np.c_[(V - ctr) @ t0, (V - ctr) @ t1]
    solve = factorized(L)
    for _ in range(iters):
        # yerel adım: her üçgen için en yakın rotasyon
        Rs = np.zeros((nF, 2, 2))
        S = np.zeros((nF, 2, 2))
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            du = U[F[:, j]] - U[F[:, k]]
            dx = X[:, j] - X[:, k]
            S += cot[:, i, None, None] * du[:, :, None] * dx[:, None, :]
        u_, _, vt = np.linalg.svd(S)
        d = np.sign(np.linalg.det(u_ @ vt))
        u_[:, :, 1] *= d[:, None]
        Rs = u_ @ vt
        # global adım
        b = np.zeros((n, 2))
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            dx = X[:, j] - X[:, k]
            r = 0.5 * cot[:, i, None] * np.einsum("fab,fb->fa", Rs, dx)
            np.add.at(b, F[:, j], r)
            np.add.at(b, F[:, k], -r)
        U = np.c_[solve(b[:, 0]), solve(b[:, 1])]
    # bozulma: her üçgenin Jacobian tekil değerleri
    J = np.zeros((nF, 2, 2))
    dU = np.stack([U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]], 2)
    dX = np.stack([X[:, 1], X[:, 2]], 2)
    J = dU @ np.linalg.inv(dX)
    sv = np.linalg.svd(J, compute_uv=False)
    return U, sv


def closed_contour(U, F, s, step=0.005):
    """Üçgenleme üzerindeki s>0 bölgesinin kapalı dış konturu (mesh dışı = negatif)."""
    x0, y0 = U.min(0) - 3 * step
    x1, y1 = U.max(0) + 3 * step
    gx, gy = np.arange(x0, x1, step), np.arange(y0, y1, step)
    GX, GY = np.meshgrid(gx, gy)
    G = np.c_[GX.ravel(), GY.ravel()]
    Z = LinearNDInterpolator(U, s, fill_value=-1.0)(G)
    # mesh dışı (içbükey sınırda Delaunay dolgusu) = negatif
    Z[cKDTree(U).query(G)[0] > 0.8 * MAX_EDGE] = -1.0
    Z = Z.reshape(GX.shape)
    cont = max(measure.find_contours(Z, 0.0), key=len)
    poly = Polygon([(x0 + c * step, y0 + r * step) for r, c in cont]).buffer(0)
    return max(poly.geoms, key=lambda g: g.area) if hasattr(poly, "geoms") else poly


def main():
    stl = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    debug_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    occ = trimesh.util.concatenate([trimesh.load(stl / f"{k}.stl") for k in OCCLUDERS])
    head = trimesh.load(stl / "15_Kafa.stl")
    eyes = {"SOL": trimesh.load(stl / "16_Sol_Goz.stl"), "SAG": trimesh.load(stl / "17_Sag_Goz.stl")}
    result, theta_ref = {}, None
    for label in ["SOL", "SAG"]:  # SOL önce: iki yaylı kıvrım açıyı belirler
        eye = eyes[label]
        view = visible_dir(eye, head)
        c, R, sph_res = fit_sphere(eye.vertices, view)
        P = crease_points(eye, view)
        x = unit(np.cross([0, 0, 1], view))
        y = np.cross(view, x)
        cen = eye.centroid
        if label == "SOL":
            keep = np.abs(np.linalg.norm(P - c, axis=1) - R) < 0.25
            a, theta, med = fit_cap_circle(unit(P[keep] - c), view)
            theta_ref = theta
        else:
            # alt kapak birleşimindeki kıvrım ve dış kenar hariç: yalnız iris yayı
            px, py = (P - cen) @ x, (P - cen) @ y
            keep = (px > -0.3) & (px < 1.1) & (py > -1.2)
            a, theta, med = fit_cap_circle(unit(P[keep] - c), view, theta_ref)

        # kubbe bölgesi (taban + 3° pay), ön yüzler, tepeyle bağlantılı bileşen
        ang_v = np.arccos(np.clip(unit(eye.vertices - c) @ a, -1, 1))
        fsel = (ang_v[eye.faces] < theta + np.radians(3)).all(1) & ((eye.face_normals @ a) > 0)
        patch = eye.submesh([np.where(fsel)[0]], append=True)
        Vp, Fp = trimesh.remesh.subdivide_to_size(patch.vertices, patch.faces, MAX_EDGE)
        patch = trimesh.Trimesh(Vp, Fp, process=True)
        comps = patch.split(only_watertight=False)
        top = c + R * a
        patch = min(comps, key=lambda m: np.min(np.linalg.norm(m.vertices - top, axis=1)))
        V, F = patch.vertices, patch.faces
        U, sv = arap_flatten(V, F)
        d1, d2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
        area2 = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
        flips = int(min((area2 > 0).sum(), (area2 < 0).sum()))

        # hizalama: tepe merkezde, 3B "yukarı" (dünya Z'nin teğet izdüşümü) +y
        up3 = unit(np.array([0, 0, 1.0]) - a * a[2])
        right3 = np.cross(up3, a)
        T = np.c_[(V - top) @ right3, (V - top) @ up3]
        w = np.exp(-np.linalg.norm(V - top, axis=1) ** 2)  # merkeze yakın noktalar ağırlıklı
        mu_u, mu_t = (U * w[:, None]).sum(0) / w.sum(), (T * w[:, None]).sum(0) / w.sum()
        H = ((U - mu_u) * w[:, None]).T @ (T - mu_t)
        uu, _, vv = np.linalg.svd(H)
        Rot = uu @ vv
        if np.linalg.det(Rot) < 0:
            U[:, 0] *= -1
            H = ((U - (U * w[:, None]).sum(0) / w.sum()) * w[:, None]).T @ (T - mu_t)
            uu, _, vv = np.linalg.svd(H)
            Rot = uu @ vv
        U = U @ Rot
        k0 = np.argmin(np.linalg.norm(V - top, axis=1))
        U = U - U[k0]

        # görünürlük: her tepe noktasından bakış konisindeki 9 yöne ışın
        n_v = patch.vertex_normals
        t0 = unit(np.cross([0, 0, 1], view))
        t1 = np.cross(view, t0)
        dirs = [view] + [unit(view + np.tan(np.radians(CONE_DEG)) * (np.cos(p) * t0 + np.sin(p) * t1))
                         for p in np.radians(np.arange(0, 360, 45))]
        vis = np.zeros(len(V), bool)
        for d in dirs:
            ok = (n_v @ d) > 0
            O = V[ok] + n_v[ok] * 0.01
            hit = occ.ray.intersects_any(O, np.tile(d, (len(O), 1)))
            idx = np.where(ok)[0][~hit]
            vis[idx] = True

        # skaler alanlar (mm): kubbe içi ve taşma paylı görünürlük; sıfır konturu = decal sınırı
        ang_p = np.arccos(np.clip(unit(V - c) @ a, -1, 1))
        s_dome = (theta - ang_p) * R
        d_vis = cKDTree(U[vis]).query(U)[0]
        d_inv = cKDTree(U[~vis]).query(U)[0]
        s_vis = np.where(vis, BLEED + d_inv, BLEED - d_vis)
        s = np.minimum(s_dome, s_vis)
        poly = closed_contour(U, F, s)
        # 0.24 mm'den dar çıkıntıları temizle (0.12 mm morfolojik açma)
        poly = poly.buffer(-0.12, join_style=1).buffer(0.12, join_style=1)
        poly = max(poly.geoms, key=lambda g: g.area) if hasattr(poly, "geoms") else poly
        # açınımdaki iris dairesi: tam kubbe kenarındaki noktalara daire oturt
        E2 = U[np.abs(s_dome) < 0.01]
        sol = np.linalg.lstsq(np.c_[2 * E2, np.ones(len(E2))], (E2 ** 2).sum(1), rcond=None)[0]
        iris_c = sol[:2]
        iris_r = float(np.sqrt(sol[2] + iris_c @ iris_c))
        r_edge = np.linalg.norm(E2 - iris_c, axis=1)
        if debug_dir:
            np.savez(debug_dir / f"acinim_{label}.npz", V=V, U=U, F=F, vis=vis, s_dome=s_dome,
                     outline=np.asarray(poly.exterior.coords))
        inside = (s_dome[F] > 0).all(1)
        sv_in = sv[inside]
        area3 = np.sum(patch.area_faces[inside & vis[F].any(1)])
        result[label] = {
            "stl": "16_Sol_Goz.stl" if label == "SOL" else "17_Sag_Goz.stl",
            "kure_R_mm": round(R, 3),
            "kure_fit_ortalama_sapma_mm": round(sph_res, 4),
            "kubbe_yarim_aci_deg": round(float(np.degrees(theta)), 2),
            "kubbe_taban_capi_mm": round(float(2 * R * np.sin(theta)), 3),
            "kubbe_yuksekligi_mm": round(float(R * (1 - np.cos(theta))), 3),
            "kubbe_yuzey_capi_mm": round(2 * R * theta, 3),
            "kivrim_fit_medyan_sapma_deg": round(med, 2),
            "kivrim_nokta_sayisi": int(keep.sum()),
            "acinim_iris_merkezi_mm": [round(float(v), 3) for v in iris_c],
            "acinim_iris_yaricapi_mm": round(iris_r, 3),
            "acinim_iris_daire_sapma_std_mm": round(float(r_edge.std()), 3),
            "acinim_ters_ucgen": flips,
            "acinim_gerilme_min_max": [round(float(sv_in.min()), 3), round(float(sv_in.max()), 3)],
            "acinim_gerilme_p5_p95": [round(float(np.percentile(sv_in, 5)), 3), round(float(np.percentile(sv_in, 95)), 3)],
            "gorunen_iris_yuzey_alani_mm2": round(float(area3), 2),
            "decal_alani_mm2": round(poly.area, 2),
            "decal_bbox_mm": [round(v, 3) for v in poly.bounds],
            "decal_kontur_mm": [[round(px, 3), round(py, 3)] for px, py in poly.simplify(0.005).exterior.coords],
            "kubbe_ekseni": [round(float(v), 4) for v in a],
            "kubbe_tepesi_mm": [round(float(v), 3) for v in top],
        }
        print(label, {k: v for k, v in result[label].items() if k not in ("decal_kontur_mm",)})
    out_path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
