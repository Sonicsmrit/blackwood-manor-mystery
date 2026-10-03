# ==============================================================================
# PROFESSIONAL OPTIMIZED CHROMATIC ABERRATION SHADER FOR REN'PY
# Developed by: GRIMUMU (2025)
#
# # LICENSE:
# Free for use in both commercial and non-commercial projects.
# Attribution is required. Please credit "GRIMUMU" in your project.
#
# SUPPORT & SOCIALS:
# - Itch.io:    https://grimumu.itch.io/
# - Instagram:  https://www.instagram.com/grimumu__/
# - X/Twitter:  https://x.com/Grimumu_
# - Patreon:    https://www.patreon.com/c/Grimumu
#
# ==============================================================================
#
# A high-performance solution for pixel-perfect color channel splitting.
# Specialized in cinematic distortion and lens effects for high-res sprites.
#
# ==============================================================================
#
# QUICK PRESETS (For beginners):
# ------------------------------
# - at chromatic_1 ... to ... at chromatic_10
# (Increasing levels of color distortion)
#
# PARAMETERS GUIDE (For advanced users):
# --------------------------------------
# - amount: Distortion intensity in pixels.
#
# ==============================================================================

init python:
    renpy.register_shader("custom.chromatic_pro",
        variables="""
        uniform sampler2D tex0;
        uniform vec2 u_model_size;
        uniform float u_amount;
        varying vec2 v_tex_coord;
        """,
        fragment_300="""
        vec2 px_size = 1.0 / u_model_size;
        vec2 offset = vec2(u_amount, 0.0) * px_size;

        vec4 col_r = texture2D(tex0, v_tex_coord - offset);
        vec4 col_g = texture2D(tex0, v_tex_coord);
        vec4 col_b = texture2D(tex0, v_tex_coord + offset);

        gl_FragColor = vec4(col_r.r, col_g.g, col_b.b, col_g.a);
        """)

transform chromatic(amount=5.0):
    mesh True
    mesh_pad (int(amount + 2), 0, int(amount + 2), 0)
    shader "custom.chromatic_pro"
    u_amount float(amount)



# PRESETS
transform chromatic_1:
    chromatic(amount=1.0)
transform chromatic_2:
    chromatic(amount=2.0)
transform chromatic_3:
    chromatic(amount=3.0)
transform chromatic_4:
    chromatic(amount=4.0)
transform chromatic_5:
    chromatic(amount=5.0)
transform chromatic_6:
    chromatic(amount=6.0)
transform chromatic_7:
    chromatic(amount=7.0)
transform chromatic_8:
    chromatic(amount=8.0)
transform chromatic_9:
    chromatic(amount=9.0)
transform chromatic_10:
    chromatic(amount=10.0)