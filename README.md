# Documentation claim auditor

An offline static checker that compares documentation promises with supported
Python call patterns. Version 0.1.0 requires Python 3.9 or later and has no runtime
dependencies. Source is parsed with AST and never executed.

```sh
pip install .
audio-fingerprinting-claim-audit /path/to/project
python3 -m audio_fingerprinting_claim_audit /path/to/project --json
python3 -m unittest discover
```

The checker reads root README.md and Markdown files beneath any docs path
component. Fenced blocks are skipped; inline code counts. Paragraph text is
lowercased, contractions expanded, hyphens replaced with spaces, and whitespace
collapsed. Exact phrases use word boundaries, with denials removed first.

Evidence is confined to one source module. Supported operations are:

```text
acoustid.fingerprint_file(...) (including module and from-import aliases)
d = Dejavu(...); d.fingerprint_file(...) or d.fingerprint_directory(...)
obj.fingerprint_audio(...)
obj.generate_audio_fingerprint(...)
obj.get_audio_fingerprint(...)
obj.compute_audio_fingerprint(...)
obj.create_audio_fingerprint(...)
```

The generic forms also accept from-import aliases and are suppressed by local
function or method definitions of the matching name. The first two routes have
no additional shadow restriction. Imports alone, unrelated audio processing,
byte hashes, external commands, strings and invalid source provide no evidence.
This is a syntactic check; it cannot establish runtime correctness or quality.

Symlinks are skipped. Source under fixtures, docs and examples is excluded.
Source under tests, or with a test filename, supplies only test evidence.

```text
documented-audio-fingerprinting-claim-false          HIGH (or MEDIUM for tests only)
documented-no-audio-fingerprinting-claim-false       HIGH
```

Each family produces at most one finding. JSON includes verdict, findings with
id, severity and message, production_evidence and test_evidence. Findings set the
verdict to FAIL even if they fall below the selected exit threshold.

Options: --json emits the report as JSON; --verbose lists evidence paths;
--ignore accepts a repeatable relative path prefix bounded by path components;
--fail-on selects LOW, MEDIUM or HIGH (default HIGH); --version prints 0.1.0.
Exit status is 0 when no finding reaches the threshold, 2 when one does, and 1
for usage or input errors. The checker performs no network access or file writes.

Licensed under MIT.
