"""Write small binary glTF 2.0 files for tests, in pure Python.

Build a model with `GlbWriter`, then `write` it into a directory the test
owns. Valid models come from the builder methods. A test makes a malformed
one by editing `document` before writing, or by passing `write` the
container overrides `to_bytes` takes.
"""

import json
import struct
from pathlib import Path

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT = 5126
UNSIGNED_SHORT = 5123
_FORMATS = {FLOAT: "f", UNSIGNED_SHORT: "H"}

# One triangle in the XY plane, facing +Z.
TRIANGLE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))

_COMPONENTS = {"SCALAR": 1, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_OUTPUT_TYPES = {
    "translation": "VEC3",
    "scale": "VEC3",
    "rotation": "VEC4",
    "weights": "SCALAR",
}


def float32(value):
    """`value` as glTF stores it, so accessor bounds match the data."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _pad(data, fill):
    return data + fill * (-len(data) % 4)


class GlbWriter:
    def __init__(self):
        self.document = {
            "asset": {"version": "2.0", "generator": "moskophoros tests"},
            "scenes": [],
            "nodes": [],
        }
        self._binary = bytearray()
        self._mesh = None

    def node(
        self,
        name=None,
        *,
        mesh=False,
        translation=None,
        rotation=None,
        scale=None,
        children=(),
        skin=None,
        weights=None,
    ):
        """Add a node and return its index.

        `mesh` is True for the shared triangle, or a mesh index from `mesh`.
        `rotation` is a quaternion (x, y, z, w). `weights` overrides the
        mesh's default morph weights.
        """
        node = {}
        if name is not None:
            node["name"] = name
        if mesh is True:
            node["mesh"] = self._triangle()
        elif mesh is not False:
            node["mesh"] = mesh
        for key, value in (
            ("translation", translation),
            ("rotation", rotation),
            ("scale", scale),
            ("weights", weights),
        ):
            if value is not None:
                node[key] = list(value)
        if children:
            node["children"] = list(children)
        if skin is not None:
            node["skin"] = skin
        self.document["nodes"].append(node)
        return len(self.document["nodes"]) - 1

    def mesh(
        self, positions, *, targets=(), weights=None, joints=None, skin_weights=None
    ):
        """Add a triangle-list mesh of `positions` and return its index.

        `targets` are morph targets, each a list of position offsets, and
        `weights` their default weights. `joints` and `skin_weights` give
        each vertex four joint indices and four weights, for skinning.
        """
        primitive = {
            "attributes": {"POSITION": self._accessor("VEC3", positions, True)}
        }
        if joints is not None:
            primitive["attributes"]["JOINTS_0"] = self._accessor(
                "VEC4", joints, False, UNSIGNED_SHORT
            )
            primitive["attributes"]["WEIGHTS_0"] = self._accessor(
                "VEC4", skin_weights, False
            )
        if targets:
            primitive["targets"] = [
                {"POSITION": self._accessor("VEC3", offsets, True)}
                for offsets in targets
            ]
        mesh = {"primitives": [primitive]}
        if weights is not None:
            mesh["weights"] = list(weights)
        meshes = self.document.setdefault("meshes", [])
        meshes.append(mesh)
        return len(meshes) - 1

    def instances(self, node, translations):
        """Draw `node`'s mesh once per translation, with EXT_mesh_gpu_instancing."""
        accessor = self._accessor("VEC3", translations, False)
        self.document["nodes"][node]["extensions"] = {
            "EXT_mesh_gpu_instancing": {"attributes": {"TRANSLATION": accessor}}
        }
        used = self.document.setdefault("extensionsUsed", [])
        if "EXT_mesh_gpu_instancing" not in used:
            used.append("EXT_mesh_gpu_instancing")

    def skin(self, joints, inverse_bind_matrices):
        """Add a skin of `joints`, with one column-major 4×4 inverse bind
        matrix each, and return its index."""
        skins = self.document.setdefault("skins", [])
        skins.append(
            {
                "joints": list(joints),
                "inverseBindMatrices": self._accessor(
                    "MAT4", inverse_bind_matrices, False
                ),
            }
        )
        return len(skins) - 1

    def scene(self, nodes, *, default=False):
        """Add a scene of root `nodes`; `default` sets the `scene` property."""
        self.document["scenes"].append({"nodes": list(nodes)})
        index = len(self.document["scenes"]) - 1
        if default:
            self.document["scene"] = index
        return index

    def animation(self, name, channels):
        """Add an animation; `name=None` leaves it unnamed.

        Each channel is `(node, path, times, values)`, where `path` is
        `translation`, `rotation`, `scale` or `weights` and each value is a
        tuple: for `weights`, one weight per morph target. Each channel gets
        its own linear sampler.
        """
        samplers = []
        targets = []
        for node, path, times, values in channels:
            if len(times) != len(values):
                raise ValueError("a channel needs one value per time")
            rows = values
            if path == "weights":
                rows = [(weight,) for row in values for weight in row]
            samplers.append(
                {
                    "input": self._accessor("SCALAR", [(t,) for t in times], True),
                    "output": self._accessor(_OUTPUT_TYPES[path], rows, False),
                    "interpolation": "LINEAR",
                }
            )
            targets.append(
                {
                    "sampler": len(samplers) - 1,
                    "target": {"node": node, "path": path},
                }
            )
        animation = {"channels": targets, "samplers": samplers}
        if name is not None:
            animation["name"] = name
        self.document.setdefault("animations", []).append(animation)
        return len(self.document["animations"]) - 1

    def to_bytes(
        self,
        *,
        magic=b"glTF",
        version=2,
        length=None,
        json_bytes=None,
        omit_json=False,
        json_chunk_length=None,
    ):
        """Encode the model; the keywords produce malformed containers.

        `length` replaces the header's total length, `json_bytes` the JSON
        chunk's content and `json_chunk_length` its declared length.
        `omit_json` leaves the JSON chunk out, so the file starts with its
        binary chunk if it has one.
        """
        if json_bytes is None:
            json_bytes = json.dumps(self.document, separators=(",", ":")).encode()
        chunks = []
        if not omit_json:
            chunks.append((JSON_CHUNK, _pad(json_bytes, b" "), json_chunk_length))
        if self._binary:
            chunks.append((BIN_CHUNK, _pad(bytes(self._binary), b"\0"), None))
        body = b"".join(
            struct.pack("<II", len(data) if declared is None else declared, kind) + data
            for kind, data, declared in chunks
        )
        total = 12 + len(body) if length is None else length
        return struct.pack("<4sII", magic, version, total) + body

    def write(self, directory, stem="subject", **overrides):
        """Write `<stem>.glb` into `directory` and return its path."""
        path = Path(directory) / f"{stem}.glb"
        path.write_bytes(self.to_bytes(**overrides))
        return path

    def _triangle(self):
        if self._mesh is None:
            self._mesh = self.mesh(TRIANGLE)
        return self._mesh

    def _accessor(self, kind, rows, bounds, component=FLOAT):
        """Store rows in the buffer and return their accessor's index."""
        if any(len(row) != _COMPONENTS[kind] for row in rows):
            raise ValueError(f"every {kind} row needs {_COMPONENTS[kind]} values")
        if component == FLOAT:
            rows = [tuple(float32(value) for value in row) for row in rows]
        offset = len(self._binary)
        for row in rows:
            self._binary += struct.pack(f"<{len(row)}{_FORMATS[component]}", *row)
        self._binary += b"\0" * (-len(self._binary) % 4)
        document = self.document
        document["buffers"] = [{"byteLength": len(self._binary)}]
        views = document.setdefault("bufferViews", [])
        views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(self._binary) - offset,
            }
        )
        accessor = {
            "bufferView": len(views) - 1,
            "componentType": component,
            "count": len(rows),
            "type": kind,
        }
        if bounds:
            accessor["min"] = [min(column) for column in zip(*rows, strict=True)]
            accessor["max"] = [max(column) for column in zip(*rows, strict=True)]
        accessors = document.setdefault("accessors", [])
        accessors.append(accessor)
        return len(accessors) - 1
