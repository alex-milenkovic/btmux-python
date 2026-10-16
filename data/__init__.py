"""Data templates - mech definitions, weapon stats."""

from .templates import (
    # Dataclasses
    ArmorLayout,
    WeaponMount,
    MechTemplate,
    # Factory functions
    create_mech_from_template,
    create_weapon_slots_from_template,
    # Template registry
    MECH_TEMPLATES,
    get_template,
    list_templates,
    # Pre-defined templates
    TEST_MECH_TEMPLATE,
    ASSAULT_MECH_TEMPLATE,
    LIGHT_MECH_TEMPLATE,
)

__all__ = [
    # Dataclasses
    "ArmorLayout",
    "WeaponMount",
    "MechTemplate",
    # Factory functions
    "create_mech_from_template",
    "create_weapon_slots_from_template",
    # Template registry
    "MECH_TEMPLATES",
    "get_template",
    "list_templates",
    # Pre-defined templates
    "TEST_MECH_TEMPLATE",
    "ASSAULT_MECH_TEMPLATE",
    "LIGHT_MECH_TEMPLATE",
]
