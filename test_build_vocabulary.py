import unittest
import tempfile
from collections import Counter
from pathlib import Path

from build_vocabulary import (
    choose_examples, normalize_text, reading_order, sentence_quality, tokens, write_outputs,
)


class VocabularyTests(unittest.TestCase):
    def test_function_words_and_case(self):
        self.assertEqual(list(tokens("The model and THE models, or a model.")),
                         ["the", "model", "and", "the", "models", "or", "a", "model"])

    def test_token_boundaries(self):
        self.assertEqual(list(tokens("x y I a GPT3 gpt-4 don't model's https://example.org mail@openai.com")),
                         ["i", "a", "gpt", "don't", "model"])

    def test_normalization(self):
        self.assertEqual(normalize_text("classiﬁcation trans-\nformer fine-\ntuning"),
                         "classification transformer fine-tuning")

    def test_sentence_quality(self):
        self.assertIsNotNone(sentence_quality("The model learns useful representations from the training data."))
        self.assertIsNone(sentence_quality("The model learns useful representations"))
        self.assertIsNone(sentence_quality("1 2 3 4 = x + y."))
        self.assertIsNone(sentence_quality("Table 3: Results on question answering and commonsense reasoning."))

    def test_column_order(self):
        def block(name, x0, y0, x1):
            return {"text": name, "bbox": [x0, y0, x1, y0 + 10]}
        blocks = [
            block("right2", 320, 150, 550), block("left1", 50, 100, 290),
            block("heading", 50, 50, 550), block("right1", 320, 100, 550),
            block("left2", 50, 150, 290),
        ]
        self.assertEqual([b["text"] for b in reading_order(blocks, 600)],
                         ["heading", "left1", "left2", "right1", "right2"])

    def test_examples_prefer_different_papers(self):
        records = [
            {"text": "The model learns from training data.", "score": 1, "paper_number": 1, "id": "a"},
            {"text": "This model learns from other data.", "score": 2, "paper_number": 1, "id": "b"},
            {"text": "A model can generalize to new tasks.", "score": 3, "paper_number": 2, "id": "c"},
        ]
        self.assertEqual([r["id"] for r in choose_examples("model", [0, 1, 2], records)], ["a", "c"])

    def test_single_example(self):
        records = [{"text": "A model learns.", "score": 1, "paper_number": 1, "id": "a"}]
        self.assertEqual(len(choose_examples("model", [0], records)), 1)

    def test_markdown_files_are_written(self):
        paper = {"number": 1, "key": "test", "title": "Test", "path": "test.pdf"}
        extracted = [{"paper": paper, "sha256": "abc", "pages": [{
            "page": 1, "method": "text", "blocks": [{
                "text": "The model learns from data.", "bbox": [0, 0, 100, 100],
            }],
        }]}]
        record = {
            "id": "P01-S00001", "paper_number": 1, "paper_key": "test",
            "paper_title": "Test", "pdf_path": "test.pdf", "pages": [1],
            "blocks": [{"page": 1, "block": 1}], "ocr": False,
            "text": "The model learns from data.", "score": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_outputs(output, extracted, [record], Counter({"model": 2, "data": 1}),
                          Counter({"model": 1, "data": 1}), [("model", 2), ("data", 1)], 1)
            files = sorted((output / "notebooks").glob("*.md"))
            self.assertEqual(len(files), 2)
            self.assertIn("## 0001. model", files[0].read_text())
            self.assertIn("## 0002. data", files[1].read_text())


if __name__ == "__main__":
    unittest.main()
