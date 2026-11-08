Read audit.md and qualification.json first. This is the lead-authorized bounded
wallet config/prompt correction from b17746e6. Reproduce from the task branch:

    python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py
    /usr/bin/python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py test_direct_profile.py
    python3 -B vanguard/network/freeze-profile.py --check

Final qualification logs are full-source-qualified.log and direct-python312-qualified.log.
Intermediate failures are retained with their cause in qualification.json.
Fixtures use disposable Python CLI/PTY and HTTP servers with native effects
substituted. They do not establish native wallet behavior. Platform first;
Security only upon a changed-surface finding. No runtime authority is included.
Historical native ATTEMPTED_FAIL,9/16 PASS; full matrix/acceptance/integration open.
launch_ready=false;public_launch=false. Needs TJ: None.
