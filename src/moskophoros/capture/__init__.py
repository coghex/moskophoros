"""The capture boundary: versioned jobs in, validated results out.

`backend` builds jobs and validates results, following design §Capture job
and result contract. `blender` finds Blender, checks its version and runs one
capture phase. `blender_script.py`, which runs inside Blender, is the only
module that imports `bpy`, and nothing here imports it.
"""
