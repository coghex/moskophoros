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

# One triangle in the XY plane, facing +Z.
TRIANGLE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))

_COMPONENTS = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}
_OUTPUT_TYPES = {"translation": "VEC3", "scale": "VEC3", "rotation": "VEC4"}


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

    def node(self, name=None, *, mesh=False, translation=None, children=()):
        """Add a node, optionally with the triangle mesh; return its index."""
        node = {}
        if name is not None:
            node["name"] = name
        if mesh:
            node["mesh"] = self._triangle()
        if translation is not None:
            node["translation"] = list(translation)
        if children:
            node["children"] = list(children)
        self.document["nodes"].append(node)
        return len(self.document["nodes"]) - 1

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
        `translation`, `rotation` or `scale` and each value is a tuple. Each
        channel gets its own linear sampler.
        """
        samplers = []
        targets = []
        for node, path, times, values in channels:
            if len(times) != len(values):
                raise ValueError("a channel needs one value per time")
            samplers.append(
                {
                    "input": self._accessor("SCALAR", [(t,) for t in times], True),
                    "output": self._accessor(_OUTPUT_TYPES[path], values, False),
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
            position = self._accessor("VEC3", TRIANGLE, True)
            self.document["meshes"] = [
                {"primitives": [{"attributes": {"POSITION": position}}]}
            ]
            self._mesh = 0
        return self._mesh

    def _accessor(self, kind, rows, bounds):
        """Store float rows in the buffer and return their accessor's index."""
        if any(len(row) != _COMPONENTS[kind] for row in rows):
            raise ValueError(f"every {kind} row needs {_COMPONENTS[kind]} values")
        rows = [tuple(float32(value) for value in row) for row in rows]
        offset = len(self._binary)
        for row in rows:
            self._binary += struct.pack(f"<{len(row)}f", *row)
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
            "componentType": FLOAT,
            "count": len(rows),
            "type": kind,
        }
        if bounds:
            accessor["min"] = [min(column) for column in zip(*rows, strict=True)]
            accessor["max"] = [max(column) for column in zip(*rows, strict=True)]
        accessors = document.setdefault("accessors", [])
        accessors.append(accessor)
        return len(accessors) - 1
