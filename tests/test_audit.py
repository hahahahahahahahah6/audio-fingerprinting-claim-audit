import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from audio_fingerprinting_claim_audit.audit import audit, evidence, phrases_in
from audio_fingerprinting_claim_audit import phrases

EXPECTED_FINGERPRINT = ('audio fingerprinting', 'fingerprints audio', 'fingerprint audio', 'audio fingerprint identification', 'identifies audio by fingerprint', 'identifies songs', 'identifies song', 'recognizes songs', 'recognises songs', 'song identification', 'song recognition', 'music identification', 'identifies music', 'recognizes music', 'recognises music', 'music recognition', 'audio fingerprint matching', 'matches audio fingerprints', 'fingerprint based audio identification', 'fingerprint based song identification', 'acoustic fingerprinting', 'fingerprints songs', 'fingerprints music', 'audio fingerprint generation', 'generates audio fingerprints', 'creates audio fingerprints', 'song fingerprinting', 'music fingerprinting', 'audio fingerprint lookup', 'looks up audio fingerprints', 'identifies audio tracks', 'audio track identification', 'identifies audio recordings', 'audio recording identification', 'identify songs', 'identify music', 'recognize songs', 'recognise songs', 'audio fingerprint detector', 'supports audio fingerprinting', 'audio fingerprinting support', 'real time audio fingerprinting', 'live song identification')
EXPECTED_NOFINGERPRINT = ('no audio fingerprinting', 'does not fingerprint audio', 'without audio fingerprinting', 'no song identification', 'does not identify songs', 'without song identification', 'no music identification', 'does not identify music', 'audio fingerprinting not supported', 'does not support audio fingerprinting', 'cannot identify songs', 'never identifies songs', 'no acoustic fingerprinting', 'does not fingerprint songs', 'no song recognition', 'does not recognize songs', 'no music recognition', 'does not recognize music', 'no audio fingerprint identification', 'does not identify audio by fingerprint', 'without audio fingerprint identification', 'no fingerprint based audio identification', 'does not match audio fingerprints', 'without song recognition')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'audio_fingerprinting_claim_audit', str(self.root), *args], capture_output=True, text=True)

    def test_phrase_oracle(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        parsed = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)}
        self.assertEqual(parsed['FINGERPRINT'], EXPECTED_FINGERPRINT)
        self.assertEqual(parsed['NOFINGERPRINT'], EXPECTED_NOFINGERPRINT)
        self.assertEqual(len(parsed['FINGERPRINT']), 43)
        self.assertEqual(len(parsed['NOFINGERPRINT']), 24)
        for phrase in EXPECTED_FINGERPRINT:
            self.assertEqual(phrases_in(phrase), {'FINGERPRINT'})
        for phrase in EXPECTED_NOFINGERPRINT:
            self.assertEqual(phrases_in(phrase), {'NOFINGERPRINT'})

    def test_good(self):
        self.put('README.md', 'audio fingerprinting')
        self.put('app.py', 'model.fingerprint_audio(audio)')
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_bad_exact(self):
        self.put('README.md', 'audio fingerprinting')
        result = self.cli('--json')
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report['verdict'], 'FAIL')
        self.assertEqual(report['findings'][0]['id'], 'documented-audio-fingerprinting-claim-false')
        self.assertEqual(report['findings'][0]['severity'], 'HIGH')
        self.assertTrue(report['findings'][0]['message'])

    def test_test_only(self):
        self.put('README.md', 'audio fingerprinting')
        self.put('tests/helper.py', 'model.fingerprint_audio(audio)')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.cli('--fail-on', 'MEDIUM').returncode, 2)

    def test_denial(self):
        self.put('README.md', 'does not fingerprint audio')
        self.put('app.py', 'model.fingerprint_audio(audio)')
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(audit(self.root)['findings'][0]['id'], 'documented-no-audio-fingerprinting-claim-false')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_no_claim(self):
        self.put('README.md', 'An application.')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_no_source_asymmetry(self):
        self.put('README.md', 'audio fingerprinting')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')
        self.put('README.md', 'no audio fingerprinting')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_fences_inline_normalization(self):
        for marker in ('```', '~~~'):
            for spaces in range(4):
                self.assertEqual(phrases_in(' ' * spaces + marker + '\naudio fingerprinting\n' + ' ' * spaces + marker), set())
        self.assertEqual(phrases_in('`audio fingerprinting`'), {'FINGERPRINT'})
        self.assertEqual(phrases_in("doesn't fingerprint audio"), {'NOFINGERPRINT'})
        self.assertEqual(phrases_in('AUDIO-FINGERPRINTING'), {'FINGERPRINT'})
        self.assertEqual(phrases_in('audio\nfingerprinting'), {'FINGERPRINT'})
        self.assertEqual(phrases_in('audio\n\nfingerprinting'), set())
        self.assertEqual(phrases_in('xaudio fingerprintingx'), set())

    def test_docs_selection(self):
        self.put('nested/docs/a.md', 'audio fingerprinting')
        self.assertTrue(audit(self.root)['findings'])
        self.assertEqual(audit(self.root, ['nested'])['verdict'], 'PASS')
        self.put('nested/docs/a.md', 'neutral')
        self.put('nested/README.md', 'audio fingerprinting')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_exclusions(self):
        self.put('README.md', 'audio fingerprinting')
        for path in ('fixtures/a.py', 'docs/a.py', 'examples/a.py'):
            self.put(path, 'm.fingerprint_audio(a)')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')
        for path in ('test_one.py', 'one_test.py'):
            self.put(path, 'm.fingerprint_audio(a)')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')

    def test_symlinks(self):
        self.put('README.md', 'audio fingerprinting')
        with tempfile.TemporaryDirectory() as elsewhere:
            target = Path(elsewhere)
            (target / 'app.py').write_text('m.fingerprint_audio(a)')
            (self.root / 'link.py').symlink_to(target / 'app.py')
            (self.root / 'linked').symlink_to(target, target_is_directory=True)
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_split_pairs(self):
        self.put('README.md', 'audio fingerprinting')
        for constructor, use in [('Dejavu()', 'r.fingerprint_file(a)'), ('d.Dejavu()', 'r.fingerprint_directory(a)')]:
            self.put('one.py', 'r = ' + constructor)
            self.put('two.py', use)
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_usage_version(self):
        self.assertEqual(self.cli('--version').stdout.strip(), '0.1.0')
        self.assertEqual(self.cli('--unknown').returncode, 1)
        self.assertEqual(self.cli('--fail-on', 'invalid').returncode, 1)
        result = subprocess.run([sys.executable, '-m', 'audio_fingerprinting_claim_audit'], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(subprocess.run([sys.executable, '-m', 'audio_fingerprinting_claim_audit', str(self.root / 'missing')], capture_output=True).returncode, 1)

    def test_console_entry_definition(self):
        from importlib.metadata import distribution
        try:
            entries = distribution('audio-fingerprinting-claim-audit').entry_points
        except Exception:
            project = Path(__file__).resolve().parents[1] / 'pyproject.toml'
            self.assertIn('audio-fingerprinting-claim-audit = "audio_fingerprinting_claim_audit.audit:main"', project.read_text())
        else:
            self.assertTrue(any(e.name == 'audio-fingerprinting-claim-audit' and e.value == 'audio_fingerprinting_claim_audit.audit:main' for e in entries))



def route_test(source, expected):
    def test(self):
        self.assertEqual(evidence(source), expected, source)
    return test

# Each route and exclusion is a separate test for useful failure reporting.
POSITIVES = [
    'import acoustid\nacoustid.fingerprint_file(a)',
    'import acoustid as ac\nac.fingerprint_file(a)',
    'from acoustid import fingerprint_file\nfingerprint_file(a)',
    'from acoustid import fingerprint_file as fp\nfp(a)',
    'd=Dejavu()\nd.fingerprint_file(a)',
    'd=lib.Dejavu()\nd.fingerprint_directory(a)',
    'from dejavu import Dejavu as D\nd: object=D()\nd.fingerprint_file(a)',
    'import dejavu as j\nd=j.Dejavu()\nd.fingerprint_directory(a)',
    'import acoustid\ndef fingerprint_file(a): pass\nacoustid.fingerprint_file(a)',
    'from acoustid import fingerprint_file as f\ndef f(a): pass\nf(a)',
    'def Dejavu(): pass\nd=Dejavu()\nd.fingerprint_file(a)',
]
NEGATIVES = [
    'import acoustid', 'import dejavu', 'import chromaprint', 'import audfprint',
    'import essentia', 'librosa.load(a)', 'soundfile.read(a)', 'wave.open(a).readframes(4)',
    'torchaudio.load(a)', 'r.listen(a)', 'r.record(a)', 'sounddevice.rec(a)',
    'pyaudio.open().read(a)', 'obj.play(a)', 'obj.transcribe(a)', 'obj.recognize_google(a)',
    'obj.stt(a)', 'pyttsx3.say(a)', 'vad.is_speech(a)', 'silero.get_speech_timestamps(a)',
    'pyannote.load("segmentation")', 'pvporcupine.create()', 'openwakeword.Model().predict(a)',
    'obj.detect_keyword(a)', 'speechbrain.verify_files(a,b)', 'resemblyzer.compare(a,b)',
    'obj.verify_speaker(a)', 'pipeline("diarization")', 'obj.diarize(a)',
    'noisereduce.reduce_noise(a)', 'df.enhance.enhance(a)', 'obj.suppress_noise(a)',
    'obj.remove_noise(a)', 'demucs.separate(a)', 'spleeter.separate(a)',
    'obj.separate_stems(a)', 'obj.split_stems(a)', 'obj.isolate_vocals(a)',
    'r=AudioTagging()\nr.inference(a)', 'r=YAMNet()\nr(a)', 'obj.detect_sound_event(a)',
    'classifier.predict(a)', 'pipeline("audio-classification",model="music-genre")',
    'librosa.feature.chroma_stft(a)', 'librosa.feature.mfcc(a)',
    'librosa.feature.spectral_centroid(a)', 'hashlib.md5(open(a,"rb").read())',
    'hashlib.sha256(data)', 'import acoustid\nacoustid.lookup(key,fp)',
    'import acoustid\nacoustid.match(a)', 'd=Dejavu()', 'd.fingerprint_file(a)',
    'd.fingerprint_directory(a)', 'd=Other()\nd.fingerprint_file(a)',
    'subprocess.run(["fpcalc", "a.wav"])', 'subprocess.run(["audfprint", "a.wav"])',
    's="acoustid Dejavu fingerprint_audio"', 'obj.fingerprint_audio', 'bad syntax !!!',
    'import other as acoustid\nacoustid.fingerprint_file(a)',
    'from other import fingerprint_file\nfingerprint_file(a)',
    'import acoustid.submodule\nacoustid.fingerprint_file(a)',
]
for generic in ('fingerprint_audio', 'generate_audio_fingerprint', 'get_audio_fingerprint',
                'compute_audio_fingerprint', 'create_audio_fingerprint'):
    POSITIVES.extend(['obj.' + generic + '(a)',
                      'from helper import ' + generic + '\n' + generic + '(a)',
                      'from helper import ' + generic + ' as f\nf(a)',
                      'import ' + generic + ' as f\nf(a)'])
    NEGATIVES.extend([generic + '(a)',
                      'def ' + generic + '(a): pass\nobj.' + generic + '(a)',
                      'class C:\n def ' + generic + '(self,a): pass\nobj.' + generic + '(a)',
                      'from helper import ' + generic + ' as f\ndef f(a): pass\nf(a)',
                      'from helper import ' + generic + ' as f\ndef ' + generic + '(a): pass\nf(a)'])
for index, source in enumerate(POSITIVES):
    setattr(AuditTests, 'test_positive_%02d' % index, route_test(source, True))
for index, source in enumerate(NEGATIVES):
    setattr(AuditTests, 'test_negative_%02d' % index, route_test(source, False))


def self_audit(self):
    from importlib.metadata import metadata, PackageNotFoundError
    try:
        readme = metadata('audio-fingerprinting-claim-audit').get_payload()
    except PackageNotFoundError:
        readme = (Path(__file__).resolve().parents[1] / 'README.md').read_text()
    self.assertEqual(phrases_in(readme), set())
    self.put('README.md', readme)
    self.assertEqual(audit(self.root)['verdict'], 'PASS')


def split_import(self):
    self.put('README.md', 'audio fingerprinting')
    self.put('one.py', 'import acoustid\nfrom helper import fingerprint_audio as f')
    self.put('two.py', 'acoustid.fingerprint_file(a)\nf(a)')
    self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')


def ignore_verbose(self):
    self.put('README.md', 'audio fingerprinting')
    self.put('src/app.py', 'obj.fingerprint_audio(a)')
    self.assertEqual(self.cli('--verbose').returncode, 0)
    self.assertIn('src/app.py', self.cli('--verbose').stdout)
    self.assertEqual(self.cli('--ignore', 'src', '--ignore', 'unused').returncode, 2)
    self.assertEqual(self.cli('--ignore', 'sr').returncode, 0)


def io_error(self):
    from unittest.mock import patch
    self.put('README.md', 'neutral')
    from audio_fingerprinting_claim_audit.audit import main
    with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
        self.assertEqual(main([str(self.root)]), 1)


setattr(AuditTests, 'test_self_audit', self_audit)
setattr(AuditTests, 'test_split_import', split_import)
setattr(AuditTests, 'test_ignore_verbose', ignore_verbose)
setattr(AuditTests, 'test_io_error', io_error)

if __name__ == '__main__':
    unittest.main()
