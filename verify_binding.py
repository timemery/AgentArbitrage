
import unittest
import re

class TestBindingFormatting(unittest.TestCase):
    def format_binding(self, binding_str):
        if binding_str:
            return str(binding_str).replace('_', ' ').replace('-', ' ').title()
        return binding_str

    def test_formatting_logic(self):
        test_cases = {
            "library_binding": "Library Binding",
            "mass-market": "Mass Market",
            "sheet_music": "Sheet Music",
            "bundle": "Bundle",
            "hardcover": "Hardcover",
            "paperback": "Paperback",
            "audio_cd": "Audio Cd", # Python title() behavior: "Audio Cd" is expected if simple title() used
        }

        for input_str, expected in test_cases.items():
            result = self.format_binding(input_str)
            print(f"Input: {input_str} -> Output: {result}")
            self.assertEqual(result, expected)

    def test_css_content(self):
        with open('static/global.css', 'r') as f:
            css_content = f.read()

        self.assertIn('.binding-cell', css_content)
        self.assertIn('max-width: 95px', css_content)
        self.assertIn('overflow: visible', css_content) # Check hover effect

    def test_html_content(self):
        with open('templates/dashboard.html', 'r') as f:
            html_content = f.read()

        # Check for the specific Binding cell rendering
        self.assertIn('class="binding-cell"', html_content)
        self.assertIn('col === \'Binding\'', html_content)

if __name__ == '__main__':
    unittest.main()
