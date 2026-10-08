import json
from pathlib import Path
import unittest

from app.dataset.sroie_loader import SROIELoader


class SROIELoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = SROIELoader(Path("data/raw"))

    def test_discovers_expected_splits_and_counts(self):
        self.assertEqual(self.loader.dataset_root.name, "SROIE2019")
        self.assertEqual(len(list(self.loader.iter_examples("train"))), 626)
        self.assertEqual(len(list(self.loader.iter_examples("test"))), 347)

    def test_normalizes_and_preserves_annotation_data(self):
        example = self.loader.load_example("train", "X00016469612")
        self.assertEqual(example.company, "BOOK TA .K (TAMAN DAYA) SDN BHD")
        self.assertEqual(json.loads(example.entity_annotation_text)["total"], "9.00")
        boxes = self.loader.load_box_annotation("train", example.document_id)
        self.assertEqual(len(boxes), 44)
        self.assertEqual(boxes[0]["text"], "TAN WOON YANN")


if __name__ == "__main__":
    unittest.main()