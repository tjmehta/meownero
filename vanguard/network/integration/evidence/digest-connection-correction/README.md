Digest connection correction; source review only.

Read audit.md, lead-decision.json and qualification.json first. Full-source.log records363 passing checks on Python3.15.2; python312-direct.log records84 passing direct checks on Python3.12.3. Both exercise the exact known-bad ed78cd5 and current client on the same session-nonce fixture. No native process, Docker, admission or original-lock action ran. All16 functional native rowsNOT_RUN; historical nativeATTEMPTED_FAIL. launch_ready=false;public_launch=false.

Reproduce from this branch:

    python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py
    /usr/bin/python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py test_direct_profile.py
    python3 -B vanguard/network/freeze-profile.py --check

Platform first, then Security; a separate new exact900s reuse grant is required after both accept. All earlier grants are permanently consumed. P2P retains ownership; preserve Core decision47234b59/count2 and later Security. Needs TJ: None.
