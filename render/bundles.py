"""Curated tract bundles for INI Austin imagery.

Chosen for two reasons at once: they spread well through the volume so the
render reads as a whole brain, and each one means something the chapter
actually cares about. Colour is cool-dominant with two warm accents so the
image stays on-brand while individual bundles remain separable.
"""

CURATED = [
    # file stem,                                        colour,     label
    ("Commissure_CorpusCallosum",                       "#79E4FF", "Corpus callosum"),
    ("Association_ArcuateFasciculusL",                  "#3E8CFF", "Arcuate fasciculus (L)"),
    ("Association_ArcuateFasciculusR",                  "#3E8CFF", "Arcuate fasciculus (R)"),
    ("Association_SuperiorLongitudinalFasciculusL",     "#63C8E6", "Superior longitudinal (L)"),
    ("Association_SuperiorLongitudinalFasciculusR",     "#63C8E6", "Superior longitudinal (R)"),
    ("Association_InferiorLongitudinalFasciculusL",     "#9FB4FF", "Inferior longitudinal (L)"),
    ("Association_InferiorLongitudinalFasciculusR",     "#9FB4FF", "Inferior longitudinal (R)"),
    ("Association_UncinateFasciculusL",                 "#C6A3FF", "Uncinate (L)"),
    ("Association_UncinateFasciculusR",                 "#C6A3FF", "Uncinate (R)"),
    ("Association_CingulumR",                           "#7BE6C4", "Cingulum (R)"),
    ("Association_FrontalAslantTractL",                 "#FFD08A", "Frontal aslant (L)"),
    ("Association_FrontalAslantTractR",                 "#FFD08A", "Frontal aslant (R)"),
    ("ProjectionBasalGanglia_ThalamicRadiationL",       "#E4EEFF", "Thalamic radiation (L)"),
    ("ProjectionBasalGanglia_ThalamicRadiationR",       "#E4EEFF", "Thalamic radiation (R)"),
    ("ProjectionBrainstem_CorticopontineTractL",        "#AEDBFF", "Corticopontine (L)"),
    ("ProjectionBrainstem_CorticopontineTractR",        "#AEDBFF", "Corticopontine (R)"),
    ("Association_VerticalOccipitalFasciculusL",        "#8FD8F0", "Vertical occipital (L)"),
    ("Association_VerticalOccipitalFasciculusR",        "#8FD8F0", "Vertical occipital (R)"),
]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
