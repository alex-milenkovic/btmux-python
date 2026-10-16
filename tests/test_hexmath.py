"""
Simple tests for hexmath module.

Run with: python -m pytest tests/test_hexmath.py -v
Or just:  python tests/test_hexmath.py
"""

import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from physics.hexmath import (
    hex_to_float, float_to_hex, find_components, find_bearing,
    hex_distance, hex_bearing, normalize_heading, heading_difference,
    turn_direction, SCALEMAP, ALPHA
)


def test_hex_to_float_origin():
    """Test hex (0,0) converts to expected cartesian coords."""
    x, y = hex_to_float(0, 0)
    # hex_x=0: cart_x = (2 + 0) * ALPHA = 2 * ALPHA
    # hex_y=0, even column: cart_y = HALF_Y + 0 = SCALEMAP/2
    expected_x = 2 * ALPHA
    expected_y = SCALEMAP / 2
    assert abs(x - expected_x) < 0.01, f"Expected x={expected_x}, got {x}"
    assert abs(y - expected_y) < 0.01, f"Expected y={expected_y}, got {y}"
    print(f"hex(0,0) -> ({x:.2f}, {y:.2f})")


def test_hex_to_float_column_offset():
    """Test that even/odd columns have different Y offsets."""
    # Even column (0) - has HALF_Y offset
    _, y0 = hex_to_float(0, 0)
    # Odd column (1) - no offset
    _, y1 = hex_to_float(1, 0)

    # y0 should be HALF_Y higher than y1 for same row
    diff = y0 - y1
    expected = SCALEMAP / 2
    assert abs(diff - expected) < 0.01, f"Expected diff={expected}, got {diff}"
    print(f"Column offset test: even y={y0:.2f}, odd y={y1:.2f}, diff={diff:.2f}")


def test_float_to_hex_roundtrip():
    """Test that hex->float->hex roundtrips correctly."""
    test_coords = [
        (0, 0), (1, 0), (0, 1), (1, 1),
        (5, 5), (10, 10), (3, 7),
    ]
    for hx, hy in test_coords:
        fx, fy = hex_to_float(hx, hy)
        hx2, hy2 = float_to_hex(fx, fy)
        assert (hx, hy) == (hx2, hy2), f"Roundtrip failed: ({hx},{hy}) -> ({fx:.2f},{fy:.2f}) -> ({hx2},{hy2})"
    print("Roundtrip tests passed for multiple coordinates")


def test_find_components_north():
    """Test that heading 0 (North) gives negative Y (up)."""
    dx, dy = find_components(100.0, 0)
    assert abs(dx) < 0.01, f"North should have dx~0, got {dx}"
    assert dy < 0, f"North should have negative dy, got {dy}"
    print(f"North (0 deg) at speed 100: dx={dx:.2f}, dy={dy:.2f}")


def test_find_components_east():
    """Test that heading 90 (East) gives positive X."""
    dx, dy = find_components(100.0, 90)
    assert dx > 0, f"East should have positive dx, got {dx}"
    assert abs(dy) < 0.01, f"East should have dy~0, got {dy}"
    print(f"East (90 deg) at speed 100: dx={dx:.2f}, dy={dy:.2f}")


def test_find_components_south():
    """Test that heading 180 (South) gives positive Y (down)."""
    dx, dy = find_components(100.0, 180)
    assert abs(dx) < 0.01, f"South should have dx~0, got {dx}"
    assert dy > 0, f"South should have positive dy, got {dy}"
    print(f"South (180 deg) at speed 100: dx={dx:.2f}, dy={dy:.2f}")


def test_find_components_west():
    """Test that heading 270 (West) gives negative X."""
    dx, dy = find_components(100.0, 270)
    assert dx < 0, f"West should have negative dx, got {dx}"
    assert abs(dy) < 0.01, f"West should have dy~0, got {dy}"
    print(f"West (270 deg) at speed 100: dx={dx:.2f}, dy={dy:.2f}")


def test_find_bearing_cardinal():
    """Test bearings for cardinal directions."""
    # From origin to points in cardinal directions
    # North: negative Y
    bearing = find_bearing(0, 0, 0, -100)
    assert bearing == 0, f"North bearing should be 0, got {bearing}"

    # C FindBearing adds 5 before signed integer division:
    # (-900 + 5) / 10 truncates to -89, then adding 180 gives 91.
    bearing = find_bearing(0, 0, 100, 0)
    assert bearing == 91, f"East bearing should match C signed rounding (91), got {bearing}"

    # South: positive Y
    bearing = find_bearing(0, 0, 0, 100)
    assert bearing == 180, f"South bearing should be 180, got {bearing}"

    # West: negative X
    bearing = find_bearing(0, 0, -100, 0)
    assert bearing == 270, f"West bearing should be 270, got {bearing}"

    print("Cardinal bearing tests passed")


def test_hex_distance_same():
    """Test that distance to same hex is ~0."""
    dist = hex_distance(5, 5, 5, 5)
    assert dist < 0.01, f"Same hex distance should be ~0, got {dist}"
    print(f"Distance (5,5) to (5,5): {dist:.4f}")


def test_hex_distance_adjacent():
    """Test distance to adjacent hexes is ~1."""
    # Adjacent hex (same column, next row)
    dist = hex_distance(0, 0, 0, 1)
    assert 0.9 < dist < 1.1, f"Adjacent hex distance should be ~1, got {dist}"
    print(f"Distance (0,0) to (0,1): {dist:.4f}")

    # Adjacent hex (next column)
    dist = hex_distance(0, 0, 1, 0)
    assert 0.9 < dist < 1.1, f"Adjacent hex distance should be ~1, got {dist}"
    print(f"Distance (0,0) to (1,0): {dist:.4f}")


def test_normalize_heading():
    """Test heading normalization."""
    assert normalize_heading(0) == 0
    assert normalize_heading(359) == 359
    assert normalize_heading(360) == 0
    assert normalize_heading(450) == 90
    assert normalize_heading(-90) == 270
    print("Heading normalization tests passed")


def test_heading_difference():
    """Test heading difference calculations."""
    assert heading_difference(0, 0) == 0
    assert heading_difference(0, 90) == 90
    assert heading_difference(0, 180) == 180
    assert heading_difference(0, 270) == 90  # Shorter way around
    assert heading_difference(350, 10) == 20  # Across 0
    print("Heading difference tests passed")


def test_turn_direction():
    """Test turn direction calculation."""
    assert turn_direction(0, 0) == 0
    assert turn_direction(0, 90) == 1   # Turn right
    assert turn_direction(0, 270) == -1  # Turn left (shorter)
    assert turn_direction(350, 10) == 1  # Turn right across 0
    assert turn_direction(10, 350) == -1  # Turn left across 0
    print("Turn direction tests passed")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_hex_to_float_origin,
        test_hex_to_float_column_offset,
        test_float_to_hex_roundtrip,
        test_find_components_north,
        test_find_components_east,
        test_find_components_south,
        test_find_components_west,
        test_find_bearing_cardinal,
        test_hex_distance_same,
        test_hex_distance_adjacent,
        test_normalize_heading,
        test_heading_difference,
        test_turn_direction,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\n--- {test.__name__} ---")
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
