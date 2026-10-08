"""Generated models for the material-ID and shade buffers (design §Capture,
material styling design §Spike record (D-10)).

Each builder writes a `.glb` into a directory and returns its path. Positions
are glTF's: +Y up, the camera of direction 0 looking along −Z.
"""

import io
import math

from glb_writer import GlbWriter
from PIL import Image

QUAD_UV = [(0, 1), (1, 1), (1, 0), (0, 1), (1, 0), (0, 0)]
GREY = (0.6, 0.6, 0.6, 1.0)


def quad_xy(x0, y0, x1, y1, z):
    """A rectangle in the plane `z`, facing +Z."""
    return [
        (x0, y0, z),
        (x1, y0, z),
        (x1, y1, z),
        (x0, y0, z),
        (x1, y1, z),
        (x0, y1, z),
    ]


def quad_xz(x0, z0, x1, z1, y):
    """A rectangle in the plane `y`, facing +Y."""
    return [
        (x0, y, z0),
        (x0, y, z1),
        (x1, y, z1),
        (x0, y, z0),
        (x1, y, z1),
        (x1, y, z0),
    ]


def cube(center, half):
    x, y, z = center
    c = [
        (x + dx * half, y + dy * half, z + dz * half)
        for dx in (-1, 1)
        for dy in (-1, 1)
        for dz in (-1, 1)
    ]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    triangles = []
    for a, b, d, e in faces:
        triangles += [c[a], c[b], c[d], c[a], c[d], c[e]]
    return triangles


def sphere(center, radius, rings=24, segments=48):
    """A UV sphere's triangles and smooth normals, wound outward."""
    cx, cy, cz = center

    def point(i, j):
        theta = math.pi * i / rings
        phi = 2 * math.pi * j / segments
        n = (
            math.sin(theta) * math.cos(phi),
            math.cos(theta),
            math.sin(theta) * math.sin(phi),
        )
        return (cx + radius * n[0], cy + radius * n[1], cz + radius * n[2]), n

    positions, normals = [], []
    for i in range(rings):
        for j in range(segments):
            a, b = point(i, j), point(i + 1, j)
            c, d = point(i + 1, j + 1), point(i, j + 1)
            for triangle in ((a, c, b), (a, d, c)):
                for position, normal in triangle:
                    positions.append(position)
                    normals.append(normal)
    return positions, normals


class Model:
    """A `GlbWriter` building one mesh of several primitives on one node."""

    def __init__(self):
        self.writer = GlbWriter()
        meshes = self.writer.document.setdefault("meshes", [])
        meshes.append({"primitives": []})
        self.mesh = len(meshes) - 1
        self.nodes = []

    def material(
        self,
        name,
        color=GREY,
        *,
        alpha_mode=None,
        cutoff=None,
        texture=None,
        metallic=0.0,
        roughness=1.0,
    ):
        pbr = {
            "baseColorFactor": list(color),
            "metallicFactor": metallic,
            "roughnessFactor": roughness,
        }
        if texture is not None:
            pbr["baseColorTexture"] = {"index": texture}
        entry = {"pbrMetallicRoughness": pbr}
        if name is not None:
            entry["name"] = name
        if alpha_mode is not None:
            entry["alphaMode"] = alpha_mode
        if cutoff is not None:
            entry["alphaCutoff"] = cutoff
        materials = self.writer.document.setdefault("materials", [])
        materials.append(entry)
        return len(materials) - 1

    def texture(self, size, pixel):
        image = Image.new("RGBA", size)
        image.putdata([pixel(x, y) for y in range(size[1]) for x in range(size[0])])
        data = io.BytesIO()
        image.save(data, "PNG")
        return self.writer.texture(data.getvalue())

    def primitive(
        self, positions, material=None, *, normals=None, texcoords=None, colors=None
    ):
        writer = self.writer
        primitive = {
            "attributes": {"POSITION": writer._accessor("VEC3", positions, True)}
        }
        if colors is not None:
            primitive["attributes"]["COLOR_0"] = writer._accessor("VEC4", colors, False)
        if normals is not None:
            primitive["attributes"]["NORMAL"] = writer._accessor("VEC3", normals, False)
        if texcoords is not None:
            primitive["attributes"]["TEXCOORD_0"] = writer._accessor(
                "VEC2", texcoords, False
            )
        if material is not None:
            primitive["material"] = material
        writer.document["meshes"][self.mesh]["primitives"].append(primitive)

    def bare_node(self, positions):
        """A node of its own whose one primitive has no material."""
        node = self.writer.node(mesh=self.writer.mesh(positions))
        self.nodes.append(node)

    def write(self, directory, stem):
        node = self.writer.node(stem, mesh=self.mesh)
        self.writer.scene([node, *self.nodes], default=True)
        return self.writer.write(directory, stem)


def checker(x, y):
    """An 8×8 texture of opaque yellow cells and fully transparent cells."""
    return (255, 220, 0, 255) if (x // 2 + y // 2) % 2 else (0, 0, 0, 0)


# Material indices of `edges`, in glTF order.
EDGES = {
    "left": 0,
    "right": 1,
    "strip": 2,
    "mask": 3,
    "behind": 4,
    "occluder": 5,
    "occluded": 6,
    "glass": 7,
    "unused": 8,
}


def edges(directory):
    """Two materials meeting along x = 0; a strip 0.01 m wide; a `MASK`
    material 0.2 m in front of another; a cube of one material in front of a
    quad of another; a `BLEND` material; a material no primitive uses; two
    materials named `steel` and one unnamed; a primitive without a material
    and a node whose mesh has no material at all.

    In front view (pitch 0, the ground point at the origin), the left and
    right quads span y 0–1, the `MASK` pair x −1–0 and y 1.1–2.1, the
    occlusion pair x 0.1–1 and y 1.1–2.1, the `BLEND` quad and the
    material-less primitive y −1 to −0.1, and the bare node y −2 to −1.1.
    """
    model = Model()
    left = model.material("steel", (0.8, 0.1, 0.1, 1))
    right = model.material("cloth", (0.1, 0.8, 0.1, 1))
    strip = model.material("wire", (0.9, 0.9, 0.9, 1))
    mask = model.material(
        "leaf",
        (1, 1, 1, 1),
        alpha_mode="MASK",
        cutoff=0.5,
        texture=model.texture((8, 8), checker),
    )
    behind = model.material("bark", (0.2, 0.2, 0.9, 1))
    occluder = model.material("steel", (0.5, 0.5, 0.5, 1))
    occluded = model.material(None, (0.9, 0.5, 0.1, 1))
    glass = model.material("glass", (0.7, 0.9, 1.0, 0.5), alpha_mode="BLEND")
    model.material("unused")
    assert [left, right, strip, mask, behind, occluder, occluded, glass] == list(
        range(8)
    )
    model.primitive(quad_xy(-1.0, 0.0, 0.0, 1.0, 0.0), left)
    model.primitive(quad_xy(0.0, 0.0, 1.0, 1.0, 0.0), right)
    model.primitive(quad_xy(-0.505, 0.05, -0.495, 0.95, 0.05), strip)
    model.primitive(quad_xy(-1.0, 1.1, 0.0, 2.1, 0.2), mask, texcoords=QUAD_UV)
    model.primitive(quad_xy(-1.0, 1.1, 0.0, 2.1, 0.0), behind)
    model.primitive(quad_xy(0.1, 1.1, 1.0, 2.1, 0.0), occluded)
    model.primitive(cube((0.55, 1.6, 0.3), 0.2), occluder)
    model.primitive(quad_xy(-1.0, -1.0, -0.05, -0.1, 0.0), glass)
    model.primitive(quad_xy(0.05, -1.0, 1.0, -0.1, 0.0))
    model.bare_node(quad_xy(-1.0, -2.0, 1.0, -1.1, 0.0))
    return model.write(directory, "edges")


def form(directory, stem="form", materials=None):
    """D-25's three forms on one fixture: a flat floor (y = 0, x −1.5–1.5,
    z −1–1.5), a wall meeting it in a 90° crease along z = −1 (1.5 m high)
    and an isolated smooth sphere (radius 0.35 m, centre (0.7, 0.75, 0.4)).
    `materials(model)` returns the floor's, wall's and sphere's materials;
    by default one grey each."""
    model = Model()
    if materials is None:
        floor, wall, ball = (model.material(name) for name in ("floor", "wall", "ball"))
    else:
        floor, wall, ball = materials(model)
    model.primitive(quad_xz(-1.5, -1.0, 1.5, 1.5, 0.0), floor, texcoords=QUAD_UV)
    model.primitive(quad_xy(-1.5, 0.0, 1.5, 1.5, -1.0), wall, texcoords=QUAD_UV)
    positions, normals = sphere((0.7, 0.75, 0.4), 0.35)
    model.primitive(positions, ball, normals=normals)
    return model.write(directory, stem)


def appearance(directory):
    """`form` with materials that differ in colour, texture, metallic and
    roughness, and identical geometry."""

    def materials(model):
        texture = model.texture(
            (8, 8), lambda x, y: ((x * 37) % 256, (y * 53) % 256, 90, 255)
        )
        return (
            model.material(
                "floor",
                (0.1, 0.2, 0.9, 1),
                metallic=1.0,
                roughness=0.1,
                texture=texture,
            ),
            model.material("wall", (0.9, 0.9, 0.1, 1), metallic=0.5, roughness=0.3),
            model.material("ball", (0.05, 0.05, 0.05, 1), metallic=1.0, roughness=0.0),
        )

    return form(directory, "appearance", materials)


def vertex_colours(directory):
    """Two quads side by side sharing material 0, meeting along x = 0; only
    the right one has (neutral white) vertex colours, so Blender's importer
    gives it its own copy of the material."""
    model = Model()
    shared = model.material("steel")
    model.primitive(quad_xy(-1.0, 0.0, 0.0, 1.0, 0.0), shared)
    model.primitive(
        quad_xy(0.0, 0.0, 1.0, 1.0, 0.0), shared, colors=[(1.0, 1.0, 1.0, 1.0)] * 6
    )
    return model.write(directory, "colours")
