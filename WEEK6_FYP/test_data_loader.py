"""Checks that Week 6 reads the real FYP sources without copying them."""
from pathlib import Path
import sys
import unittest

WEEK6 = Path(__file__).resolve().parent.parent / "Week 6"
sys.path.insert(0, str(WEEK6))
import app as week6_app  # noqa: E402


class RealDataLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = week6_app.load_documents()

    def test_expected_raw_document_count(self):
        self.assertEqual(len(self.documents), 37533)

    def test_document_fields_and_real_source_paths(self):
        required = {"id", "title", "text", "type", "source", "source_file"}
        self.assertTrue(self.documents)
        self.assertTrue(all(required <= document.keys() for document in self.documents))
        self.assertTrue(all((week6_app.REPO / document["source"]).is_file() for document in self.documents))
        self.assertEqual(sum(week6_app.SOURCE_COUNTS.values()), len(self.documents))
        self.assertEqual(week6_app.DATA_DIR, week6_app.REPO / "FYP_Data")


if __name__ == "__main__":
    unittest.main()
