"""Normal and depth buffers as the capture writes them (design §Capture job
and result contract), written here independently of the package, for fake
captures and their tests.

Each is a 16-bit RGBA PNG, every row unfiltered, with no chunk but IHDR,
IDAT and IEND. Alpha is 65535 on a surface and every sample is 0 off one. A
normal component n is stored as floor((n + 1) / 2 · 65535 + ½); a depth is a
32-bit float whose big-endian bits are red (high half) and green (low half),
with blue 0.
"""

import struct
import zlib

import numpy as np

SURFACE = 0xFFFF


def png16(path, samples, *, filters=None, extra_chunks=()):
    """Write `samples`, a `(height, width, 4)` array of 16-bit values, as an
    RGBA PNG. `filters` gives each row's filter byte (0 by default), and
    `extra_chunks` adds `(kind, body)` chunks after the header."""
    samples = np.asarray(samples, dtype=np.uint16)
    height, width, _ = samples.shape
    data = samples.astype(">u2").tobytes()
    stride = width * 8
    raw = b"".join(
        bytes([0 if filters is None else filters[y]])
        + data[y * stride : (y + 1) * stride]
        for y in range(height)
    )

    def chunk(kind, body):
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 16, 6, 0, 0, 0)
    content = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
    for kind, body in extra_chunks:
        content += chunk(kind, body)
    content += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def normal_samples(normals, covered):
    """The samples of a normal buffer: `normals` `(height, width, 3)`,
    stored where `covered`."""
    normals = np.asarray(normals, dtype=np.float64)
    covered = np.asarray(covered, dtype=bool)
    samples = np.zeros((*covered.shape, 4), dtype=np.uint16)
    encoded = np.floor((normals + 1) / 2 * 65535 + 0.5).astype(np.uint16)
    samples[covered, :3] = encoded[covered]
    samples[covered, 3] = SURFACE
    return samples


def depth_samples(depth, covered):
    """The samples of a depth buffer: `depth` `(height, width)` in meters,
    stored where `covered`."""
    covered = np.asarray(covered, dtype=bool)
    bits = np.asarray(depth, dtype=np.float32).view(np.uint32)
    samples = np.zeros((*covered.shape, 4), dtype=np.uint16)
    samples[covered, 0] = (bits[covered] >> 16).astype(np.uint16)
    samples[covered, 1] = (bits[covered] & 0xFFFF).astype(np.uint16)
    samples[covered, 3] = SURFACE
    return samples


def write_normal(path, covered, normal=(0.0, 0.0, 1.0)):
    """A normal buffer facing `normal` wherever `covered`; `normal` is one
    vector or a `(height, width, 3)` array."""
    covered = np.asarray(covered, dtype=bool)
    normals = np.broadcast_to(np.asarray(normal, dtype=np.float64), (*covered.shape, 3))
    return png16(path, normal_samples(normals, covered))


def write_depth(path, covered, depth=0.0):
    """A depth buffer of `depth` meters wherever `covered`; `depth` is one
    value or a `(height, width)` array."""
    covered = np.asarray(covered, dtype=bool)
    depths = np.broadcast_to(np.asarray(depth, dtype=np.float64), covered.shape)
    return png16(path, depth_samples(depths, covered))


# The front layer's buffers (alpha design, Capture transport and provenance).
FRONT_BUFFERS = ("front_color", "front_alpha", "front_matid", "front_shade")


def write_front(
    directory, ordinal, size, present=None, colour=(0, 0, 0), q=0, code=1, shade=137
):
    """Frame `ordinal`'s front buffers under `directory`, `size` (width,
    height): the front layer in `colour` at alpha `q`, material-ID `code` and
    `shade` wherever `present`, a `(height, width)` bool array, and nowhere
    by default. Returns {name: relative path}."""
    from PIL import Image

    width, height = size
    present = (
        np.zeros((height, width), dtype=bool)
        if present is None
        else np.asarray(present, dtype=bool)
    )
    paths = {name: f"{name}/{ordinal:06d}.png" for name in FRONT_BUFFERS}
    for name, value in (
        ("front_color", (*colour, 255)),
        ("front_matid", (code >> 8, code & 255, 0, 255)),
        ("front_shade", (shade, shade, shade, 255)),
    ):
        pixels = np.zeros((height, width, 4), dtype=np.uint8)
        pixels[present] = value
        path = directory / paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(pixels, "RGBA").save(path)
    samples = np.zeros((height, width, 4), dtype=np.uint16)
    samples[present] = (q, 0, 0, SURFACE)
    png16(directory / paths["front_alpha"], samples)
    return paths
