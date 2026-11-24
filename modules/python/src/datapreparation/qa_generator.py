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

"""Template based question and answer generation for instruction tuning datasets.

Turns product catalog records into shopping style question and answer pairs
without calling a large language model. Generation is a pure function of the
product data and a seed, so the resulting dataset is reproducible and can be
generated in parallel, in any order and with any batch size.
"""

import hashlib
import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

logger = logging.getLogger(__name__)

# Splits of the generated dataset
SPLIT_TRAINING = "training"
SPLIT_VALIDATION = "validation"
SPLIT_TEST = "test"
SPLITS = (SPLIT_TRAINING, SPLIT_VALIDATION, SPLIT_TEST)

# Columns of the generated dataset, 'split' is used to route a row to its split
DATASET_COLUMNS = ["Question", "Answer", "Context", "prompt"]
SPLIT_COLUMN = "split"
QA_COLUMNS = DATASET_COLUMNS + [SPLIT_COLUMN]

# Columns of the product catalog used to generate the questions and answers
PRODUCT_NAME_COLUMN = "Name"
PRODUCT_CATEGORY_COLUMN = "Category"
PRODUCT_SPECIFICATIONS_COLUMN = "Specifications"

# Attribute values longer than this are listed in the product details but are
# not used to phrase a question, long values are usually free text
MAX_ATTRIBUTE_VALUE_LENGTH = 60

# Lower case attribute values that don't make a meaningful answer on their own,
# they are listed in the product details but are not used to phrase a question
UNINFORMATIVE_ATTRIBUTE_VALUES = frozenset(
    {"-", "n/a", "na", "no", "none", "not applicable", "yes"}
)

_HASH_SEPARATOR = "\x1f"

# Questions about the product as a whole: (question, answer)
PRODUCT_QA_TEMPLATES: Tuple[Tuple[str, str], ...] = (
    (
        "Can you tell me more about {name}?",
        "Sure! Here is what I found about {name}.",
    ),
    (
        "I'm looking for {name}. Do you have it?",
        "Yes, we have {name} in our {category} catalog.",
    ),
    (
        "What are the product details of {name}?",
        "Here are the product details of {name}.",
    ),
    (
        "Which category does {name} belong to?",
        "{name} belongs to {category}.",
    ),
    (
        "Could you show me the specifications of {name}?",
        "Of course! These are the specifications of {name}.",
    ),
)

# Questions about an attribute that reads naturally as "the <label> of <name>":
# (question, answer)
ATTRIBUTE_QA_TEMPLATES: Tuple[Tuple[str, str], ...] = (
    (
        "What is the {label} of {name}?",
        "The {label} of {name} is {value}.",
    ),
    (
        "Can you tell me the {label} of {name}?",
        "Sure! The {label} of {name} is {value}.",
    ),
    (
        "I'm interested in {name}. What is its {label}?",
        "The {label} of {name} is {value}.",
    ),
    (
        "Could you help me find out the {label} of {name}?",
        "Of course! The {label} of {name} is {value}.",
    ),
)

# Lower case attribute name -> label used in ATTRIBUTE_QA_TEMPLATES
ATTRIBUTE_LABELS: Dict[str, str] = {
    "brand color": "color",
    "closure": "closure type",
    "collar": "collar type",
    "color": "color",
    "cup type": "cup type",
    "fabric": "fabric",
    "fit": "fit",
    "inner lining": "inner lining",
    "length": "length",
    "neck": "neckline",
    "number of contents in sales package": "pack size",
    "pattern": "pattern",
    "seam type": "seam type",
    "sleeve": "sleeve type",
    "straps": "strap type",
    "type": "type",
    "weave type": "weave type",
    "wire support": "wire support",
}

# Lower case attribute name -> questions phrased specifically for the attribute:
# (question, answer)
ATTRIBUTE_SPECIFIC_QA_TEMPLATES: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "fabric": (
        (
            "What material is {name} made of?",
            "{name} is made of {value}.",
        ),
    ),
    "ideal for": (
        (
            "Who is {name} ideal for?",
            "{name} is ideal for {value} wear.",
        ),
        (
            "Who is {name} designed for?",
            "{name} is designed as {value} wear.",
        ),
    ),
    "occasion": (
        (
            "What occasion is {name} suitable for?",
            "{name} is suitable for these occasions: {value}.",
        ),
        (
            "When can I wear {name}?",
            "You can wear {name} on these occasions: {value}.",
        ),
    ),
    "pattern": (
        (
            "What pattern does {name} have?",
            "The pattern of {name} is {value}.",
        ),
    ),
}


def stable_hash(*parts: Any) -> int:
    """Returns a hash that is stable across processes, machines and Python versions.

    The built-in hash() is salted per process, so it can't be used to make the
    same decision on different Ray workers.

    Args:
        *parts: Values to hash, converted to strings.

    Returns:
        Unsigned 64 bit integer hash of the parts.
    """
    data = _HASH_SEPARATOR.join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


def clean_text(value: Any) -> str:
    """Converts a catalog value to a single line string.

    Args:
        value: Raw value, None and NaN are treated as missing.

    Returns:
        The value with surrounding and repeated whitespace removed, or an empty
        string if the value is missing.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return " ".join(str(value).split())


def parse_specifications(specifications: Any) -> Dict[str, str]:
    """Parses product specifications into attribute name and value pairs.

    Args:
        specifications: JSON object string as written by the data processing
            step (e.g. '{"Fabric": "Cotton"}') or an already parsed dictionary.

    Returns:
        Dictionary of attribute names and values in catalog order. Attributes
        with a missing name or value are skipped, and an empty dictionary is
        returned when the specifications are missing or can't be parsed.
    """
    if isinstance(specifications, dict):
        raw_attributes = specifications
    else:
        text = clean_text(specifications)
        if not text:
            return {}
        try:
            raw_attributes = json.loads(text)
        except (TypeError, ValueError):
            logger.debug("Unable to parse specifications: %s", text)
            return {}
        if not isinstance(raw_attributes, dict):
            return {}

    attributes = {}
    for raw_key, raw_value in raw_attributes.items():
        key = clean_text(raw_key)
        value = "" if isinstance(raw_value, (dict, list)) else clean_text(raw_value)
        if key and value:
            attributes[key] = value
    return attributes


def format_answer(template: str, **values: Any) -> str:
    """Formats the sentence of an answer from a template.

    Args:
        template: Answer template that ends with a period.
        **values: Values of the placeholders of the template.

    Returns:
        The sentence, with a single period at the end when the last value
        already ends with a period.
    """
    sentence = template.format(**values)
    if sentence.endswith(".."):
        sentence = sentence[:-1]
    return sentence


def format_product_details(name: str, category: str, attributes: Dict[str, str]) -> str:
    """Formats the product details block that is appended to every answer.

    Args:
        name: Product name.
        category: Product category.
        attributes: Attribute names and values.

    Returns:
        Product details with one item per line, each line ends with a newline.
    """
    details = f"Product Name: {name}\nProduct Category: {category}\nProduct Details:\n"
    for key, value in attributes.items():
        details += f"- {key}: {value}\n"
    return details


def generate_context(category: str) -> str:
    """Returns the conversation context for a product category."""
    return f"Online shopping for {category}"


def generate_prompt(context: str, question: str, answer: str) -> str:
    """Formats a question and answer as a Gemma instruction tuned model prompt.

    Args:
        context: Context of the conversation.
        question: Question from the user.
        answer: Answer from the model.

    Returns:
        Prompt using the Gemma chat template turns.
    """
    return (
        f"<start_of_turn>user\nContext:{context}\n{question}<end_of_turn>"
        f"<start_of_turn>model\n{answer}<end_of_turn>"
    )


class QAGenerator:
    """Generates question and answer pairs for products from templates."""

    def __init__(
        self,
        num_questions: int = 6,
        seed: int = 42,
        train_ratio: float = 0.8,
        validation_ratio: float = 0.1,
    ):
        """Initializes the generator.

        Args:
            num_questions: Number of question and answer pairs per product. A
                product has fewer pairs when there aren't that many questions
                to ask about it.
            seed: Seed for the template selection and the split assignment.
            train_ratio: Fraction of the pairs assigned to the training split.
                Every product has at least one pair in the training split,
                regardless of the fraction.
            validation_ratio: Fraction of the pairs assigned to the validation
                split, the remaining pairs are assigned to the test split.
        """
        if num_questions < 1:
            raise ValueError("num_questions must be at least 1")
        if not 0 < train_ratio < 1:
            raise ValueError("train_ratio must be between 0 and 1")
        if not 0 <= validation_ratio < 1 or train_ratio + validation_ratio > 1:
            raise ValueError(
                "validation_ratio must be between 0 and 1, and train_ratio + "
                "validation_ratio can't be greater than 1"
            )

        self.num_questions = num_questions
        self.seed = seed
        self.train_ratio = train_ratio
        self.validation_ratio = validation_ratio

    def assign_split(self, question: str, answer: str) -> str:
        """Assigns a question and answer pair to a dataset split.

        The assignment only depends on the seed and the content of the pair, so
        it is the same regardless of where and in which order pairs are
        generated.

        Args:
            question: Question of the pair.
            answer: Answer of the pair.

        Returns:
            Name of the split: 'training', 'validation' or 'test'.
        """
        buckets = 10000
        bucket = stable_hash(self.seed, "split", question, answer) % buckets
        if bucket < round(self.train_ratio * buckets):
            return SPLIT_TRAINING
        if bucket < round((self.train_ratio + self.validation_ratio) * buckets):
            return SPLIT_VALIDATION
        return SPLIT_TEST

    def _select_template(
        self, templates: Sequence[Tuple[str, str]], *key: Any
    ) -> Tuple[str, str]:
        """Selects one of the templates based on a stable hash of the key."""
        return templates[stable_hash(self.seed, "template", *key) % len(templates)]

    def _product_candidates(
        self, product_key: str, name: str, category: str
    ) -> List[Tuple[str, str]]:
        """Returns the questions about the product as a whole, in selection order."""
        candidates = [
            (
                question.format(name=name, category=category),
                format_answer(answer, name=name, category=category),
            )
            for question, answer in PRODUCT_QA_TEMPLATES
        ]
        return self._rank(candidates, product_key, "product")

    def _attribute_candidates(
        self, product_key: str, name: str, attributes: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        """Returns one question per supported attribute, in selection order."""
        candidates = []
        topics = set()
        for key, value in attributes.items():
            if (
                len(value) > MAX_ATTRIBUTE_VALUE_LENGTH
                or value.lower() in UNINFORMATIVE_ATTRIBUTE_VALUES
            ):
                continue

            attribute = key.lower()
            label = ATTRIBUTE_LABELS.get(attribute)
            # Different attributes can share a label, e.g. 'Color' and 'Brand Color'.
            # Only the first one is used, so that there is one answer per topic.
            topic = label or attribute
            if topic in topics:
                continue

            templates = list(ATTRIBUTE_SPECIFIC_QA_TEMPLATES.get(attribute, ()))
            if label:
                templates.extend(ATTRIBUTE_QA_TEMPLATES)
            if not templates:
                continue

            topics.add(topic)
            question, answer = self._select_template(templates, product_key, topic)
            candidates.append(
                (
                    question.format(name=name, label=label, value=value),
                    format_answer(answer, name=name, label=label, value=value),
                )
            )
        return self._rank(candidates, product_key, "attribute")

    def _rank(
        self, candidates: List[Tuple[str, str]], product_key: str, kind: str
    ) -> List[Tuple[str, str]]:
        """Orders the candidates pseudo randomly, but reproducibly."""
        return sorted(
            candidates,
            key=lambda candidate: stable_hash(
                self.seed, "rank", kind, product_key, candidate[0]
            ),
        )

    def generate_for_product(
        self,
        name: Any,
        category: Any,
        specifications: Any = None,
    ) -> List[Dict[str, str]]:
        """Generates the question and answer pairs for a product.

        One question is about the product as a whole, the remaining questions
        are about its attributes. Questions about the product as a whole are
        used instead when the product doesn't have enough attributes.

        At least one pair of the product is assigned to the training split. The
        model can only answer the questions of the validation and test splits
        about products that it was trained on.

        Args:
            name: Product name.
            category: Product category, used as the context of the conversation.
            specifications: Product specifications, see parse_specifications().

        Returns:
            List of rows with the QA_COLUMNS, empty if the product doesn't have
            a name or a category.
        """
        name = clean_text(name)
        category = clean_text(category)
        if not name or not category:
            return []

        attributes = parse_specifications(specifications)
        details = format_product_details(name, category, attributes)

        # Identical products generate identical pairs, so they can be deduplicated
        product_key = _HASH_SEPARATOR.join(
            [name, category, json.dumps(attributes, sort_keys=True)]
        )
        product_candidates = self._product_candidates(product_key, name, category)
        attribute_candidates = self._attribute_candidates(product_key, name, attributes)

        attribute_quota = self.num_questions - 1
        selected = (
            product_candidates[:1]
            + attribute_candidates[:attribute_quota]
            + product_candidates[1:]
            + attribute_candidates[attribute_quota:]
        )[: self.num_questions]

        context = generate_context(category)
        rows = []
        for question, answer_text in selected:
            answer = f"{answer_text} \n{details}"
            rows.append(
                {
                    "Question": question,
                    "Answer": answer,
                    "Context": context,
                    "prompt": generate_prompt(context, question, answer),
                    SPLIT_COLUMN: self.assign_split(question, answer),
                }
            )
        if rows and all(row[SPLIT_COLUMN] != SPLIT_TRAINING for row in rows):
            rows[0][SPLIT_COLUMN] = SPLIT_TRAINING
        return rows

    def generate(self, products: Iterable[Mapping[str, Any]]) -> List[Dict[str, str]]:
        """Generates the question and answer pairs for products.

        Args:
            products: Products with the 'Name' and 'Category' keys, and
                optionally the 'Specifications' key.

        Returns:
            List of rows with the QA_COLUMNS, one row per question and answer pair.
        """
        rows = []
        for product in products:
            rows.extend(
                self.generate_for_product(
                    product.get(PRODUCT_NAME_COLUMN),
                    product.get(PRODUCT_CATEGORY_COLUMN),
                    product.get(PRODUCT_SPECIFICATIONS_COLUMN),
                )
            )
        return rows


def finalize_qa_pairs(
    rows: Iterable[Mapping[str, str]], seed: int = 42
) -> List[Mapping[str, str]]:
    """Removes duplicate pairs and puts the pairs in a reproducible order.

    Products that are listed more than once in the catalog generate identical
    question and answer pairs, only one of each is kept. The pairs are then
    ordered pseudo randomly, independent of the order they were generated in.

    Args:
        rows: Rows with the QA_COLUMNS.
        seed: Seed for the order of the pairs.

    Returns:
        The unique rows, ordered.
    """
    unique_rows = {}
    for row in rows:
        unique_rows.setdefault((row["Question"], row["Answer"]), row)
    return [
        unique_rows[key]
        for key in sorted(
            unique_rows, key=lambda key: (stable_hash(seed, "order", *key), key)
        )
    ]


def split_qa_pairs(
    rows: Iterable[Mapping[str, str]],
) -> Dict[str, Dict[str, List[str]]]:
    """Splits the question and answer pairs into the dataset splits.

    Args:
        rows: Rows with the QA_COLUMNS.

    Returns:
        Dictionary of split name to the DATASET_COLUMNS of the split, each
        column is a list of values.
    """
    splits: Dict[str, Dict[str, List[str]]] = {
        split: {column: [] for column in DATASET_COLUMNS} for split in SPLITS
    }
    for row in rows:
        columns = splits[row[SPLIT_COLUMN]]
        for column in DATASET_COLUMNS:
            columns[column].append(row[column])
    return splits
