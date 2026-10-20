"""Compatibility checks for metadata consumed by FPP before loading the page."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_fpp_settings_loader_receives_both_maps(self):
        data = json.loads((ROOT / 'settings.json').read_text())
        # FPP LoadPluginSettingInfos indexes and array_merges both maps.
        # Missing either map aborts plugin.php before it reaches content.php.
        self.assertIsInstance(data['settings'], dict)
        self.assertIsInstance(data['settingGroups'], dict)
        self.assertEqual(data['settings']['ConnectorToken']['type'], 'password')
        self.assertEqual(data['settings']['ConnectorToken']['default'], '')

    def test_repository_metadata_matches_install_directory(self):
        data = json.loads((ROOT / 'pluginInfo.json').read_text())
        self.assertEqual(data['repoName'], 'fpp-ledshows')
        self.assertEqual(data['srcURL'], 'https://github.com/Kingshome0317/fpp-ledshows.git')
