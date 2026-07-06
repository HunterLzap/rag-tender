"""标书长文本分块回归测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.text_chunks import split_text_chunks


class SplitTextChunksTests(unittest.TestCase):
    def test_text_just_over_chunk_size_terminates_with_two_chunks(self) -> None:
        text = "x" * 25001

        chunks = split_text_chunks(text, chunk_size=25000, overlap=2000)

        self.assertEqual(2, len(chunks))
        self.assertEqual(25000, len(chunks[0]))
        self.assertEqual(2001, len(chunks[1]))
        self.assertEqual(text, chunks[0] + chunks[1][2000:])

    def test_long_text_has_finite_chunks_and_preserves_overlap(self) -> None:
        text = "".join(chr(65 + i % 26) for i in range(100000))

        chunks = split_text_chunks(text, chunk_size=25000, overlap=2000)

        self.assertEqual(5, len(chunks))
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous[-2000:], current[:2000])

        rebuilt = chunks[0] + "".join(chunk[2000:] for chunk in chunks[1:])
        self.assertEqual(text, rebuilt)

    def test_overlap_must_be_smaller_than_chunk_size(self) -> None:
        with self.assertRaises(ValueError):
            split_text_chunks("content", chunk_size=2000, overlap=2000)

    def test_rejects_unreasonable_chunk_count(self) -> None:
        with self.assertRaises(ValueError):
            split_text_chunks(
                "x" * 10000,
                chunk_size=1000,
                overlap=100,
                max_chunks=5,
            )


if __name__ == "__main__":
    unittest.main()
