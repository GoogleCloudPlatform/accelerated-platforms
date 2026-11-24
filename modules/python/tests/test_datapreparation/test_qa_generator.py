# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for qa_generator module."""

import collections
import json
import unittest

from src.datapreparation.qa_generator import (
    ATTRIBUTE_LABELS,
    ATTRIBUTE_QA_TEMPLATES,
    ATTRIBUTE_SPECIFIC_QA_TEMPLATES,
    DATASET_COLUMNS,
    MAX_ATTRIBUTE_VALUE_LENGTH,
    PRODUCT_QA_TEMPLATES,
    QA_COLUMNS,
    SPLIT_TEST,
    SPLIT_TRAINING,
    SPLIT_VALIDATION,
    SPLITS,
    QAGenerator,
    clean_text,
    finalize_qa_pairs,
    format_answer,
    format_product_details,
    generate_context,
    generate_prompt,
    parse_specifications,
    split_qa_pairs,
    stable_hash,
)

CATEGORY = "Men's Clothing"
SPECIFICATIONS = json.dumps(
    {
        "Sleeve": "Half Sleeve",
        "Number of Contents in Sales Package": "Pack of 1",
        "Fabric": "Cotton",
        "Type": "Polo Neck",
        "Fit": "Slim",
        "Pattern": "Solid",
        "Occasion": "Casual",
        "Ideal For": "Men's",
        "Style Code": "NMFNHZ444",
    }
)
DETAILS = (
    "Product Name: Polo T-Shirt\n"
    "Product Category: Men's Clothing\n"
    "Product Details:\n"
    "- Sleeve: Half Sleeve\n"
    "- Number of Contents in Sales Package: Pack of 1\n"
    "- Fabric: Cotton\n"
    "- Type: Polo Neck\n"
    "- Fit: Slim\n"
    "- Pattern: Solid\n"
    "- Occasion: Casual\n"
    "- Ideal For: Men's\n"
    "- Style Code: NMFNHZ444\n"
)


def _products(count):
    """Returns products with different names and specifications."""
    fabrics = ["Cotton", "Silk", "Polyester", "Georgette"]
    return [
        {
            "Name": f"Product {index}",
            "Category": CATEGORY,
            "Specifications": json.dumps(
                {
                    "Fabric": fabrics[index % len(fabrics)],
                    "Pattern": "Solid",
                    "Occasion": "Casual",
                    "Sleeve": "Half Sleeve",
                }
            ),
        }
        for index in range(count)
    ]


class TestHelpers(unittest.TestCase):
    """Unit tests covering the text, specification and prompt helpers."""

    def test_stable_hash(self):
        """Test that the hash doesn't change, the dataset splits depend on it."""
        self.assertEqual(stable_hash("a", 1), 9484037261928657086)
        self.assertEqual(stable_hash(42, "split", "q", "a"), 18193522986031864821)
        # The parts are separated, they aren't just concatenated
        self.assertNotEqual(stable_hash("a", 1), stable_hash("a1"))

    def test_clean_text(self):
        """Test that values are converted to single line strings."""
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(float("nan")), "")
        self.assertEqual(clean_text("  Solid \n Men's   Shirt\t"), "Solid Men's Shirt")
        self.assertEqual(clean_text(42), "42")

    def test_parse_specifications(self):
        """Test that specifications are parsed in catalog order."""
        attributes = parse_specifications('{"Fabric": " Cotton ", "Fit": "Slim"}')
        self.assertEqual(
            list(attributes.items()), [("Fabric", "Cotton"), ("Fit", "Slim")]
        )
        self.assertEqual(parse_specifications({"Pack": 2}), {"Pack": "2"})

    def test_parse_specifications_skips_missing_values(self):
        """Test that attributes without a usable name or value are skipped."""
        attributes = parse_specifications(
            {"Fabric": "", "": "Cotton", "Fit": None, "Care": ["Wash"], "Type": "Top"}
        )
        self.assertEqual(attributes, {"Type": "Top"})

    def test_parse_specifications_invalid(self):
        """Test that missing or invalid specifications are parsed as empty."""
        for specifications in (None, "", float("nan"), "not json", "[1, 2]", "{"):
            self.assertEqual(parse_specifications(specifications), {})

    def test_format_product_details(self):
        """Test the product details block that is appended to the answers."""
        details = format_product_details(
            "Polo T-Shirt", CATEGORY, parse_specifications(SPECIFICATIONS)
        )
        self.assertEqual(details, DETAILS)

    def test_generate_prompt(self):
        """Test that the prompt uses the Gemma chat template turns."""
        context = generate_context(CATEGORY)
        self.assertEqual(context, "Online shopping for Men's Clothing")
        self.assertEqual(
            generate_prompt(context, "What is it?", "A shirt\n"),
            "<start_of_turn>user\nContext:Online shopping for Men's Clothing\n"
            "What is it?<end_of_turn><start_of_turn>model\nA shirt\n<end_of_turn>",
        )

    def test_templates_placeholders(self):
        """Test that every template can be formatted with the available values."""
        for question, answer in PRODUCT_QA_TEMPLATES:
            self.assertIn("N", question.format(name="N", category="C"))
            self.assertIn("N", answer.format(name="N", category="C"))
        for question, answer in ATTRIBUTE_QA_TEMPLATES:
            question = question.format(name="N", label="L", value="V")
            answer = answer.format(name="N", label="L", value="V")
            self.assertIn("N", question)
            self.assertIn("L", question)
            self.assertNotIn("V", question)
            self.assertIn("V", answer)
        for attribute, templates in ATTRIBUTE_SPECIFIC_QA_TEMPLATES.items():
            # Attributes without a label are formatted without one
            label = ATTRIBUTE_LABELS.get(attribute)
            for question, answer in templates:
                question = question.format(name="N", label=label, value="V")
                answer = answer.format(name="N", label=label, value="V")
                self.assertIn("N", question)
                self.assertNotIn("V", question)
                self.assertIn("V", answer)
                self.assertNotIn("None", question + answer)

    def test_format_answer(self):
        """Test that an answer ends with a single period."""
        template = "The fabric of {name} is {value}."
        self.assertEqual(
            format_answer(template, name="Tee", value="Cotton"),
            "The fabric of Tee is Cotton.",
        )
        self.assertEqual(
            format_answer(template, name="Tee", value="Cotton."),
            "The fabric of Tee is Cotton.",
        )

    def test_attribute_answers_wording(self):
        """Test the answers for the values that the product catalog uses."""

        def answers(templates, label, value):
            return [
                format_answer(answer, name="Tee", label=label, value=value)
                for _, answer in templates
            ]

        self.assertEqual(
            ATTRIBUTE_LABELS["number of contents in sales package"], "pack size"
        )
        self.assertEqual(
            answers(ATTRIBUTE_QA_TEMPLATES, "pack size", "Pack of 1"),
            [
                "The pack size of Tee is Pack of 1.",
                "Sure! The pack size of Tee is Pack of 1.",
                "The pack size of Tee is Pack of 1.",
                "Of course! The pack size of Tee is Pack of 1.",
            ],
        )
        specific = ATTRIBUTE_SPECIFIC_QA_TEMPLATES
        self.assertEqual(
            answers(specific["occasion"], None, "Casual, Lounge Wear"),
            [
                "Tee is suitable for these occasions: Casual, Lounge Wear.",
                "You can wear Tee on these occasions: Casual, Lounge Wear.",
            ],
        )
        self.assertEqual(
            answers(specific["ideal for"], None, "Women's"),
            ["Tee is ideal for Women's wear.", "Tee is designed as Women's wear."],
        )
        self.assertEqual(
            answers(specific["fabric"], "fabric", "Cotton"), ["Tee is made of Cotton."]
        )
        self.assertEqual(
            answers(specific["pattern"], "pattern", "Solid"),
            ["The pattern of Tee is Solid."],
        )

    def test_attribute_names_are_lower_case(self):
        """Test that the attribute names can be matched in lower case."""
        for attribute in list(ATTRIBUTE_LABELS) + list(ATTRIBUTE_SPECIFIC_QA_TEMPLATES):
            self.assertEqual(attribute, attribute.lower())


class TestQAGenerator(unittest.TestCase):
    """Unit tests covering QAGenerator."""

    def setUp(self):
        self.generator = QAGenerator(num_questions=3, seed=42)

    def test_invalid_configuration(self):
        """Test that an invalid configuration is rejected."""
        with self.assertRaises(ValueError):
            QAGenerator(num_questions=0)
        with self.assertRaises(ValueError):
            QAGenerator(train_ratio=0)
        with self.assertRaises(ValueError):
            QAGenerator(train_ratio=1)
        with self.assertRaises(ValueError):
            QAGenerator(validation_ratio=-0.1)
        with self.assertRaises(ValueError):
            QAGenerator(train_ratio=0.8, validation_ratio=0.3)

    def test_generate_for_product(self):
        """Test the question and answer pairs generated for a product."""
        rows = self.generator.generate_for_product(
            "Polo T-Shirt", CATEGORY, SPECIFICATIONS
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["Question"] for row in rows}), 3)
        for row in rows:
            self.assertEqual(list(row), QA_COLUMNS)
            self.assertIn("Polo T-Shirt", row["Question"])
            # The answer is a sentence followed by the product details
            sentence, details = row["Answer"].split(" \n", 1)
            self.assertIn("Polo T-Shirt", sentence)
            self.assertEqual(details, DETAILS)
            self.assertEqual(row["Context"], "Online shopping for Men's Clothing")
            self.assertEqual(
                row["prompt"],
                generate_prompt(row["Context"], row["Question"], row["Answer"]),
            )
            self.assertIn(row["split"], SPLITS)

    def test_generate_for_product_golden(self):
        """Test that the pairs of a product and a seed never change.

        The dataset of a seed is only reproducible as long as the templates,
        the selection of the questions and the split assignment don't change.
        Update the expected values when one of them is changed on purpose.
        """
        rows = self.generator.generate_for_product(
            "Polo T-Shirt", CATEGORY, SPECIFICATIONS
        )
        self.assertEqual(
            [
                (row["Question"], row["Answer"].split(" \n", 1)[0], row["split"])
                for row in rows
            ],
            [
                (
                    "Can you tell me more about Polo T-Shirt?",
                    "Sure! Here is what I found about Polo T-Shirt.",
                    "training",
                ),
                (
                    "What pattern does Polo T-Shirt have?",
                    "The pattern of Polo T-Shirt is Solid.",
                    "training",
                ),
                (
                    "What occasion is Polo T-Shirt suitable for?",
                    "Polo T-Shirt is suitable for these occasions: Casual.",
                    "training",
                ),
            ],
        )

        rows = QAGenerator(num_questions=3, seed=7).generate_for_product(
            "Polo T-Shirt", CATEGORY, SPECIFICATIONS
        )
        self.assertEqual(
            [row["Question"] for row in rows],
            [
                "Could you show me the specifications of Polo T-Shirt?",
                "Who is Polo T-Shirt designed for?",
                "What is the pack size of Polo T-Shirt?",
            ],
        )

    def test_generate_for_product_questions(self):
        """Test that one question is about the product and the others about attributes."""
        product_questions = {
            question.format(name="Polo T-Shirt", category=CATEGORY)
            for question, _ in PRODUCT_QA_TEMPLATES
        }
        attribute_values = set(parse_specifications(SPECIFICATIONS).values())

        rows = self.generator.generate_for_product(
            "Polo T-Shirt", CATEGORY, SPECIFICATIONS
        )

        self.assertIn(rows[0]["Question"], product_questions)
        for row in rows[1:]:
            self.assertNotIn(row["Question"], product_questions)
            sentence = row["Answer"].split(" \n", 1)[0]
            self.assertTrue(any(value in sentence for value in attribute_values))

    def test_generate_for_product_without_specifications(self):
        """Test that product questions are used when there are no attributes."""
        for specifications in (None, "{}", '{"Style Code": "X1"}'):
            rows = self.generator.generate_for_product(
                "Plain Tee", CATEGORY, specifications
            )
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({row["Question"] for row in rows}), 3)

    def test_generate_for_product_missing_name_or_category(self):
        """Test that products without a name or a category are skipped."""
        self.assertEqual(self.generator.generate_for_product(None, CATEGORY), [])
        self.assertEqual(self.generator.generate_for_product("  ", CATEGORY), [])
        self.assertEqual(self.generator.generate_for_product("Tee", None), [])
        self.assertEqual(self.generator.generate_for_product("Tee", float("nan")), [])

    def test_generate_for_product_skips_unsuitable_values(self):
        """Test that long and uninformative values aren't used for questions."""
        specifications = {
            "Fabric": "x" * (MAX_ATTRIBUTE_VALUE_LENGTH + 1),
            "Closure": "N/A",
            "Inner Lining": "Yes",
        }
        product_questions = {
            question.format(name="Tee", category=CATEGORY)
            for question, _ in PRODUCT_QA_TEMPLATES
        }

        rows = QAGenerator(num_questions=5).generate_for_product(
            "Tee", CATEGORY, specifications
        )

        self.assertEqual({row["Question"] for row in rows}, product_questions)
        # The values are still listed in the product details
        self.assertIn("- Closure: N/A\n", rows[0]["Answer"])

    def test_generate_for_product_shared_label(self):
        """Test that attributes that share a label only generate one question."""
        specifications = {"Color": "Red", "Brand Color": "Crimson", "color": "Red"}
        rows = QAGenerator(num_questions=10).generate_for_product(
            "Tee", CATEGORY, specifications
        )

        questions = [row["Question"] for row in rows]
        self.assertEqual(len(questions), len(set(questions)))
        # The 5 product questions and 1 question about the color
        self.assertEqual(len(rows), len(PRODUCT_QA_TEMPLATES) + 1)

    def test_generate_for_product_num_questions(self):
        """Test that the number of questions per product is configurable."""
        for num_questions in (1, 2, 5, 8):
            rows = QAGenerator(num_questions=num_questions).generate_for_product(
                "Polo T-Shirt", CATEGORY, SPECIFICATIONS
            )
            self.assertEqual(len(rows), num_questions)
            self.assertEqual(len({row["Question"] for row in rows}), num_questions)

    def test_generate(self):
        """Test that pairs are generated for every product."""
        rows = self.generator.generate(_products(4) + [{"Name": None}])
        self.assertEqual(len(rows), 12)

    def test_generate_is_reproducible(self):
        """Test that the pairs don't depend on the order or batching of the products."""
        products = _products(20)
        expected = {json.dumps(row) for row in self.generator.generate(products)}

        actual = set()
        for product in reversed(products):
            for row in QAGenerator(num_questions=3, seed=42).generate([product]):
                actual.add(json.dumps(row))

        self.assertEqual(actual, expected)

    def test_generate_identical_products(self):
        """Test that identical products generate identical pairs."""
        product = _products(1)[0]
        rows = self.generator.generate([product, dict(product)])
        self.assertEqual(rows[:3], rows[3:])

    def test_seed_changes_questions(self):
        """Test that a different seed selects different questions."""
        products = _products(20)
        questions = [row["Question"] for row in self.generator.generate(products)]
        other_questions = [
            row["Question"]
            for row in QAGenerator(num_questions=3, seed=7).generate(products)
        ]
        self.assertNotEqual(questions, other_questions)

    def test_assign_split(self):
        """Test that the pairs are split with the configured ratios."""
        counts = collections.Counter(
            self.generator.assign_split(f"question {index}", f"answer {index}")
            for index in range(5000)
        )

        self.assertEqual(set(counts), set(SPLITS))
        self.assertAlmostEqual(counts[SPLIT_TRAINING] / 5000, 0.8, delta=0.03)
        self.assertAlmostEqual(counts[SPLIT_VALIDATION] / 5000, 0.1, delta=0.03)
        self.assertAlmostEqual(counts[SPLIT_TEST] / 5000, 0.1, delta=0.03)
        # The assignment of a pair to a split never changes for a seed
        self.assertEqual(
            [
                self.generator.assign_split(f"question {index}", f"answer {index}")
                for index in range(7)
            ],
            [
                SPLIT_TRAINING,
                SPLIT_TRAINING,
                SPLIT_TEST,
                SPLIT_TRAINING,
                SPLIT_TRAINING,
                SPLIT_VALIDATION,
                SPLIT_TEST,
            ],
        )
        self.assertEqual(
            QAGenerator(seed=7).assign_split("question 0", "answer 0"),
            SPLIT_VALIDATION,
        )

    def test_assign_split_without_validation(self):
        """Test that the validation split can be disabled."""
        generator = QAGenerator(train_ratio=0.9, validation_ratio=0)
        splits = {
            generator.assign_split(f"question {index}", "answer")
            for index in range(500)
        }
        self.assertEqual(splits, {SPLIT_TRAINING, SPLIT_TEST})

    def test_generate_for_product_has_a_training_pair(self):
        """Test that at least one pair of every product is in the training split."""
        generator = QAGenerator(num_questions=3, train_ratio=0.05, validation_ratio=0.5)
        moved = 0
        for product in _products(40):
            rows = generator.generate([product])
            splits = [row["split"] for row in rows]
            assigned = [
                generator.assign_split(row["Question"], row["Answer"]) for row in rows
            ]

            if SPLIT_TRAINING in assigned:
                self.assertEqual(splits, assigned)
            else:
                # Only the first pair is moved to the training split
                self.assertEqual(splits, [SPLIT_TRAINING] + assigned[1:])
                moved += 1

        self.assertGreater(moved, 0)
        self.assertLess(moved, 40)


class TestDataset(unittest.TestCase):
    """Unit tests covering finalize_qa_pairs and split_qa_pairs."""

    def setUp(self):
        self.rows = QAGenerator().generate(_products(10))

    def test_finalize_qa_pairs_removes_duplicates(self):
        """Test that duplicate pairs are removed."""
        rows = finalize_qa_pairs(self.rows + self.rows[:5])
        self.assertEqual(len(rows), len(self.rows))
        self.assertCountEqual(
            [row["Question"] for row in rows], [row["Question"] for row in self.rows]
        )

    def test_finalize_qa_pairs_order(self):
        """Test that the order doesn't depend on the order of the input."""
        rows = finalize_qa_pairs(self.rows)
        self.assertEqual(finalize_qa_pairs(list(reversed(self.rows))), rows)
        # The pairs of a product aren't kept together
        self.assertNotEqual(rows, self.rows)
        self.assertNotEqual(finalize_qa_pairs(self.rows, seed=7), rows)

    def test_finalize_qa_pairs_empty(self):
        """Test that an empty input is supported."""
        self.assertEqual(finalize_qa_pairs([]), [])

    def test_split_qa_pairs(self):
        """Test that the pairs are routed to their split."""
        splits = split_qa_pairs(self.rows)

        self.assertEqual(list(splits), list(SPLITS))
        total = 0
        for split, columns in splits.items():
            self.assertEqual(list(columns), DATASET_COLUMNS)
            expected = [row["prompt"] for row in self.rows if row["split"] == split]
            self.assertEqual(columns["prompt"], expected)
            for column in DATASET_COLUMNS:
                self.assertEqual(len(columns[column]), len(expected))
            total += len(expected)
        self.assertEqual(total, len(self.rows))

    def test_split_qa_pairs_empty(self):
        """Test that every split and column exists when there are no pairs."""
        splits = split_qa_pairs([])
        for split in SPLITS:
            self.assertEqual(splits[split], {column: [] for column in DATASET_COLUMNS})


if __name__ == "__main__":
    unittest.main()
