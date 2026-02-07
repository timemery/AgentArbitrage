import unittest
import os

class TestDeploymentSafety(unittest.TestCase):
    def test_deploy_script_forces_pause(self):
        """
        Verifies that deploy_update.sh calls Diagnostics/force_pause.py.
        This is CRITICAL to prevent token starvation livelocks on low-tier plans.
        """
        script_path = "deploy_update.sh"
        if not os.path.exists(script_path):
            self.fail(f"{script_path} not found.")

        with open(script_path, 'r') as f:
            content = f.read()

        # Check for the specific call
        expected_call = "Diagnostics/force_pause.py"

        # We also check if it's commented out (simple check, not perfect bash parsing)
        # We look for the string being present and NOT preceded immediately by a '#'
        # (though typically it's on a new line)

        self.assertIn(expected_call, content, "deploy_update.sh MUST call Diagnostics/force_pause.py")

        # Ensure it's not commented out
        lines = content.splitlines()
        found_active_call = False
        for line in lines:
            if expected_call in line and not line.strip().startswith('#'):
                found_active_call = True
                break

        self.assertTrue(found_active_call, "The call to force_pause.py appears to be commented out in deploy_update.sh")

if __name__ == '__main__':
    unittest.main()
