"""Tests of scripts/collect.py. Run: python3 -I tests/test_collect.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import collect  # noqa: E402

MO = ['sw', 'sc', 'sd', 'svx', 'cui', 'sfx', 'vcl', 'svt']


def metadata(langs):
    files = []
    for lang in langs:
        files.append('/instdir/share/registry/Langpack-%s.xcd' % lang)
        files.append('/instdir/share/registry/res/registry_%s.xcd' % lang)
        files.append('/instdir/share/registry/res/fcfg_langpack_%s.xcd' % lang)
        if lang != 'en-US':
            files += ['/instdir/program/resource/%s/LC_MESSAGES/%s.mo' % (lang, m) for m in MO]
    return {'files': [{'filename': f, 'start': 0, 'end': 1} for f in files]}


class CollectTest(unittest.TestCase):
    def test_parse_env_strips_quotes_and_comments(self):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('# comment\nLANGS="fr de"\nBUILD_NUMBER=2\n\n')
        self.assertEqual(collect.parse_env(f.name), {'LANGS': 'fr de', 'BUILD_NUMBER': '2'})

    def test_all_languages_present(self):
        langs = ['en-US', 'fr', 'de', 'es', 'it']
        self.assertEqual(collect.missing_language_files(metadata(langs), langs), [])

    def test_missing_language_reported(self):
        missing = collect.missing_language_files(metadata(['en-US', 'fr']), ['en-US', 'fr', 'de'])
        self.assertIn('/instdir/share/registry/Langpack-de.xcd', missing)
        self.assertIn('/instdir/program/resource/de/LC_MESSAGES/sw.mo', missing)

    def test_brotli_size_smaller_than_raw_for_text(self):
        with tempfile.NamedTemporaryFile('wb', delete=False) as f:
            f.write(b'LibreOffice ' * 10000)
        self.assertLess(collect.brotli_size(f.name), 1000)


if __name__ == '__main__':
    unittest.main()
