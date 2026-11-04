# Frozen runtime producer/consumer audit

Authority: answered lead interaction `81de4466-14e3-4d2a-bfa3-d8eaebcc50dd`; baseline `bf6acfba8cf0d649ec5c29480387bdd5327f8837`. Paths below are relative to `vanguard/network/` unless marked upstream. The frozen driver, freezer and build script are byte-identical to the baseline. This is static source evidence, not execution of RPC/daemon/wallet behavior.

Every row obtains string `status="PASS"` from `profile-integration.py:49`; `run-profile.py:494` accepts only PASS/FAIL/NOT_RUN. Unreached rows originate from `profile_contract.py:REQUIRED`/`empty_rows()`. The recursive consumer at `run-profile.py:439` checks dictionary types, exact known key sets for PASS, every required field, and exact literal Python types (`bool` cannot stand for `int`). FAIL/NOT_RUN permit only valid subsets. Unknown keys export the fixed `<unknown>` token, never the producer's key.

| Row and every emitted witness field | Frozen producer file:line | Consumer file:line; type, shape, literal | Mismatch |
| --- | --- | --- | --- |
| peer/native_handshake: request_sha256, command | profile-integration.py:456; profile_contract.py:52 | run-profile.py:467,457; lowercase 64-hex string SHA256; integer 1001 | None |
| peer/genesis_state: height, top_block_hash, work, pool_hashes | profile-integration.py:457,153–161 | run-profile.py:458–459,467; integer 1; exact lowercase c.GENESIS string; string optional 0x plus 1–32 hex digits; empty list length 0 | None; upstream emits lowercase 0x-prefixed hex, accepted |
| peer/daemon_fork_table: v18_height, offline_wallet | profile-integration.py:464 | run-profile.py:468; integer 1, string NOT_RUN | None |
| wallet/persisted_height_zero: wallets | profile-integration.py:489; profile_contract.py:REQUIRED wallet keys | run-profile.py:469; integer 2 | None |
| wallet/address_roundtrip: wallets | profile-integration.py:489 | run-profile.py:469; integer 2 | None |
| wallet/foreign_prefix_refusal: wallets | profile-integration.py:489 | run-profile.py:470; integer 2 | None |
| auth/http_auth: daemons, loopback_socket_census | profile-integration.py:466 | run-profile.py:470; integer 2, boolean true | None |
| auth/seventeen_denials: wallets, per_wallet, code | profile-integration.py:490 | run-profile.py:471; integers 2,17,-7 | None |
| auth/rotated_login: wallets, old_credentials_rejected | profile-integration.py:491 | run-profile.py:472; integer 2, boolean true | None |
| isolation/uuid_guard: guard, fixture_sha256, healthy_before_after, unchanged_state | profile-integration.py:322–323; state from153–161 | run-profile.py:473–474; exact string net_node.inl:handle_handshake/network_id; lowercase 64-hex SHA256; boolean true; full state fields as above | None |
| isolation/chain_genesis_guard: guard, fixture_sha256, healthy_before_after, unchanged_state, response_command | profile-integration.py:331–332; chain_control:301–309 | run-profile.py:475–476; exact string Blockchain::find_blockchain_supplement/genesis; lowercase 64-hex SHA256; boolean true; full state fields as above; integer 2007 | None |
| isolation/launcher_refusals: controls, kind, original_unchanged | profile-integration.py:206 | run-profile.py:477; integer 8; exact string launcher-manifest-only; boolean true | None |
| isolation/no_fallback: bounded_seconds, loopback_socket_samples, exclusive_endpoint_absent, unchanged_state, scope | profile-integration.py:473–474; state153–161 | run-profile.py:478–479; integers 2,20; boolean true; full state fields as above; exact string bounded-no-external-connection | None |
| reopen/wallet_save_exit_release: wallets, forced_kill | profile-integration.py:492 | run-profile.py:480; integer 2, boolean false | None |
| reopen/wallet_cold_restore: wallets, height | profile-integration.py:493 | run-profile.py:481; integers 2,0 | None |
| reopen/daemon_reopen_restore: genesis_only, counterpart_stopped | profile-integration.py:485 | run-profile.py:482; booleans true,true | None |

Nested state expansion applies independently to peer/genesis_state, isolation/uuid_guard.unchanged_state, isolation/chain_genesis_guard.unchanged_state and isolation/no_fallback.unchanged_state: height is native JSON integer 1; top_block_hash is exact c.GENESIS; work is native wide_cumulative_difficulty string; pool_hashes is constructed empty list, never copied arbitrary pool contents. `snapshot()` requires the same height/hash and zero pool before returning. Upstream pinned `src/rpc/core_rpc_server_commands_defs.h:785,803,805` declares height uint64_t and hash/work strings; `src/rpc/core_rpc_server.cpp:98,309,329` assigns the hash and wide-difficulty conversion. `src/cryptonote_basic/difficulty.cpp:244–257` emits lowercase chars0123456789abcdef and returns "0x" plus at least one digit. A uint128 value uses at most32 digits. No decimal/int conversion seam exists here. `profile_contract.py:53` uses hashlib.hexdigest(), producing lowercase64 hex digits.

All runtime literals, int/string/boolean distinctions, hash case/prefixes and list lengths match. No controller-side runtime correction or driver change is needed. This table lists every discovered mismatch: none in runtime. The separate build mismatch is the literal loader SONAME rejected by the baseline lib-only predicate; the correction adds only `ld-linux-x86-64.so.2`, retaining the existing grammar and32-entry cap.

The complete actual frozen row-expression fixture and recursive missing-field tests exercise these consumers, with native RPC/sockets/processes substituted. They supplement this audit; they do not replace future native verification.
