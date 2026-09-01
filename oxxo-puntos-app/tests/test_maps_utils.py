import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.maps_utils import extract_coordinates_from_map_url


class MapUrlCoordinatesTest(unittest.TestCase):
    def test_google_at_coordinates(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/@4.710989,-74.072092,15z"
            ),
            (4.710989, -74.072092),
        )

    def test_google_at_coordinates_with_apostrophes_in_place_name(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/place/4%C2%B034'19.2%22N+74%C2%B005'35.7%22W/@4.5833175,-74.191013,12z/data=!4m4!3m3!8m2!3d4.572!4d-74.09325"
            ),
            (4.5833175, -74.191013),
        )

    def test_google_encoded_place_coordinates(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/place/x/data=!3d4.711%214d-74.072"
            ),
            (4.711, -74.072),
        )

    def test_query_coordinate_pair(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/search/?api=1&query=4.711%2C-74.072"
            ),
            (4.711, -74.072),
        )

    def test_separate_latitude_longitude_parameters(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://example.test/map?latitude=4.711&longitude=-74.072"
            ),
            (4.711, -74.072),
        )

    def test_bing_coordinates(self):
        self.assertEqual(
            extract_coordinates_from_map_url(
                "https://www.bing.com/maps?cp=4.711%7E-74.072&lvl=15"
            ),
            (4.711, -74.072),
        )

    def test_rejects_incomplete_or_invalid_coordinates(self):
        self.assertIsNone(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/search/?api=1&query=4.711"
            )
        )
        self.assertIsNone(
            extract_coordinates_from_map_url(
                "https://www.google.com/maps/@194.711,-274.072,15z"
            )
        )


if __name__ == "__main__":
    unittest.main()
