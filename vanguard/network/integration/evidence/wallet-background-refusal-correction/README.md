Read audit.md and qualification.json. This is the one correction pass under
lead7c011923, deadline19:39:53UTC. Source PTY fixtures only; accepted4ba03433 is the
known-bad prompt control. Run the existing guarded-source-tests.py full suite on
Python3.15.2 and test_direct_profile.py on Python3.12.3, then freezer --check.
All native effects in source tests are substituted; the separate consumed native
attempt remains failed with9/16 functional PASS. No new grant or retry is implied.
