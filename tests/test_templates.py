from __future__ import annotations

import unittest

from magent_tui.templates import instantiate_template, template_names


class TemplateTest(unittest.TestCase):
    def test_template_names_not_empty(self) -> None:
        self.assertIn("product_sprint", template_names())

    def test_instantiate_returns_deep_copy(self) -> None:
        agents_a = instantiate_template("product_sprint")
        agents_b = instantiate_template("product_sprint")
        agents_a[0].name = "Changed"
        self.assertNotEqual(agents_a[0].name, agents_b[0].name)

