"""Fluid composition from integer areas, including complements of box unions."""

from numbers import Integral

from .oleo_residual_recuperacao import calculate_residual_oil

CLASS_NAMES = ("Water", "Oil", "Gas")


def composition_from_counts(class_pixels, wall_px=0):
    residual = calculate_residual_oil(class_pixels)
    if isinstance(wall_px, bool) or not isinstance(wall_px, Integral) or wall_px < 0:
        raise ValueError("Wall area must be a nonnegative integer")
    counts = {name: int(class_pixels[name]) for name in CLASS_NAMES}
    fluid = residual["initial_oil_equivalent_px"]
    fractions = {
        name: count / fluid if fluid else None for name, count in counts.items()
    }
    return {
        "area_px": fluid + int(wall_px),
        "fluid_area_px": fluid,
        "excluded_wall_px": int(wall_px),
        "class_pixels": counts,
        "class_fractions": fractions,
        "class_percentages": {
            name: value * 100 if value is not None else None
            for name, value in fractions.items()
        },
        "dominant_class": max(counts, key=counts.get) if fluid else None,
        "residual_oil": residual,
    }


def outside_deadend_composition(full_image, deadends_union):
    """Subtract the union counts, never the sum of overlapping box counts."""
    return composition_from_counts(
        {
            name: full_image["class_pixels"][name]
            - deadends_union["class_pixels"][name]
            for name in CLASS_NAMES
        },
        full_image.get("excluded_wall_px", 0)
        - deadends_union.get("excluded_wall_px", 0),
    )
