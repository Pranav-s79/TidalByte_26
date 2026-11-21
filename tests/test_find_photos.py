from flood.find_photos import matches

POINT = {"lat": 29.689, "lon": -95.437}


def img(id_, dlat, dlon, heading, pano=False):
    return {"id": id_, "captured_at": 1431805423500, "compass_angle": heading, "is_pano": pano,
            "computed_geometry": {"type": "Point", "coordinates": [POINT["lon"] + dlon, POINT["lat"] + dlat]}}


def test_facing_first_then_nearest_and_radius_cut():
    south_looking_north = img("a", -0.0003, 0, 0)     # ~33 m south, heading north: sees the point
    south_looking_south = img("b", -0.0001, 0, 180)   # ~11 m south, heading away
    pano_far = img("c", 0.0004, 0, 90, pano=True)     # ~45 m north, 360°: always sees it
    too_far = img("d", 0.001, 0, 180)                 # ~111 m: outside 50 m
    out = matches(POINT, [south_looking_south, too_far, pano_far, south_looking_north], 50)
    assert [m["id"] for m in out] == ["a", "c", "b"]
    assert [m["faces_point"] for m in out] == [True, True, False]
    assert out[0]["captured_at"] == "2015-05-16" and out[0]["license"] == "CC BY-SA 4.0"


def test_pano_view_looks_where_asked():
    import numpy as np
    from flood.find_photos import pano_view
    pano = np.zeros((90, 360, 3), np.uint8)
    pano[:, 90:180] = (255, 0, 0)   # west of centre: compass 180-270 if centre (col 180) is heading 270
    pano[:, 180:270] = (0, 0, 255)  # east of centre: compass 270-360
    left = pano_view(pano, pano_heading=270, yaw=225, fov=60, size=(40, 30))
    right = pano_view(pano, pano_heading=270, yaw=315, fov=60, size=(40, 30))
    assert left[15, 20].tolist() == [255, 0, 0] and right[15, 20].tolist() == [0, 0, 255]
