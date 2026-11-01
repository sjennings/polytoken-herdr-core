from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from probe_profile import prepare_profile


class ProfileTests(unittest.TestCase):
    def test_new_profile_is_reusable_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as root:
            path = prepare_profile(Path(root) / 'profile')
            (path / 'user-choice').write_text('retained')
            self.assertEqual(prepare_profile(path), path)
            self.assertEqual((path / 'user-choice').read_text(), 'retained')

    def test_existing_unmarked_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                prepare_profile(root)

    def test_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            target = prepare_profile(Path(root) / 'profile')
            link = Path(root) / 'link'
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                prepare_profile(link)
