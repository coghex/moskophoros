"""The byte-exact manifest of the smallest positional export, checked member
by member against design P-8a's table before it was pinned: two directions,
one still clip, the sheet's colour and normal maps and a flat preview. The
test recomputes the fingerprint independently of the writer."""

POSITIONAL = b"""{
  "schema": "moskophoros.export/1",
  "generator": {
    "tool": "moskophoros",
    "version": "0.1.0",
    "python": "3.13.15",
    "numpy": "2.5.3",
    "pillow": "12.3.0",
    "blender": "5.2.2",
    "renderer": "cycles",
    "color": {
      "technique": "cycles-flat-emission",
      "samples_per_pixel": 1,
      "seed": 0,
      "pixel_filter": "BOX",
      "filter_width_px": 0.01,
      "min_transparent_bounces": 64,
      "transparent_max_bounces": 64,
      "pass_alpha_threshold": 9.313225746154785e-10
    },
    "shade": {
      "technique": "cycles-ambient-occlusion",
      "samples_per_pixel": 1,
      "seed": 0,
      "pixel_filter": "BOX",
      "filter_width_px": 0.01
    }
  },
  "source": {
    "file": "hero.glb",
    "sha256": "abababababababababababababababababababababababababababababababab"
  },
  "subject": "hero",
  "variant": "default",
  "settings": {
    "view": {
      "preset": "custom",
      "directions": 2,
      "start_angle_deg": 0.0
    },
    "camera": {
      "projection": "orthographic",
      "direction": [
        0.0,
        0.0,
        -1.0
      ],
      "roll": 0.0,
      "position": null
    },
    "model_yaw_deg": 0.0,
    "fps": 12.0,
    "frames": "auto",
    "supersample": 4,
    "pixels_per_meter": 4.0,
    "cell": {
      "width": 3,
      "height": 2
    },
    "ground_m": {
      "x": 0.0,
      "y": 0.0,
      "z": 0.0
    },
    "ground_px": {
      "x": 1,
      "y": 2
    },
    "root_motion": "error",
    "previews": true,
    "normals": true,
    "depth": false,
    "light": {
      "position": null,
      "intensity": 1.0,
      "ambient": 0.3
    },
    "shade": {
      "ao_distance_m": 0.3,
      "ao_samples": 64,
      "occlusion_weight": 0.25,
      "convexity_weight": 1.0,
      "range": [
        84,
        191
      ],
      "mode": "ramp",
      "ambient_form": true,
      "key": {
        "direction": [
          -0.5183210553488161,
          0.604707897906952,
          0.604707897906952
        ],
        "strength": 0.0
      },
      "sky": {
        "strength": 0.0
      },
      "ground": {
        "strength": 0.0
      },
      "sky_ground_frame": "camera",
      "brightness": {
        "floor": 0.3,
        "ceiling": 1.0
      },
      "snap": "off",
      "dither": {
        "pattern": "off",
        "strength": 1.0
      }
    },
    "ramp": {
      "lightness_step": 0.12,
      "hue_shift_deg": -12.0,
      "chroma_fade": 0.3
    },
    "style": {
      "reduce": "plain",
      "edges": "hard",
      "palette": null,
      "materials": null
    },
    "stored_directions": "all",
    "direction_names": [],
    "mirrors": [],
    "export": {
      "formats": [
        "sheet"
      ],
      "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
      "atlas_path": "atlases/{clip}{map}.png",
      "sheet_path": "sheet{map}.png",
      "atlas_padding": 0
    },
    "clips": [
      {
        "name": "pose",
        "loop": true,
        "frames": null,
        "fps": null,
        "stored_directions": null,
        "mirrors": null,
        "output_name": null
      }
    ]
  },
  "fingerprint": "sha256:abb6647b2be4cea863706a6bb15a08c0aefe899825a5f60314da4a35d9c66a6c",
  "artifacts": [
    {
      "kind": "sheet",
      "channel": "color",
      "path": "hero.png",
      "width": 3,
      "height": 4,
      "padding": 0,
      "cell": {
        "width": 3,
        "height": 2
      }
    },
    {
      "kind": "sheet",
      "channel": "normal",
      "path": "hero.normal.png",
      "width": 3,
      "height": 4,
      "padding": 0,
      "cell": {
        "width": 3,
        "height": 2
      }
    },
    {
      "kind": "preview",
      "channel": "flat",
      "path": "hero.pose.gif",
      "width": 24,
      "height": 8,
      "clip": "pose"
    }
  ],
  "directions": [
    {
      "index": 0,
      "angle_deg": 0.0,
      "label": "south",
      "output_name": "south"
    },
    {
      "index": 1,
      "angle_deg": 180.0,
      "label": "north",
      "output_name": "north"
    }
  ],
  "clips": [
    {
      "name": "pose",
      "loop": true,
      "duration_s": 0.0,
      "frame_count": 1,
      "frame_duration_s": 0.08333333333333333,
      "time_scale": 1.0,
      "output_name": "pose",
      "fps": 12.0,
      "stored_directions": [
        0,
        1
      ],
      "mirrors": []
    }
  ],
  "frames": [
    {
      "clip": "pose",
      "direction": 0,
      "index": 0,
      "time_s": 0.0,
      "locations": [
        {
          "artifact": 0,
          "x": 0,
          "y": 0,
          "w": 3,
          "h": 2
        },
        {
          "artifact": 1,
          "x": 0,
          "y": 0,
          "w": 3,
          "h": 2
        }
      ]
    },
    {
      "clip": "pose",
      "direction": 1,
      "index": 0,
      "time_s": 0.0,
      "locations": [
        {
          "artifact": 0,
          "x": 0,
          "y": 2,
          "w": 3,
          "h": 2
        },
        {
          "artifact": 1,
          "x": 0,
          "y": 2,
          "w": 3,
          "h": 2
        }
      ]
    }
  ]
}
"""
