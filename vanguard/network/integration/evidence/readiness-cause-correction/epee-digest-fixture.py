"""Digest fixture entry; per-session successor replaces the global-nonce control."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path.cwd()/'vanguard/network'))
from test_direct_profile import Direct
names=[name for name in unittest.defaultTestLoader.getTestCaseNames(Direct) if name.startswith('test_rpc_session_')]
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Direct(name) for name in names))
raise SystemExit(not result.wasSuccessful())
