
import unittest
import os

class TestUITextUpdates(unittest.TestCase):
    def test_layout_nav_text(self):
        """Verify templates/layout.html contains 'My Mentor'"""
        filepath = 'templates/layout.html'
        with open(filepath, 'r') as f:
            content = f.read()
            self.assertIn('<span>My Mentor</span>', content, "Nav link text not updated to 'My Mentor'")
            self.assertNotIn('<span>Mentor</span>', content, "Old nav link text 'Mentor' still present")

    def test_mentor_chat_intros(self):
        """Verify static/js/mentor_chat.js contains new intro texts"""
        filepath = 'static/js/mentor_chat.js'
        with open(filepath, 'r') as f:
            content = f.read()

            # Check Olyvia
            self.assertIn('Olivia is a seasoned financial advisor', content)
            self.assertIn('fiercely protecting capital', content)

            # Check Joel
            self.assertIn('Joel is an aggressive arbitrage mentor', content)
            self.assertIn('maximum profit momentum', content)

            # Check Evelyn
            self.assertIn('Evelyn is a seasoned arbitrage mentor', content)
            self.assertIn('long-term seller competence', content)

            # Check Errol
            self.assertIn('Errol is a quantitative arbitrage mentor', content)
            self.assertIn('high-confidence recommendations', content)

            # Verify old text is gone (sample)
            self.assertNotIn('Greetings Tim, Olivia here', content)

if __name__ == '__main__':
    unittest.main()
