#!/usr/bin/env python3
"""Freeze/check source bytes; --built is used only by the future granted build."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import network as n
import policy
import profile_contract as c

UP=Path('<repo>/build/vanguard-src/monero-fcmp')
EXTRA=['src/p2p/p2p_protocol_defs.h','src/p2p/net_node.inl',
       'src/cryptonote_protocol/cryptonote_protocol_defs.h','src/cryptonote_protocol/cryptonote_protocol_handler.inl',
       'contrib/epee/include/storages/portable_storage_to_bin.h',
       'contrib/epee/include/storages/portable_storage_base.h',
       'contrib/epee/include/storages/portable_storage.h',
       'src/common/password.cpp','src/rpc/rpc_args.cpp','src/wallet/wallet_rpc_server.h',
       'src/rpc/CMakeLists.txt','src/p2p/net_node.cpp','tests/unit_tests/base58.cpp','tests/functional_tests/wallet.py']
CODE=['test_handoff.py','profile_handoff.py','profile_contract.py','run-profile.py','profile-integration.py',
      'freeze-profile.py','test_profile.py','profile_outer.py','run-outer.py','test_outer.py',
      'profile_manager.py','profile_helper.py','test_manager.py','profile_packet.py',
      'profile_dispatch.py','profile-helper.py','test_dispatch.py','profile_bootstrap.py','test_bootstrap.py',
      'profile_executor.py','profile-root-helper.py','profile_runtime.py','test_executor.py','test_installation.py','profile_ingress.py','test_ingress.py',
      'profile_constructor.py','test_constructor.py','test_supervisor.py','profile-custodian.py','test_lifecycle_source.py',
      'profile_receiver.py','test_receiver.py']


def candidate_paths():
    files=[c.HERE/name for name in CODE]
    files+=sorted(p for p in (c.HERE/'integration').iterdir() if p.name not in
                  ['inputs.json','evidence'] and p.is_file())
    files.append(c.HERE/'integration/installation-inventory.json')
    return sorted(set(files))


def installation_inventory():
    reference=c.json_file(c.HERE/'integration/reference-inputs.json')
    all_sources={str(p.relative_to(n.ROOT)) for p in candidate_paths()}|set(reference['repository_files'])
    prefix='vanguard/network/'
    root_sources=[prefix+name for name in ('profile-root-helper.py','profile_executor.py',
        'profile_contract.py','profile_packet.py','profile_ingress.py','profile_runtime.py',
        'profile_bootstrap.py','profile_dispatch.py','profile_manager.py','profile_outer.py',
        'profile_handoff.py','profile_helper.py','profile_constructor.py','profile_receiver.py','profile-custodian.py','integration/installation-inventory.json')]
    runtime={prefix+name for name in CODE if not name.startswith('test_')}
    runtime|={prefix+name for name in ('network.py','policy.py','run-genesis.py','profile.json',
        'source-bindings.json','policy-bindings.json','evidence/native-genesis-attempt01/recipe1.json',
        'integration/build.sh','integration/reviewed-contract.json','integration/outer-capabilities.json')}
    runtime.add('vanguard/source-lock.json')
    # The recipe was already transitively bound by profile.json, but must also
    # have an explicit input-index entry for installation.
    all_sources|=runtime
    return dict(schema='meownero-installation-inventory/1',
        hash_index='exact authority-bound inputs.json; candidate_files + reference.repository_files',
        groups=dict(root_helper={name:Path(name).name for name in root_sources},
            child_runtime={name:'runtime/'+name for name in sorted(runtime)},
            validation_data={name:'runtime/'+name for name in sorted(all_sources-runtime)}),
        entry_points=dict(root_helper=['profile-root-helper.py','profile-custodian.py'],child_runtime=[prefix+name for name in
            ('profile-helper.py','run-outer.py','run-profile.py','profile-integration.py','freeze-profile.py')]),
        authority_index=dict(destination='runtime/vanguard/network/integration/inputs.json',
            binding='exact independently authenticated artifact/grant inputs_file_sha256; not self-hashed'),
        external_runtime_inputs=dict(candidate_git_metadata='runtime/.git: original committed candidate identity; NOT_SUPPLIED_NOT_QUALIFIED',
            pinned_source_cache_toolchain='original run-genesis.py BASE/RUST paths and source-lock/input tree bindings; not installed source files',
            authority_and_private_state='separately authenticated contexts, capabilities, descriptors and private attempt state; UNBOUND'),
        harness_only=dict(files=[name for name in sorted(all_sources) if Path(name).name.startswith('test_')],
            usage='validation bytes only for unchanged full input checker; never helper/child entry points',
            retained_evidence='integration/evidence/ is review-only and excluded except individually declared data'),
        installed_authority='UNQUALIFIED',native_execution='NOT_RUN')


def source_inputs():
    reference=c.json_file(c.HERE/'integration/reference-inputs.json')
    reference['upstream_files']=dict(reference['upstream_files'])
    for name in EXTRA:
        raw=(UP/name).read_bytes()
        c.require(raw==subprocess.check_output(['git','-C',str(UP),'show',reference['upstream']+':'+name],timeout=10),
                  'extra source differs from pinned Git object: '+name)
        reference['upstream_files'][name]=c.digest(raw)
    files=candidate_paths()+[c.HERE/'evidence/native-genesis-attempt01/recipe1.json']
    return dict(schema='meownero-complete-profile-inputs/1',
        source_candidate_state='SOURCE_ONLY_NOT_NATIVE_ACCEPTED',launch_ready=False,
        implementation_authorization_comment='cf81ba5e-fcb5-44fe-ae6b-5537f57484bd',
        outer_source_authorization_comment='c78e1c2c-262f-41fb-9f1e-6e3ef52ca45d',
        selected_manager_source_authorization_comment='a5ec64fd-3da7-4044-8863-795ef7a6541f',
        coherent_repair_authorization_comment='157efebb-bef3-4039-9a79-739c38935024',
        generated_entry_authorization_comment='2f5ded01-5228-4f2e-89ba-7cc9c683ef91',
        helper_executor_authorization_comment='8e061330-8bd4-4665-8fa1-daeff8176dd8',
        workload_transport_authorization_comment='fdf10e5f-7009-466e-b0c5-3fa5dc70c537',
        installation_closure_authorization_comment='33f69bb2-5193-4cfe-a793-341da4809bc9',
        installed_ingress_authorization_document='operator-route:06954175-b2a7-4c19-b216-834812f372de',
        startup_custody_authorization_interaction='a9b68ef1-9aba-46ce-8a71-fcb84f2b6d29:ec6f1616-3436-4dfb-a83d-6933597cdc74',
        connected_producer_authorization_interaction='d8a029ff-74b9-4c48-90ce-3468fb762b6d:1b041a2a-caf0-4824-848a-197dd3fd6fd7',
        cleanup_settlement_authorization_interaction='48d2d44f-aed2-46ee-bce4-191e04a15ae5:5187a4f2-ee85-4a05-af3b-ed058e1cd572',
        launch_receiver_authorization_comment='8785cbdf-59d9-4019-9439-45f23404ef5c',
        launch_receiver_platform_qualification='4c84d7e3-a5cb-4ac0-a426-86fdb9bf9b9e:6bd3a0fc-7ff0-4351-828c-32bb4de7f317',
        baseline_commit=c.BASE,reference=reference,limits=c.LIMITS,
        builder_image=c.json_file(c.HERE.parent/'source-lock.json')['builder']['image_id'],
        builder_rustc=c.json_file(c.HERE.parent/'source-lock.json')['builder']['rustc'],
        platform_bootstrap_sha256=None,
        cargo_inputs={name:c.tree_fingerprint(UP.parent/'cargo-home'/name) for name in ('registry','git')},
        rust_inputs=c.tree_fingerprint(Path('~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu')),
        candidate_files={str(p.relative_to(n.ROOT)):c.digest(p.read_bytes()) for p in files},
        fixture_sha256={label:c.digest(c.chain_request(value)) for label,value in
                        [('matching-genesis',c.GENESIS),('wrong-genesis','00'*32)]},
        proposed_native_outputs=c.empty_rows(),exclusions={key:'NOT_RUN' for key in c.EXCLUDED},
        cgroup_mechanism='platform-rootful-cgroupfs-v2-fixed-ext4/2',
        native_execution='NOT_RUN')


def source_check(manifest):
    spec=importlib.util.spec_from_file_location('profile_runner',c.HERE/'run-profile.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    runner.check_inputs(c.HERE/'integration/inputs.json')
    for name in CODE:ast.parse((c.HERE/name).read_text())
    originals=policy.checked_source(UP);changed=policy.changes(originals,n.profile())
    c.require(len(changed)==10,'ten-file overlay required')
    c.require(c.digest((UP/'external/randomx/src/configuration.h').read_bytes()) ==
              manifest['reference']['randomx']['configuration_sha256'],'RandomX drift')
    methods=c.denial_requests('schema-only-address','controller-private-fixture')
    header=(UP/'src/wallet/wallet_rpc_server_commands_defs.h').read_text()
    routes=(UP/'src/wallet/wallet_rpc_server.h').read_text()
    bindings={}
    # Validate every required field from the actual pinned native request map.
    for method,params in methods.items():
        route=re.search(r'MAP_JON_RPC_WE\("'+method+r'",\s*(\w+),\s*wallet_rpc::(\w+)\)',routes)
        c.require(route is not None,'missing native method mapping: '+method)
        handler,schema=route.groups()
        section=header.split('struct '+schema+'\n',1)[1].split('struct response_t',1)[0]
        request_map=section.split('BEGIN_KV_SERIALIZE_MAP()',1)[1].split('END_KV_SERIALIZE_MAP()',1)[0]
        required=set(re.findall(r'KV_SERIALIZE\((\w+)\)',request_map))
        c.require(required <= params.keys(),'missing required schema field '+method+': '+str(required-params.keys()))
        cpp=(UP/'src/wallet/wallet_rpc_server.cpp').read_text()
        body=cpp.split('wallet_rpc_server::'+handler+'(',1)[1].split('\n  //----------------------------------------------------------------',1)[0]
        guard=min([body.find(x) for x in ['if (m_restricted)','CHECK_IF_RESTRICTED_BACKGROUND_SYNCING()',
                      'PRE_VALIDATE_BACKGROUND_SYNC()'] if x in body],default=-1)
        c.require(guard>=0,'native restricted guard absent: '+method)
        # Every fixture reaches the early restricted guard before semantic input parsing.
        first_request=re.search(r'\breq\.',body)
        c.require(first_request is None or guard<first_request.start(),'request used before denial: '+method)
        bindings[method]=dict(handler=handler,schema=schema,required_fields=sorted(required))
    cli=(UP/'src/simplewallet/simplewallet.cpp').read_text()
    for anchor in ['set_refresh_from_block_height(height)','m_wallet->rewrite(m_wallet_file, pwd_container->password())',
                   'refresh-from-block-height = ','m_wallet->get_refresh_from_block_height()',
                   'std::string prompt = std::string("[") + tr("wallet")']:
        c.require(anchor in cli,'CLI caller/prompt drift')
    build=(c.HERE/'integration/build.sh').read_text()
    c.require('--target daemon simplewallet wallet_rpc_server --parallel 1' in build and
              'BUILD_TESTS=OFF' in build,'three production targets required')
    for name,target,binary in [('src/daemon/CMakeLists.txt','daemon','monerod'),
                              ('src/simplewallet/CMakeLists.txt','simplewallet','monero-wallet-cli'),
                              ('src/wallet/CMakeLists.txt','wallet_rpc_server','monero-wallet-rpc')]:
        raw=(UP/name).read_text()
        c.require('monero_add_executable('+target in raw and 'OUTPUT_NAME "'+binary+'"' in raw,'target mapping drift')
    native=(c.HERE/'profile-integration.py').read_text()
    c.require('--fixed-difficulty' not in native and '--regtest' not in native and 'generateblocks' not in native,
              'funding/FAKECHAIN command in dedicated driver')
    c.require('PRIVATE' in native and "(PUBLIC / 'frames'" not in native,'raw frame export')
    return dict(result='PASS_SOURCE_BINDINGS_AND_INTERFACES_ONLY',native_execution='NOT_RUN',
                overlay_files=len(changed),repository_bindings=len(manifest['reference']['repository_files']),
                upstream_bindings=len(manifest['reference']['upstream_files']),
                denial_request_bindings=bindings,source_candidate_sha256=c.digest(c.canonical(manifest)),
                inputs_file_sha256=c.digest((c.HERE/'integration/inputs.json').read_bytes()),
                public_launch=False,limitations=['No native schema parser, prompt, daemon, wallet, guard, build, resource enclosure or cleanup was executed.'])


def built(build):
    # Static ELF inspection, with no execution of the three new production binaries.
    inputs=c.json_file('/out/inputs.json')
    c.require(Path('/out/rustc.txt').read_text().strip() ==
              inputs['builder_rustc'], 'rustc version drift')
    binaries={}
    for name in ('monerod','monero-wallet-cli','monero-wallet-rpc'):
        path=build/'bin'/name
        c.require(path.is_file() and os.access(path,os.X_OK),'missing production binary')
        dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True,timeout=5)
        binaries[name]=dict(sha256=c.digest(path.read_bytes()),
            needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic))
    obj=build/'src/rpc/CMakeFiles/rpc.dir/core_rpc_server.cpp.o'
    c.require(obj.is_file() and 'core_rpc_server.cpp.o' in Path('/out/build.log').read_text(),'RPC object missing')
    c.require(inputs['reference']['overlay_sha256']=='32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c','overlay')
    result=dict(three_production_binaries=dict(status='PASS',binaries=binaries),
                rpc_translation_unit=dict(status='PASS',object_sha256=c.digest(obj.read_bytes())))
    Path('/public/build.json').write_text(json.dumps(result,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--freeze',action='store_true');group.add_argument('--check',action='store_true')
    group.add_argument('--built',type=Path)
    args=p.parse_args()
    if args.built:built(args.built);return
    inventory=installation_inventory()
    inventory_path=c.HERE/'integration/installation-inventory.json'
    if args.freeze:inventory_path.write_text(json.dumps(inventory,indent=2)+'\n')
    else:c.require(c.json_file(inventory_path)==inventory,'installation inventory drift')
    current=source_inputs()
    path=c.HERE/'integration/inputs.json'
    if args.freeze:path.write_text(json.dumps(current,indent=2)+'\n')
    else:c.require(c.json_file(path)==current,'frozen source/input drift')
    print(json.dumps(source_check(current),indent=2))


if __name__=='__main__':main()
