# Vẽ biểu tượng ứng dụng OpenTenki ra PNG, chỉ dùng thư viện chuẩn của Python.
#
# Máy này không có Pillow, không có rsvg-convert, không có ImageMagick, không có
# Inkscape. Chỉ có `sips`, mà `sips` không dựng được SVG. Nên tự viết:
#
#   - bộ mã hoá PNG  (zlib + struct, khoảng 12 dòng)
#   - bộ dựng hình   (hàm khoảng cách có dấu, khử răng cưa bằng smoothstep)
#
# Dùng hàm khoảng cách thay vì lấy mẫu nhiều lần: mỗi điểm ảnh tính đúng MỘT
# lần, độ phủ suy ra từ khoảng cách tới biên hình. Lấy mẫu 3×3 cho ảnh 1024
# là 9,4 triệu phép tính trong Python thuần — chậm tới mức vô lý, mà kết quả
# không đẹp hơn.

import zlib, struct, math, sys

# ── Bộ mã hoá PNG ──────────────────────────────────────────────────────────

def ghi_png(duong, rong, cao, hang):
    """hang: danh sách bytes, mỗi phần tử là một dòng RGB (rong*3 byte)."""
    tho = b''.join(b'\x00' + h for h in hang)          # 0 = không lọc trước
    def khoi(ten, du):
        c = ten + du
        return struct.pack('>I', len(du)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', rong, cao, 8, 2, 0, 0, 0)   # 8 bit, RGB
    with open(duong, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n'
                + khoi(b'IHDR', ihdr)
                + khoi(b'IDAT', zlib.compress(tho, 9))
                + khoi(b'IEND', b''))

# ── Hàm khoảng cách có dấu ─────────────────────────────────────────────────

def d_tron(px, py, cx, cy, r):
    return math.hypot(px - cx, py - cy) - r

def d_hop_bo(px, py, cx, cy, nx, ny, r):
    """Hộp chữ nhật bo góc. nx, ny là nửa cạnh."""
    qx = abs(px - cx) - (nx - r)
    qy = abs(py - cy) - (ny - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r

def d_vien(px, py, ax, ay, bx, by, r):
    """Đoạn thẳng bo tròn hai đầu — dùng vẽ hạt mưa."""
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    h = max(0.0, min(1.0, (pax * bax + pay * bay) / (bax * bax + bay * bay)))
    return math.hypot(pax - bax * h, pay - bay * h) - r

def phu(d, mem):
    """Khoảng cách → độ phủ 0..1. `mem` là bề rộng dải khử răng cưa."""
    if d <= -mem: return 1.0
    if d >=  mem: return 0.0
    t = (mem - d) / (2 * mem)
    return t * t * (3 - 2 * t)          # smoothstep

def tron(nen, tren, a):
    return tuple(n + (t - n) * a for n, t in zip(nen, tren))

# ── Bảng màu, lấy đúng từ trang web ────────────────────────────────────────

XANH2 = (0x38, 0xbd, 0xf8)      # --xanh2
XANH  = (0x0a, 0x6e, 0xd1)      # --xanh
TIM   = (0x63, 0x66, 0xf1)      # --tim
TRANG = (0xff, 0xff, 0xff)
NANG  = (0xfd, 0xd8, 0x35)
NANG2 = (0xfb, 0xa5, 0x0b)

def nen_gradient(t):
    """Chuyển màu chéo: xanh nhạt → xanh → tím, cùng hướng với logo web."""
    if t < 0.55:
        k = t / 0.55
        return tron(XANH2, XANH, k * k * (3 - 2 * k))
    k = (t - 0.55) / 0.45
    return tron(XANH, TIM, k * k * (3 - 2 * k))

# ── Dựng một điểm ảnh ──────────────────────────────────────────────────────

def diem(x, y, mem):
    # Nền: chuyển màu theo đường chéo
    mau = nen_gradient(max(0.0, min(1.0, (x + y) * 0.5)))

    # Mặt trời, nấp sau đám mây
    a = phu(d_tron(x, y, 0.371, 0.325, 0.132), mem)
    if a > 0:
        # chuyển màu nhẹ trong lòng mặt trời cho đỡ phẳng
        k = max(0.0, min(1.0, (y - 0.19) / 0.27))
        mau = tron(mau, tron(NANG, NANG2, k), a)

    # Đám mây: ba hình tròn chồng lên một hộp bo góc
    dm = min(
        d_tron(x, y, 0.496, 0.487, 0.158),
        d_tron(x, y, 0.363, 0.545, 0.113),
        d_tron(x, y, 0.633, 0.548, 0.122),
        d_hop_bo(x, y, 0.498, 0.590, 0.160, 0.072, 0.070),
    )
    # Viền trong bằng màu nền, để mây tách khỏi mặt trời mà không cần đổ bóng
    a = phu(dm + 0.030, mem)
    if a > 0: mau = tron(mau, nen_gradient(max(0.0, min(1.0, (x + y) * 0.5))), a)
    a = phu(dm, mem)
    if a > 0: mau = tron(mau, TRANG, a)

    # Ba hạt mưa nghiêng
    for hx in (0.378, 0.496, 0.614):
        dh = d_vien(x, y, hx + 0.020, 0.700, hx - 0.018, 0.800, 0.0235)
        a = phu(dh, mem)
        if a > 0: mau = tron(mau, TRANG, a)

    return mau

# ── Chạy ───────────────────────────────────────────────────────────────────

for canh in (512, 1024):
    mem = 1.1 / canh                      # dải khử răng cưa ≈ một điểm ảnh
    hang = []
    for j in range(canh):
        y = (j + 0.5) / canh
        d = bytearray()
        for i in range(canh):
            r, g, b = diem((i + 0.5) / canh, y, mem)
            d += bytes((int(r + 0.5), int(g + 0.5), int(b + 0.5)))
        hang.append(bytes(d))
    ten = f'icon-{canh}.png'
    ghi_png(ten, canh, canh, hang)
    print(f'  {ten}', file=sys.stderr)
