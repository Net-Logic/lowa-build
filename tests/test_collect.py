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


XCU = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" oor:name="Linguistic" oor:package="org.openoffice.Office">
 <node oor:name="ServiceManager"><node oor:name="Dictionaries">%s</node></node></oor:component-data>
'''
NODE = '''<node oor:name="%s" oor:op="fuse">
 <prop oor:name="Locations" oor:type="oor:string-list"><value>%s</value></prop>
 <prop oor:name="Format" oor:type="xs:string"><value>%s</value></prop>
 <prop oor:name="Locales" oor:type="oor:string-list"><value>%s</value><!-- comment --></prop>
</node>'''
# Source tree of the dictionaries: folder -> (xcu nodes, files)
TREE = {
    'en': ([('HunSpellDic_en_US', '%origin%/en_US.aff %origin%/en_US.dic', 'DICT_SPELL', 'en-US en-IL en-PH'),
            ('HyphDic_en_US', '%origin%/hyph_en_US.dic', 'DICT_HYPH', 'en-US en-IL en-PH')],
           ['en_US.aff', 'en_US.dic', 'hyph_en_US.dic', 'README_en_US.txt', 'license.txt']),
    'fr_FR': ([('HunSpellDic_fr', '%origin%/fr.aff %origin%/fr.dic', 'DICT_SPELL', 'fr-FR fr-BE fr-CH'),
               ('HyphDic_fr', '%origin%/hyph_fr.dic', 'DICT_HYPH', 'fr-FR fr-BE fr-CH')],
              ['dictionaries/fr.aff', 'dictionaries/fr.dic', 'dictionaries/hyph_fr.dic', 'dictionaries/README_dict_fr.txt']),
    'de': ([('HunSpellDic_de_DE', '%origin%/de_DE_frami.aff %origin%/de_DE_frami.dic', 'DICT_SPELL', 'de-DE'),
            ('HyphDic_de_DE', '%origin%/hyph_de_DE.dic', 'DICT_HYPH', 'de de-DE')],
           ['de_DE_frami.aff', 'de_DE_frami.dic', 'hyph_de_DE.dic', 'COPYING_GPLv3', 'COPYING_LGPL_v2.1.txt', 'README_hyph_de.txt']),
    'es': ([('HunSpellDic_es_ES', '%origin%/es_ES.aff %origin%/es_ES.dic', 'DICT_SPELL', 'es-ES'),
            ('HyphDic_es', '%origin%/hyph_es.dic', 'DICT_HYPH', 'es-AR es-ES es-MX')],
           ['es_ES.aff', 'es_ES.dic', 'hyph_es.dic', 'LICENSE.md']),
    'it_IT': ([('HunSpellDic_it_IT', '%origin%/it_IT.aff %origin%/it_IT.dic', 'DICT_SPELL', 'it-IT it-CH'),
               ('HyphDic_it_IT', '%origin%/hyph_it_IT.dic', 'DICT_HYPH', 'it-IT it-CH')],
              ['it_IT.aff', 'it_IT.dic', 'hyph_it_IT.dic', 'README_it_IT.txt']),
}


def make_tree(root, skip=None):
    for folder, (nodes, files) in TREE.items():
        os.makedirs(os.path.join(root, folder, 'dictionaries'), exist_ok=True)
        with open(os.path.join(root, folder, 'dictionaries.xcu'), 'w') as f:
            f.write(XCU % ''.join(NODE % n for n in nodes))
        for name in files:
            if name != skip:
                with open(os.path.join(root, folder, name), 'w') as f:
                    f.write('%s %s\n' % (folder, name) * 50)


class DictsTest(unittest.TestCase):
    def test_xcu_locales_by_file_name(self):
        root = tempfile.mkdtemp()
        make_tree(root)
        xcu = os.path.join(root, 'fr_FR', 'dictionaries.xcu')
        self.assertEqual(collect.xcu_locales(xcu, 'fr.dic'), ['fr-FR', 'fr-BE', 'fr-CH'])
        self.assertEqual(collect.xcu_locales(xcu, 'hyph_fr.dic'), ['fr-FR', 'fr-BE', 'fr-CH'])
        self.assertEqual(collect.xcu_locales(xcu, 'thes_fr.dat'), [])

    def test_link_names(self):
        self.assertEqual(collect.link_names('hunspell/fr_FR.dic', 'fr-FR', ['fr-FR', 'fr-BE']), ['fr_BE.dic'])
        self.assertEqual(collect.link_names('hyphen/hyph_fr_FR.dic', 'fr-FR', ['fr-FR', 'fr-CH']), ['hyph_fr_CH.dic'])
        self.assertEqual(collect.link_names('hyphen/hyph_de_DE.dic', 'de-DE', ['de-DE', 'de']), ['hyph_de.dic'])
        self.assertEqual(collect.link_names('hunspell/de_DE.aff', 'de-DE', ['de-DE']), [])

    def test_link_names_replace_the_locale_suffix_only(self):
        # A name holding the main locale twice: only the locale before the extension is replaced
        self.assertEqual(collect.link_names('hyphen/hyph_fr_FR_fr_FR.dic', 'fr-FR', ['fr-FR', 'fr-BE']), ['hyph_fr_FR_fr_BE.dic'])

    def test_repeated_locale_gives_one_link(self):
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root)
        xcu = os.path.join(root, 'it_IT', 'dictionaries.xcu')
        with open(xcu) as f:
            text = f.read()
        with open(xcu, 'w') as f:
            f.write(text.replace('<value>it-IT it-CH</value>', '<value>it-IT it-CH it-CH it-IT</value>'))
        it = next(e for e in collect.collect_dicts(root, out) if e['name'] == 'hunspell/it_IT.dic')
        self.assertEqual(it['locales'], ['it-IT', 'it-CH'])
        self.assertEqual(it['links'], ['it_CH.dic'])

    def test_collect_dicts(self):
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root)
        entries = collect.collect_dicts(root, out)
        names = sorted(e['name'] for e in entries)
        self.assertEqual(len(names), 15)
        self.assertIn('hunspell/fr_FR.dic', names)
        self.assertIn('hunspell/de_DE.aff', names)
        self.assertIn('hyphen/hyph_es_ES.dic', names)
        for e in entries:
            path = os.path.join(out, 'dicts', e['name'])
            self.assertTrue(os.path.isfile(path), path)
            self.assertEqual(e['raw'], os.path.getsize(path))
            self.assertEqual(e['sha256'], collect.sha256_file(path))
        fr = next(e for e in entries if e['name'] == 'hunspell/fr_FR.dic')
        self.assertEqual(fr['source'], 'fr_FR/dictionaries/fr.dic')
        self.assertEqual(fr['links'], ['fr_BE.dic', 'fr_CH.dic'])
        es = next(e for e in entries if e['name'] == 'hyphen/hyph_es_ES.dic')
        self.assertEqual(es['links'], ['hyph_es_AR.dic', 'hyph_es_MX.dic'])
        for lang, name in [('en', 'license.txt'), ('fr', 'README_dict_fr.txt'), ('de', 'COPYING_GPLv3'), ('es', 'LICENSE.md'), ('it', 'README_it_IT.txt')]:
            self.assertTrue(os.path.isfile(os.path.join(out, 'licenses', 'dictionaries', lang, name)), lang + '/' + name)

    def test_lgpl_text_in_each_lgpl_language(self):
        # The French and Italian hyphenation patterns are LGPL: the text goes with them, not only with German
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root)
        collect.collect_dicts(root, out)
        for lang in ('de', 'fr', 'it'):
            with open(os.path.join(out, 'licenses', 'dictionaries', lang, 'COPYING_LGPL_v2.1.txt')) as f:
                self.assertEqual(f.read(), 'de COPYING_LGPL_v2.1.txt\n' * 50, lang)

    def test_main_locale_first_and_links(self):
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root)
        de = next(e for e in collect.collect_dicts(root, out) if e['name'] == 'hyphen/hyph_de_DE.dic')
        self.assertEqual(de['locales'], ['de-DE', 'de'])
        self.assertEqual(de['links'], ['hyph_de.dic'])

    def test_missing_source_fails(self):
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root, skip='it_IT.dic')
        with self.assertRaises(SystemExit):
            collect.collect_dicts(root, out)

    def test_xcu_without_main_locale_fails(self):
        root, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        make_tree(root)
        xcu = os.path.join(root, 'es', 'dictionaries.xcu')
        with open(xcu) as f:
            text = f.read()
        with open(xcu, 'w') as f:
            f.write(text.replace('<value>es-ES</value>', '<value>es-MX</value>'))
        with self.assertRaises(SystemExit):
            collect.collect_dicts(root, out)


if __name__ == '__main__':
    unittest.main()
