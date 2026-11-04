Read audit.md, platform-f1.json, lead-decision.json and qualification.json first. This packet corrects Platform F1 on be242236. It is source evidence only, with disposable HTTP servers and substituted native/Docker/admission effects.

Reproduce from the exact task branch:

    python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py
    /usr/bin/python3 -B -W error::ResourceWarning vanguard/network/integration/evidence/sampler-metrology-correction/guarded-source-tests.py test_direct_profile.py
    python3 -B vanguard/network/freeze-profile.py --check

Final logs: full-source-qualified.log and direct-python312-qualified.log. Earlier logs preserve fixture corrections; they are not the final qualification. Current tests compare real progressing headers/framing against exact known-bad be242236, and retain the original ed78cd5 per-connection nonce regression. All native functional rows remainNOT_RUN. Platform first, then Security; both must accept before a separate new exact900s reuse grant. All older grants consumed. launch_ready=false;public_launch=false. Needs TJ: None.
