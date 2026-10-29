
import unittest
from unittest.mock import patch
from io import StringIO
from src.main import main


class TestMain(unittest.TestCase):

    @patch("builtins.input", return_value="2")
    @patch("sys.stdout", new_callable=StringIO)
    def test_project_information(self, mock_stdout, mock_input):
        main()
        output = mock_stdout.getvalue()
        self.assertIn("Team ID: T077", output)
        self.assertIn("Problem Statement: PS-052", output)

    @patch("builtins.input", return_value="3")
    @patch("sys.stdout", new_callable=StringIO)
    def test_exit_option(self, mock_stdout, mock_input):
        main()
        self.assertIn("Goodbye!", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
