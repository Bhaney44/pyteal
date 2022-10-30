"""
This file monkey-patches ConfigParser in order to enable
source mapping and test the results of source mapping various 
PyTeal apps.
"""

import ast
from configparser import ConfigParser
from copy import deepcopy
from enum import Flag, auto
from pathlib import Path
from typing import cast

import pytest
from unittest import mock

from algosdk.source_map import R3SourceMap

ALGOBANK = Path.cwd() / "examples" / "application" / "abi"

FIXTURES = Path.cwd() / "tests" / "unit" / "sourcemaps"


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_reconstruct(_):
    from pyteal import OptimizeOptions
    from examples.application.abi.algobank import router

    compile_bundle = router.compile_program_with_sourcemaps(
        version=6, optimize=OptimizeOptions(scratch_slots=True)
    )

    assert compile_bundle.approval_sourcemap
    assert compile_bundle.clear_sourcemap

    with open(ALGOBANK / "algobank_approval.teal") as af:
        assert af.read() == compile_bundle.approval_sourcemap.teal()

    with open(ALGOBANK / "algobank_clear_state.teal") as cf:
        assert cf.read() == compile_bundle.clear_sourcemap.teal()


def fixture_comparison(sourcemap: "PyTealSourceMap", name: str):
    new_version = sourcemap._tabulate_for_dev()
    with open(FIXTURES / f"_{name}", "w") as f:
        f.write(new_version)

    not_actually_comparing = False
    if not_actually_comparing:
        return

    with open(FIXTURES / name) as f:
        old_version = f.read()

    assert old_version == new_version


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
@pytest.mark.parametrize("version", [6])
@pytest.mark.parametrize("source_inference", [False, True])
@pytest.mark.parametrize("assemble_constants", [False, True])
@pytest.mark.parametrize("optimize_slots", [False, True])
def test_sourcemaps(_, version, source_inference, assemble_constants, optimize_slots):
    from pyteal import OptimizeOptions

    from examples.application.abi.algobank import router

    # TODO: add functionality that tallies the line statuses up and assert that all
    # statuses were > SourceMapItemStatus.PYTEAL_GENERATED

    compile_bundle = router.compile_program_with_sourcemaps(
        version=version,
        assemble_constants=assemble_constants,
        optimize=OptimizeOptions(scratch_slots=optimize_slots),
        source_inference=source_inference,
    )

    assert compile_bundle.approval_sourcemap
    assert compile_bundle.clear_sourcemap

    suffix = f"_v{version}_si{int(source_inference)}_ac{int(assemble_constants)}_ozs{int(optimize_slots)}"
    fixture_comparison(
        compile_bundle.approval_sourcemap, f"algobank_approval{suffix}.txt"
    )
    fixture_comparison(compile_bundle.clear_sourcemap, f"algobank_clear{suffix}.txt")


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_annotated_teal(_):
    from pyteal import OptimizeOptions

    from examples.application.abi.algobank import router

    compile_bundle = router.compile_program_with_sourcemaps(
        version=6,
        optimize=OptimizeOptions(scratch_slots=True),
    )

    ptsm = compile_bundle.approval_sourcemap
    assert ptsm

    table = ptsm.annotated_teal()

    with open(FIXTURES / "algobank_annotated.teal", "w") as f:
        f.write(table)

    table_ast = ptsm.annotated_teal(unparse_hybrid=True)

    with open(FIXTURES / "algobank_hybrid.teal", "w") as f:
        f.write(table_ast)

    table_concise = ptsm.annotated_teal(unparse_hybrid=True, concise=True)

    with open(FIXTURES / "algobank_concise.teal", "w") as f:
        f.write(table_concise)


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_mocked_config_for_frames(_):
    config = ConfigParser()
    assert config.getboolean("pyteal-source-mapper", "enabled") is True
    from pyteal.util import Frames

    assert Frames.skipping_all() is False
    assert Frames.skipping_all(_force_refresh=True) is False


# TODO: this is temporary


def make(x, y, z):
    import pyteal as pt

    return pt.Int(x) + pt.Int(y) + pt.Int(z)


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_lots_o_indirection(_):
    import pyteal as pt

    e1 = pt.Seq(pt.Pop(make(1, 2, 3)), pt.Pop(make(4, 5, 6)), make(7, 8, 9))

    @pt.Subroutine(pt.TealType.uint64)
    def foo(x):
        return pt.Seq(pt.Pop(e1), e1)

    bundle = pt.Compilation(foo(pt.Int(42)), pt.Mode.Application, version=6).compile(
        with_sourcemap=True
    )


@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_r3sourcemap(_):
    from pyteal import OptimizeOptions

    from examples.application.abi.algobank import router

    file = "dummy filename"
    compile_bundle = router.compile_program_with_sourcemaps(
        version=6, optimize=OptimizeOptions(scratch_slots=True), approval_filename=file
    )

    ptsm = compile_bundle.approval_sourcemap
    assert ptsm

    r3sm = ptsm.get_r3sourcemap()
    assert file == r3sm.file
    assert cast(str, r3sm.source_root).endswith("/pyteal/")
    assert list(range(len(r3sm.entries))) == [l for l, _ in r3sm.entries]
    assert all(c == 0 for _, c in r3sm.entries)
    assert all(x == (0,) for x in r3sm.index)
    assert len(r3sm.entries) == len(r3sm.index)

    source_files = [
        "examples/application/abi/algobank.py",
        "tests/unit/sourcemap_monkey_enabled_test.py",
    ]
    assert source_files == r3sm.source_files

    r3sm_json = r3sm.to_json()

    assert (
        "AAgBS;AAAA;AAAA;AAAA;AC8IT;ADpHA;AAAA;AAAA;ACoHA;AD5FA;AAAA;AAAA;AC4FA;AD/EA;AAAA;AAAA;AC+EA;AAAA;AAAA;AD/EA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AC+EA;AAAA;AD/EA;AAAA;AAAA;AC+EA;AD5FA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AC4FA;AAAA;AAAA;AAAA;AAAA;AD5FA;AAAA;AC4FA;ADpHA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;ACoHA;AAAA;ADpHA;AAAA;AAAA;ACoHA;AD9IS;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAAA;AAJL;AACc;AAAd;AAA4C;AAAc;AAA3B;AAA/B;AAFuB;AAKlB;AAAA;AC8IT;ADxIuC;AAAA;ACwIvC;AD9IS;AAAA;AAAA;AAAA;AAI6B;AAAA;AC0ItC;AAAA;AAAA;ADvJkB;AAAgB;AAAhB;AAAP;ACuJX;AAAA;AAAA;AAAA;AAAA;AAAA;ADvGe;AAAA;AAA0B;AAAA;AAA1B;AAAP;AACO;AAAA;AAA4B;AAA5B;AAAP;AAEI;AAAA;AACA;AACa;AAAA;AAAkB;AAA/B;AAAmD;AAAA;AAAnD;AAHJ;ACqGR;AAAA;AAAA;AAAA;ADnFmC;AAAgB;AAA7B;ACmFtB;AAAA;AAAA;AAAA;AAAA;AAAA;AD3DY;AACA;AACa;AAAc;AAA3B;AAA+C;AAA/C;AAHJ;AAKA;AACA;AAAA;AAG2B;AAAA;AAH3B;AAIyB;AAJzB;AAKsB;AALtB;AAQA;AAAA"
        == r3sm_json["mappings"]
    )
    assert file == r3sm_json["file"]
    assert source_files == r3sm_json["sources"]
    assert r3sm.source_root == r3sm_json["sourceRoot"]

    round_trip = R3SourceMap.from_json(
        r3sm_json, target="\n".join(r.target_extract for r in r3sm.entries.values())
    )

    assert r3sm_json == round_trip.to_json()


# ### ----------------- SANITY CHECKS SURVEY MOST PYTEAL CONSTRUCTS ----------------- ### #

P = "#pragma version {v}"  # fill the template at runtime

C = "comp.compile(with_sourcemap=True)"

BIG_A = "pt.And(pt.Gtxn[0].rekey_to() == pt.Global.zero_address(), pt.Gtxn[1].rekey_to() == pt.Global.zero_address(), pt.Gtxn[2].rekey_to() == pt.Global.zero_address(), pt.Gtxn[3].rekey_to() == pt.Global.zero_address(), pt.Gtxn[4].rekey_to() == pt.Global.zero_address(), pt.Gtxn[0].last_valid() == pt.Gtxn[1].last_valid(), pt.Gtxn[1].last_valid() == pt.Gtxn[2].last_valid(), pt.Gtxn[2].last_valid() == pt.Gtxn[3].last_valid(), pt.Gtxn[3].last_valid() == pt.Gtxn[4].last_valid(), pt.Gtxn[0].type_enum() == pt.TxnType.AssetTransfer, pt.Gtxn[0].xfer_asset() == asset_c, pt.Gtxn[0].receiver() == receiver)"
BIG_B = "pt.Or(pt.App.globalGet(pt.Bytes('paused')), pt.App.localGet(pt.Int(0), pt.Bytes('frozen')), pt.App.localGet(pt.Int(1), pt.Bytes('frozen')), pt.App.localGet(pt.Int(0), pt.Bytes('lock until')) >= pt.Global.latest_timestamp(), pt.App.localGet(pt.Int(1), pt.Bytes('lock until')) >= pt.Global.latest_timestamp(), pt.App.globalGet(pt.Concat(pt.Bytes('rule'), pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes('transfer group'))), pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes('transfer group'))))))"


"""
    asset_c = pt.Tmpl.Int("TMPL_ASSET_C")
    receiver = pt.Tmpl.Addr("TMPL_RECEIVER")
    transfer_amount = pt.Btoi(pt.Txn.application_args[1])
"""

# is_admin = pt.App.localGet(pt.Int(0), pt.Bytes("admin"))
# transfer = set_admin = mint = register = on_closeout = on_creation = pt.Return(pt.Int(1))
#     pt.Int(1)
# )
# asset_c = pt.Tmpl.Int("TMPL_ASSET_C")
# receiver = pt.Tmpl.Addr("TMPL_RECEIVER")
# transfer_amount = pt.Btoi(pt.Txn.application_args[1])

CONSTRUCTS = [
    (
        lambda pt: pt.Return(pt.Int(42)),
        [[P, C], ["int 42", "pt.Int(42)"], ["return", "pt.Return(pt.Int(42))"]],
    ),
    (lambda pt: pt.Int(42), [[P, C], ["int 42", "pt.Int(42)"], ["return", C]]),
    (
        lambda pt: pt.Seq(pt.Pop(pt.Bytes("hello world")), pt.Int(1)),
        [
            [P, C],
            ['byte "hello world"', "pt.Bytes('hello world')"],
            ["pop", "pt.Pop(pt.Bytes('hello world'))"],
            ["int 1", "pt.Int(1)"],
            ["return", C],
        ],
    ),
    (
        lambda pt: pt.Int(2) * pt.Int(3),
        [
            [P, C],
            ["int 2", "pt.Int(2)"],
            ["int 3", "pt.Int(3)"],
            ["*", "pt.Int(2) * pt.Int(3)"],
            ["return", C],
        ],
    ),
    (
        lambda pt: pt.Int(2) ^ pt.Int(3),
        [
            [P, C],
            ["int 2", "pt.Int(2)"],
            ["int 3", "pt.Int(3)"],
            ["^", "pt.Int(2) ^ pt.Int(3)"],
            ["return", C],
        ],
    ),
    (
        lambda pt: pt.Int(1) + pt.Int(2) * pt.Int(3),
        [
            [P, C],
            ["int 1", "pt.Int(1)"],
            ["int 2", "pt.Int(2)"],
            ["int 3", "pt.Int(3)"],
            ["*", "pt.Int(2) * pt.Int(3)"],
            ["+", "pt.Int(1) + pt.Int(2) * pt.Int(3)"],
            ["return", C],
        ],
    ),
    (
        lambda pt: ~pt.Int(1),
        [[P, C], ["int 1", "pt.Int(1)"], ["~", "~pt.Int(1)"], ["return", C]],
    ),
    (
        lambda pt: pt.And(
            pt.Int(1),
            pt.Int(2),
            pt.Or(pt.Int(3), pt.Int(4), pt.Or(pt.And(pt.Int(5), pt.Int(6)))),
        ),
        [
            [P, C],
            ["int 1", "pt.Int(1)"],
            ["int 2", "pt.Int(2)"],
            [
                "&&",
                "pt.And(pt.Int(1), pt.Int(2), pt.Or(pt.Int(3), pt.Int(4), pt.Or(pt.And(pt.Int(5), pt.Int(6)))))",
            ],
            ["int 3", "pt.Int(3)"],
            ["int 4", "pt.Int(4)"],
            [
                "||",
                "pt.Or(pt.Int(3), pt.Int(4), pt.Or(pt.And(pt.Int(5), pt.Int(6))))",
            ],
            ["int 5", "pt.Int(5)"],
            ["int 6", "pt.Int(6)"],
            ["&&", "pt.And(pt.Int(5), pt.Int(6))"],
            [
                "||",
                "pt.Or(pt.Int(3), pt.Int(4), pt.Or(pt.And(pt.Int(5), pt.Int(6))))",
            ],
            [
                "&&",
                "pt.And(pt.Int(1), pt.Int(2), pt.Or(pt.Int(3), pt.Int(4), pt.Or(pt.And(pt.Int(5), pt.Int(6)))))",
            ],
            ["return", C],
        ],
    ),
    # PyTEAL bugs - the following don't get parsed as expected!
    # (pt.Int(1) != pt.Int(2) == pt.Int(3), [])
    # (
    #     pt.Int(1) + pt.Int(2) - pt.Int(3) * pt.Int(4) / pt.Int(5) % pt.Int(6)
    #     < pt.Int(7)
    #     > pt.Int(8)
    #     <= pt.Int(9) ** pt.Int(10)
    #     != pt.Int(11)
    #     == pt.Int(12),
    #     [],
    # ),
    (
        lambda pt: pt.Btoi(
            pt.BytesAnd(pt.Bytes("base16", "0xBEEF"), pt.Bytes("base16", "0x1337"))
        ),
        [
            [P, C],
            ["byte 0xBEEF", "pt.Bytes('base16', '0xBEEF')"],
            ["byte 0x1337", "pt.Bytes('base16', '0x1337')"],
            [
                "b&",
                "pt.BytesAnd(pt.Bytes('base16', '0xBEEF'), pt.Bytes('base16', '0x1337'))",
            ],
            [
                "btoi",
                "pt.Btoi(pt.BytesAnd(pt.Bytes('base16', '0xBEEF'), pt.Bytes('base16', '0x1337')))",
            ],
            ["return", C],
        ],
        4,
    ),
    (
        lambda pt: pt.Btoi(pt.BytesZero(pt.Int(4))),
        [
            [P, C],
            ["int 4", "pt.Int(4)"],
            ["bzero", "pt.BytesZero(pt.Int(4))"],
            ["btoi", "pt.Btoi(pt.BytesZero(pt.Int(4)))"],
            ["return", C],
        ],
        4,
    ),
    (
        lambda pt: pt.Btoi(pt.BytesNot(pt.Bytes("base16", "0xFF00"))),
        [
            [P, C],
            ["byte 0xFF00", "pt.Bytes('base16', '0xFF00')"],
            ["b~", "pt.BytesNot(pt.Bytes('base16', '0xFF00'))"],
            ["btoi", "pt.Btoi(pt.BytesNot(pt.Bytes('base16', '0xFF00')))"],
            ["return", C],
        ],
        4,
    ),
    (
        lambda pt: pt.Seq(
            pt.Pop(pt.SetBit(pt.Bytes("base16", "0x00"), pt.Int(3), pt.Int(1))),
            pt.GetBit(pt.Int(16), pt.Int(64)),
        ),
        [
            [P, C],
            ("byte 0x00", "pt.Bytes('base16', '0x00')"),
            ("int 3", "pt.Int(3)"),
            ("int 1", "pt.Int(1)"),
            (
                "setbit",
                "pt.SetBit(pt.Bytes('base16', '0x00'), pt.Int(3), pt.Int(1))",
            ),
            (
                "pop",
                "pt.Pop(pt.SetBit(pt.Bytes('base16', '0x00'), pt.Int(3), pt.Int(1)))",
            ),
            ("int 16", "pt.Int(16)"),
            ("int 64", "pt.Int(64)"),
            ("getbit", "pt.GetBit(pt.Int(16), pt.Int(64))"),
            ("return", C),
        ],
        3,
    ),
    (
        lambda pt: pt.Seq(
            pt.Pop(pt.SetByte(pt.Bytes("base16", "0xff00"), pt.Int(0), pt.Int(0))),
            pt.GetByte(pt.Bytes("abc"), pt.Int(2)),
        ),
        [
            [P, C],
            ("byte 0xff00", "pt.Bytes('base16', '0xff00')"),
            ("int 0", "pt.Int(0)"),
            ("int 0", "pt.Int(0)"),
            (
                "setbyte",
                "pt.SetByte(pt.Bytes('base16', '0xff00'), pt.Int(0), pt.Int(0))",
            ),
            (
                "pop",
                "pt.Pop(pt.SetByte(pt.Bytes('base16', '0xff00'), pt.Int(0), pt.Int(0)))",
            ),
            ('byte "abc"', "pt.Bytes('abc')"),
            ("int 2", "pt.Int(2)"),
            ("getbyte", "pt.GetByte(pt.Bytes('abc'), pt.Int(2))"),
            ("return", C),
        ],
        3,
    ),
    (
        lambda pt: pt.Btoi(pt.Concat(pt.Bytes("a"), pt.Bytes("b"), pt.Bytes("c"))),
        [
            [P, C],
            ('byte "a"', "pt.Bytes('a')"),
            ('byte "b"', "pt.Bytes('b')"),
            ("concat", "pt.Concat(pt.Bytes('a'), pt.Bytes('b'), pt.Bytes('c'))"),
            ('byte "c"', "pt.Bytes('c')"),
            ("concat", "pt.Concat(pt.Bytes('a'), pt.Bytes('b'), pt.Bytes('c'))"),
            (
                "btoi",
                "pt.Btoi(pt.Concat(pt.Bytes('a'), pt.Bytes('b'), pt.Bytes('c')))",
            ),
            ("return", C),
        ],
    ),
    (
        lambda pt: pt.Btoi(pt.Substring(pt.Bytes("algorand"), pt.Int(2), pt.Int(8))),
        [
            [P, C],
            ('byte "algorand"', "pt.Bytes('algorand')"),
            (
                "extract 2 6",
                "pt.Substring(pt.Bytes('algorand'), pt.Int(2), pt.Int(8))",
            ),
            (
                "btoi",
                "pt.Btoi(pt.Substring(pt.Bytes('algorand'), pt.Int(2), pt.Int(8)))",
            ),
            (
                "return",
                C,
            ),
        ],
        5,
    ),
    (
        lambda pt: pt.Btoi(pt.Extract(pt.Bytes("algorand"), pt.Int(2), pt.Int(6))),
        [
            [P, C],
            ('byte "algorand"', "pt.Bytes('algorand')"),
            (
                "extract 2 6",
                "pt.Extract(pt.Bytes('algorand'), pt.Int(2), pt.Int(6))",
            ),
            (
                "btoi",
                "pt.Btoi(pt.Extract(pt.Bytes('algorand'), pt.Int(2), pt.Int(6)))",
            ),
            ("return", C),
        ],
        5,
    ),
    (
        lambda pt: pt.And(
            pt.Txn.type_enum() == pt.TxnType.Payment,
            pt.Txn.fee() < pt.Int(100),
            pt.Txn.first_valid() % pt.Int(50) == pt.Int(0),
            pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid(),
            pt.Txn.lease() == pt.Bytes("base64", "023sdDE2"),
        ),
        [
            [P, C],
            ("txn TypeEnum", "pt.Txn.type_enum()"),
            ("int pay", "pt.Txn.type_enum() == pt.TxnType.Payment"),
            ("==", "pt.Txn.type_enum() == pt.TxnType.Payment"),
            ("txn Fee", "pt.Txn.fee()"),
            ("int 100", "pt.Int(100)"),
            ("<", "pt.Txn.fee() < pt.Int(100)"),
            (
                "&&",
                "pt.And(pt.Txn.type_enum() == pt.TxnType.Payment, pt.Txn.fee() < pt.Int(100), pt.Txn.first_valid() % pt.Int(50) == pt.Int(0), pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid(), pt.Txn.lease() == pt.Bytes('base64', '023sdDE2'))",
            ),
            ("txn FirstValid", "pt.Txn.first_valid()"),
            ("int 50", "pt.Int(50)"),
            ("%", "pt.Txn.first_valid() % pt.Int(50)"),
            ("int 0", "pt.Int(0)"),
            ("==", "pt.Txn.first_valid() % pt.Int(50) == pt.Int(0)"),
            (
                "&&",
                "pt.And(pt.Txn.type_enum() == pt.TxnType.Payment, pt.Txn.fee() < pt.Int(100), pt.Txn.first_valid() % pt.Int(50) == pt.Int(0), pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid(), pt.Txn.lease() == pt.Bytes('base64', '023sdDE2'))",
            ),
            ("txn LastValid", "pt.Txn.last_valid()"),
            ("int 5000", "pt.Int(5000)"),
            ("txn FirstValid", "pt.Txn.first_valid()"),
            ("+", "pt.Int(5000) + pt.Txn.first_valid()"),
            ("==", "pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid()"),
            (
                "&&",
                "pt.And(pt.Txn.type_enum() == pt.TxnType.Payment, pt.Txn.fee() < pt.Int(100), pt.Txn.first_valid() % pt.Int(50) == pt.Int(0), pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid(), pt.Txn.lease() == pt.Bytes('base64', '023sdDE2'))",
            ),
            ("txn Lease", "pt.Txn.lease()"),
            ("byte base64(023sdDE2)", "pt.Bytes('base64', '023sdDE2')"),
            ("==", "pt.Txn.lease() == pt.Bytes('base64', '023sdDE2')"),
            (
                "&&",
                "pt.And(pt.Txn.type_enum() == pt.TxnType.Payment, pt.Txn.fee() < pt.Int(100), pt.Txn.first_valid() % pt.Int(50) == pt.Int(0), pt.Txn.last_valid() == pt.Int(5000) + pt.Txn.first_valid(), pt.Txn.lease() == pt.Bytes('base64', '023sdDE2'))",
            ),
            ("return", C),
        ],
    ),
    (
        lambda pt: [
            is_admin := pt.App.localGet(pt.Int(0), pt.Bytes("admin")),
            foo := pt.Return(pt.Int(1)),
            pt.Cond(
                [pt.Txn.application_id() == pt.Int(0), foo],
                [
                    pt.Txn.on_completion() == pt.OnComplete.DeleteApplication,
                    pt.Return(is_admin),
                ],
                [
                    pt.Txn.on_completion() == pt.OnComplete.UpdateApplication,
                    pt.Return(is_admin),
                ],
                [pt.Txn.on_completion() == pt.OnComplete.CloseOut, foo],
                [pt.Txn.on_completion() == pt.OnComplete.OptIn, foo],
                [pt.Txn.application_args[0] == pt.Bytes("set admin"), foo],
                [pt.Txn.application_args[0] == pt.Bytes("mint"), foo],
                [pt.Txn.application_args[0] == pt.Bytes("transfer"), foo],
                [pt.Txn.accounts[4] == pt.Bytes("foo"), foo],
            ),
        ][-1],
        [
            [P, C],
            ("txn ApplicationID", "pt.Txn.application_id()"),
            ("int 0", "pt.Int(0)"),
            ("==", "pt.Txn.application_id() == pt.Int(0)"),
            ("bnz main_l18", C),  # ... makes sense
            ("txn OnCompletion", "pt.Txn.on_completion()"),
            (
                "int DeleteApplication",
                "pt.Txn.on_completion() == pt.OnComplete.DeleteApplication",
            ),  # source inferencing at work here!!!!
            ("==", "pt.Txn.on_completion() == pt.OnComplete.DeleteApplication"),
            ("bnz main_l17", C),  # makes sense
            ("txn OnCompletion", "pt.Txn.on_completion()"),
            (
                "int UpdateApplication",
                "pt.Txn.on_completion() == pt.OnComplete.UpdateApplication",
            ),  # source inferencing
            ("==", "pt.Txn.on_completion() == pt.OnComplete.UpdateApplication"),
            ("bnz main_l16", C),  # yep
            ("txn OnCompletion", "pt.Txn.on_completion()"),
            ("int CloseOut", "pt.Txn.on_completion() == pt.OnComplete.CloseOut"),
            ("==", "pt.Txn.on_completion() == pt.OnComplete.CloseOut"),
            ("bnz main_l15", C),
            ("txn OnCompletion", "pt.Txn.on_completion()"),
            ("int OptIn", "pt.Txn.on_completion() == pt.OnComplete.OptIn"),
            ("==", "pt.Txn.on_completion() == pt.OnComplete.OptIn"),
            ("bnz main_l14", C),
            ("txna ApplicationArgs 0", "pt.Txn.application_args[0]"),
            ('byte "set admin"', "pt.Bytes('set admin')"),
            ("==", "pt.Txn.application_args[0] == pt.Bytes('set admin')"),
            ("bnz main_l13", C),
            ("txna ApplicationArgs 0", "pt.Txn.application_args[0]"),
            ('byte "mint"', "pt.Bytes('mint')"),
            ("==", "pt.Txn.application_args[0] == pt.Bytes('mint')"),
            ("bnz main_l12", C),
            ("txna ApplicationArgs 0", "pt.Txn.application_args[0]"),
            ('byte "transfer"', "pt.Bytes('transfer')"),
            ("==", "pt.Txn.application_args[0] == pt.Bytes('transfer')"),
            ("bnz main_l11", C),
            ("txna Accounts 4", "pt.Txn.accounts[4]"),
            ('byte "foo"', "pt.Bytes('foo')"),
            ("==", "pt.Txn.accounts[4] == pt.Bytes('foo')"),
            ("bnz main_l10", C),
            (
                "err",
                "pt.Cond([pt.Txn.application_id() == pt.Int(0), foo], [pt.Txn.on_completion() == pt.OnComplete.DeleteApplication, pt.Return(is_admin)], [pt.Txn.on_completion() == pt.OnComplete.UpdateApplication, pt.Return(is_admin)], [pt.Txn.on_completion() == pt.OnComplete.CloseOut, foo], [pt.Txn.on_completion() == pt.OnComplete.OptIn, foo], [pt.Txn.application_args[0] == pt.Bytes('set admin'), foo], [pt.Txn.application_args[0] == pt.Bytes('mint'), foo], [pt.Txn.application_args[0] == pt.Bytes('transfer'), foo], [pt.Txn.accounts[4] == pt.Bytes('foo'), foo])",
            ),  # OUCH - this nastiness is from Cond gnerating an err block at the very end!!!
            ("main_l10:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l11:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l12:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l13:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l14:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l15:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
            ("main_l16:", C),
            ("int 0", "pt.Int(0)"),
            ('byte "admin"', "pt.Bytes('admin')"),
            ("app_local_get", "pt.App.localGet(pt.Int(0), pt.Bytes('admin'))"),
            ("return", "pt.Return(is_admin)"),
            ("main_l17:", C),
            ("int 0", "pt.Int(0)"),
            ('byte "admin"', "pt.Bytes('admin')"),
            ("app_local_get", "pt.App.localGet(pt.Int(0), pt.Bytes('admin'))"),
            ("return", "pt.Return(is_admin)"),
            ("main_l18:", C),
            ("int 1", "pt.Int(1)"),
            ("return", "pt.Return(pt.Int(1))"),
        ],
        2,
        "Application",
    ),
    (
        lambda pt: [
            asset_c := pt.Tmpl.Int("TMPL_ASSET_C"),
            receiver := pt.Tmpl.Addr("TMPL_RECEIVER"),
            pt.And(
                pt.Gtxn[0].rekey_to() == pt.Global.zero_address(),
                pt.Gtxn[1].rekey_to() == pt.Global.zero_address(),
                pt.Gtxn[2].rekey_to() == pt.Global.zero_address(),
                pt.Gtxn[3].rekey_to() == pt.Global.zero_address(),
                pt.Gtxn[4].rekey_to() == pt.Global.zero_address(),
                pt.Gtxn[0].last_valid() == pt.Gtxn[1].last_valid(),
                pt.Gtxn[1].last_valid() == pt.Gtxn[2].last_valid(),
                pt.Gtxn[2].last_valid() == pt.Gtxn[3].last_valid(),
                pt.Gtxn[3].last_valid() == pt.Gtxn[4].last_valid(),
                pt.Gtxn[0].type_enum() == pt.TxnType.AssetTransfer,
                pt.Gtxn[0].xfer_asset() == asset_c,
                pt.Gtxn[0].receiver() == receiver,
            ),
        ][-1],
        [
            [P, C],
            ("gtxn 0 RekeyTo", "pt.Gtxn[0].rekey_to()"),
            ("global ZeroAddress", "pt.Global.zero_address()"),
            ("==", "pt.Gtxn[0].rekey_to() == pt.Global.zero_address()"),
            ("gtxn 1 RekeyTo", "pt.Gtxn[1].rekey_to()"),
            ("global ZeroAddress", "pt.Global.zero_address()"),
            ("==", "pt.Gtxn[1].rekey_to() == pt.Global.zero_address()"),
            ("&&", BIG_A),
            ("gtxn 2 RekeyTo", "pt.Gtxn[2].rekey_to()"),
            ("global ZeroAddress", "pt.Global.zero_address()"),
            ("==", "pt.Gtxn[2].rekey_to() == pt.Global.zero_address()"),
            ("&&", BIG_A),
            ("gtxn 3 RekeyTo", "pt.Gtxn[3].rekey_to()"),
            ("global ZeroAddress", "pt.Global.zero_address()"),
            ("==", "pt.Gtxn[3].rekey_to() == pt.Global.zero_address()"),
            ("&&", BIG_A),
            ("gtxn 4 RekeyTo", "pt.Gtxn[4].rekey_to()"),
            ("global ZeroAddress", "pt.Global.zero_address()"),
            ("==", "pt.Gtxn[4].rekey_to() == pt.Global.zero_address()"),
            ("&&", BIG_A),
            ("gtxn 0 LastValid", "pt.Gtxn[0].last_valid()"),
            ("gtxn 1 LastValid", "pt.Gtxn[1].last_valid()"),
            ("==", "pt.Gtxn[0].last_valid() == pt.Gtxn[1].last_valid()"),
            ("&&", BIG_A),
            ("gtxn 1 LastValid", "pt.Gtxn[1].last_valid()"),
            ("gtxn 2 LastValid", "pt.Gtxn[2].last_valid()"),
            ("==", "pt.Gtxn[1].last_valid() == pt.Gtxn[2].last_valid()"),
            ("&&", BIG_A),
            ("gtxn 2 LastValid", "pt.Gtxn[2].last_valid()"),
            ("gtxn 3 LastValid", "pt.Gtxn[3].last_valid()"),
            ("==", "pt.Gtxn[2].last_valid() == pt.Gtxn[3].last_valid()"),
            ("&&", BIG_A),
            ("gtxn 3 LastValid", "pt.Gtxn[3].last_valid()"),
            ("gtxn 4 LastValid", "pt.Gtxn[4].last_valid()"),
            ("==", "pt.Gtxn[3].last_valid() == pt.Gtxn[4].last_valid()"),
            ("&&", BIG_A),
            ("gtxn 0 TypeEnum", "pt.Gtxn[0].type_enum()"),
            (
                "int axfer",
                "pt.Gtxn[0].type_enum() == pt.TxnType.AssetTransfer",
            ),  # source inference
            ("==", "pt.Gtxn[0].type_enum() == pt.TxnType.AssetTransfer"),
            ("&&", BIG_A),
            ("gtxn 0 XferAsset", "pt.Gtxn[0].xfer_asset()"),
            ("int TMPL_ASSET_C", "pt.Tmpl.Int('TMPL_ASSET_C')"),
            ("==", "pt.Gtxn[0].xfer_asset() == asset_c"),
            ("&&", BIG_A),
            ("gtxn 0 Receiver", "pt.Gtxn[0].receiver()"),
            ("addr TMPL_RECEIVER", "pt.Tmpl.Addr('TMPL_RECEIVER')"),
            ("==", "pt.Gtxn[0].receiver() == receiver"),
            ("&&", BIG_A),
            ("return", C),
        ],
    ),
    (
        lambda pt: pt.And(
            pt.Txn.application_args.length(),  # get the number of application arguments in the transaction
            # as of AVM v5, PyTeal expressions can be used to dynamically index into array properties as well
            pt.Btoi(
                pt.Txn.application_args[pt.Txn.application_args.length() - pt.Int(1)]
            ),
        ),
        [
            [P, C],
            ("txn NumAppArgs", "pt.Txn.application_args.length()"),
            ("txn NumAppArgs", "pt.Txn.application_args.length()"),
            ("int 1", "pt.Int(1)"),
            ("-", "pt.Txn.application_args.length() - pt.Int(1)"),
            (
                "txnas ApplicationArgs",
                "pt.Txn.application_args[pt.Txn.application_args.length() - pt.Int(1)]",
            ),
            (
                "btoi",
                "pt.Btoi(pt.Txn.application_args[pt.Txn.application_args.length() - pt.Int(1)])",
            ),
            (
                "&&",
                "pt.And(pt.Txn.application_args.length(), pt.Btoi(pt.Txn.application_args[pt.Txn.application_args.length() - pt.Int(1)]))",
            ),
            ("return", C),
        ],
        5,
    ),
    (
        lambda pt: pt.Seq(
            receiver_max_balance := pt.App.localGetEx(
                pt.Int(1), pt.App.id(), pt.Bytes("max balance")
            ),
            pt.Or(
                pt.App.globalGet(pt.Bytes("paused")),
                pt.App.localGet(pt.Int(0), pt.Bytes("frozen")),
                pt.App.localGet(pt.Int(1), pt.Bytes("frozen")),
                pt.App.localGet(pt.Int(0), pt.Bytes("lock until"))
                >= pt.Global.latest_timestamp(),
                pt.App.localGet(pt.Int(1), pt.Bytes("lock until"))
                >= pt.Global.latest_timestamp(),
                pt.App.globalGet(
                    pt.Concat(
                        pt.Bytes("rule"),
                        pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes("transfer group"))),
                        pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes("transfer group"))),
                    )
                ),
            ),
        ),
        [
            [P, C],
            ("int 1", "pt.Int(1)"),
            ("global CurrentApplicationID", "pt.App.id()"),
            ('byte "max balance"', "pt.Bytes('max balance')"),
            (
                "app_local_get_ex",
                "pt.App.localGetEx(pt.Int(1), pt.App.id(), pt.Bytes('max balance'))",
            ),
            ("store 1", C),
            ("store 0", C),
            ('byte "paused"', "pt.Bytes('paused')"),
            ("app_global_get", "pt.App.globalGet(pt.Bytes('paused'))"),
            ("int 0", "pt.Int(0)"),
            ('byte "frozen"', "pt.Bytes('frozen')"),
            ("app_local_get", "pt.App.localGet(pt.Int(0), pt.Bytes('frozen'))"),
            ("||", BIG_B),
            ("int 1", "pt.Int(1)"),
            ('byte "frozen"', "pt.Bytes('frozen')"),
            ("app_local_get", "pt.App.localGet(pt.Int(1), pt.Bytes('frozen'))"),
            ("||", BIG_B),
            ("int 0", "pt.Int(0)"),
            ('byte "lock until"', "pt.Bytes('lock until')"),
            ("app_local_get", "pt.App.localGet(pt.Int(0), pt.Bytes('lock until'))"),
            ("global LatestTimestamp", "pt.Global.latest_timestamp()"),
            (
                ">=",
                "pt.App.localGet(pt.Int(0), pt.Bytes('lock until')) >= pt.Global.latest_timestamp()",
            ),
            ("||", BIG_B),
            ("int 1", "pt.Int(1)"),
            ('byte "lock until"', "pt.Bytes('lock until')"),
            ("app_local_get", "pt.App.localGet(pt.Int(1), pt.Bytes('lock until'))"),
            ("global LatestTimestamp", "pt.Global.latest_timestamp()"),
            (
                ">=",
                "pt.App.localGet(pt.Int(1), pt.Bytes('lock until')) >= pt.Global.latest_timestamp()",
            ),
            ("||", BIG_B),
            ('byte "rule"', "pt.Bytes('rule')"),
            ("int 0", "pt.Int(0)"),
            ('byte "transfer group"', "pt.Bytes('transfer group')"),
            (
                "app_local_get",
                "pt.App.localGet(pt.Int(0), pt.Bytes('transfer group'))",
            ),
            (
                "itob",
                "pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes('transfer group')))",
            ),
            (
                "concat",
                "pt.Concat(pt.Bytes('rule'), pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes('transfer group'))), pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes('transfer group'))))",
            ),
            ("int 1", "pt.Int(1)"),
            ('byte "transfer group"', "pt.Bytes('transfer group')"),
            (
                "app_local_get",
                "pt.App.localGet(pt.Int(1), pt.Bytes('transfer group'))",
            ),
            ("itob", "pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes('transfer group')))"),
            (
                "concat",
                "pt.Concat(pt.Bytes('rule'), pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes('transfer group'))), pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes('transfer group'))))",
            ),
            (
                "app_global_get",
                "pt.App.globalGet(pt.Concat(pt.Bytes('rule'), pt.Itob(pt.App.localGet(pt.Int(0), pt.Bytes('transfer group'))), pt.Itob(pt.App.localGet(pt.Int(1), pt.Bytes('transfer group')))))",
            ),
            ("||", BIG_B),
            ("return", C),
        ],
        2,
        "Application",
    ),
    (
        lambda pt: pt.EcdsaVerify(
            pt.EcdsaCurve.Secp256k1,
            pt.Sha512_256(pt.Bytes("testdata")),
            pt.Bytes(
                "base16",
                "33602297203d2753372cea7794ffe1756a278cbc4907b15a0dd132c9fb82555e",
            ),
            pt.Bytes(
                "base16",
                "20f112126cf3e2eac6e8d4f97a403d21bab07b8dbb77154511bb7b07c0173195",
            ),
            (
                pt.Bytes(
                    "base16",
                    "d6143a58c90c06b594e4414cb788659c2805e0056b1dfceea32c03f59efec517",
                ),
                pt.Bytes(
                    "base16",
                    "00bd2400c479efe5ea556f37e1dc11ccb20f1e642dbfe00ca346fffeae508298",
                ),
            ),
        ),
        [
            [P, C],
            ['byte "testdata"', "pt.Bytes('testdata')"],
            ["sha512_256", "pt.Sha512_256(pt.Bytes('testdata'))"],
            [
                "byte 0x33602297203d2753372cea7794ffe1756a278cbc4907b15a0dd132c9fb82555e",
                "pt.Bytes('base16', '33602297203d2753372cea7794ffe1756a278cbc4907b15a0dd132c9fb82555e')",
            ],
            [
                "byte 0x20f112126cf3e2eac6e8d4f97a403d21bab07b8dbb77154511bb7b07c0173195",
                "pt.Bytes('base16', '20f112126cf3e2eac6e8d4f97a403d21bab07b8dbb77154511bb7b07c0173195')",
            ],
            [
                "byte 0xd6143a58c90c06b594e4414cb788659c2805e0056b1dfceea32c03f59efec517",
                "pt.Bytes('base16', 'd6143a58c90c06b594e4414cb788659c2805e0056b1dfceea32c03f59efec517')",
            ],
            [
                "byte 0x00bd2400c479efe5ea556f37e1dc11ccb20f1e642dbfe00ca346fffeae508298",
                "pt.Bytes('base16', '00bd2400c479efe5ea556f37e1dc11ccb20f1e642dbfe00ca346fffeae508298')",
            ],
            [
                "ecdsa_verify Secp256k1",
                "pt.EcdsaVerify(pt.EcdsaCurve.Secp256k1, pt.Sha512_256(pt.Bytes('testdata')), pt.Bytes('base16', '33602297203d2753372cea7794ffe1756a278cbc4907b15a0dd132c9fb82555e'), pt.Bytes('base16', '20f112126cf3e2eac6e8d4f97a403d21bab07b8dbb77154511bb7b07c0173195'), (pt.Bytes('base16', 'd6143a58c90c06b594e4414cb788659c2805e0056b1dfceea32c03f59efec517'), pt.Bytes('base16', '00bd2400c479efe5ea556f37e1dc11ccb20f1e642dbfe00ca346fffeae508298')))",
            ],
            ["return", C],
        ],
        5,
    ),
    (
        lambda pt: [
            myvar := pt.ScratchVar(
                pt.TealType.uint64
            ),  # assign a scratch slot in any available slot
            anotherVar := pt.ScratchVar(
                pt.TealType.bytes, 4
            ),  # assign this scratch slot to slot #4
            pt.Seq(
                [
                    myvar.store(pt.Int(5)),
                    anotherVar.store(pt.Bytes("hello")),
                    pt.Assert(myvar.load() == pt.Int(5)),
                    pt.Return(pt.Int(1)),
                ]
            ),
        ][-1],
        [
            [P, C],
            ["int 5", "pt.Int(5)"],
            ["store 0", "myvar.store(pt.Int(5))"],
            ['byte "hello"', "pt.Bytes('hello')"],
            ["store 4", "anotherVar.store(pt.Bytes('hello'))"],
            ["load 0", "myvar.load()"],
            ["int 5", "pt.Int(5)"],
            ["==", "myvar.load() == pt.Int(5)"],
            ["assert", "pt.Assert(myvar.load() == pt.Int(5))"],
            ["int 1", "pt.Int(1)"],
            ["return", "pt.Return(pt.Int(1))"],
        ],
        3,
    ),
    (
        lambda pt: [
            s := pt.ScratchVar(pt.TealType.uint64),
            d := pt.DynamicScratchVar(pt.TealType.uint64),
            pt.Seq(
                d.set_index(s),
                s.store(pt.Int(7)),
                d.store(d.load() + pt.Int(3)),
                pt.Assert(s.load() == pt.Int(10)),
                pt.Int(1),
            ),
        ][-1],
        [
            [P, C],
            ["int 0", "d.set_index(s)"],
            ["store 1", "d.set_index(s)"],
            ["int 7", "pt.Int(7)"],
            ["store 0", "s.store(pt.Int(7))"],
            ["load 1", "d.store(d.load() + pt.Int(3))"],
            ["load 1", "d.load()"],
            ["loads", "d.load()"],
            ["int 3", "pt.Int(3)"],
            ["+", "d.load() + pt.Int(3)"],
            ["stores", "d.store(d.load() + pt.Int(3))"],
            ["load 0", "s.load()"],
            ["int 10", "pt.Int(10)"],
            ["==", "s.load() == pt.Int(10)"],
            ["assert", "pt.Assert(s.load() == pt.Int(10))"],
            ["int 1", "pt.Int(1)"],
            ["return", C],
        ],
        5,
    ),
    (
        lambda pt: [  # App is called at transaction index 0
            greeting := pt.ScratchVar(
                pt.TealType.bytes, 20
            ),  # this variable will live in scratch slot 20
            app1_seq := pt.Seq(
                [
                    pt.If(pt.Txn.sender() == pt.App.globalGet(pt.Bytes("creator")))
                    .Then(greeting.store(pt.Bytes("hi creator!")))
                    .Else(greeting.store(pt.Bytes("hi user!"))),
                    pt.Int(1),
                ]
            ),
            greetingFromPreviousApp := pt.ImportScratchValue(
                0, 20
            ),  # loading scratch slot 20 from the transaction at index 0
            app2_seq := pt.Seq(
                [
                    # not shown: make sure that the transaction at index 0 is an app call to App A
                    pt.App.globalPut(
                        pt.Bytes("greeting from prev app"), greetingFromPreviousApp
                    ),
                    pt.Int(1),
                ]
            ),
            pt.And(app1_seq, app2_seq),
        ][-1],
        [
            [P, C],
            ["txn Sender", "pt.Txn.sender()"],
            ['byte "creator"', "pt.Bytes('creator')"],
            ["app_global_get", "pt.App.globalGet(pt.Bytes('creator'))"],
            ["==", "pt.Txn.sender() == pt.App.globalGet(pt.Bytes('creator'))"],
            [
                "bnz main_l2",
                "pt.If(pt.Txn.sender() == pt.App.globalGet(pt.Bytes('creator')))",
            ],
            ['byte "hi user!"', "pt.Bytes('hi user!')"],
            ["store 20", "greeting.store(pt.Bytes('hi user!'))"],
            ["b main_l3", C],
            [
                "main_l2:",
                "pt.If(pt.Txn.sender() == pt.App.globalGet(pt.Bytes('creator')))",
            ],
            ['byte "hi creator!"', "pt.Bytes('hi creator!')"],
            ["store 20", "greeting.store(pt.Bytes('hi creator!'))"],
            ["main_l3:", C],
            ["int 1", "pt.Int(1)"],
            ['byte "greeting from prev app"', "pt.Bytes('greeting from prev app')"],
            ["gload 0 20", "pt.ImportScratchValue(0, 20)"],
            [
                "app_global_put",
                "pt.App.globalPut(pt.Bytes('greeting from prev app'), greetingFromPreviousApp)",
            ],
            ["int 1", "pt.Int(1)"],
            ["&&", "pt.And(app1_seq, app2_seq)"],
            ["return", C],
        ],
        4,
        "Application",
    ),
    # (lambda pt: If(pt.Int(0)).Then),
]


@pytest.mark.parametrize("i, test_case", enumerate(CONSTRUCTS))
@pytest.mark.parametrize("mode", ["Application", "Signature"])
@pytest.mark.parametrize("version", range(2, 8))
@mock.patch.object(ConfigParser, "getboolean", return_value=True)
def test_constructs(_, i, test_case, mode, version):
    """
    Sanity check source mapping the most important PyTeal constructs

    Cannot utilize @pytest.mark.parametrize because of monkeypatching
    """
    import pyteal as pt

    def unparse(sourcemap_items):
        return list(map(lambda smi: ast.unparse(smi.frame.node), sourcemap_items))

    expr, line2unparsed = test_case[:2]
    line2unparsed = deepcopy(line2unparsed)
    # fill the pragma template:
    line2unparsed[0][0] = line2unparsed[0][0].format(v=version)

    expr = expr(pt)
    if len(test_case) > 2:
        min_version = test_case[2]
        if version < min_version:
            return
    if len(test_case) > 3:
        fixed_mode = test_case[3]
        if mode != fixed_mode:
            return

    mode = getattr(pt.Mode, mode)
    comp = pt.Compilation(
        expr, mode, version=version, assemble_constants=False, optimize=None
    )
    bundle = comp.compile(with_sourcemap=True)
    sourcemap = bundle.sourcemap

    msg = f"[CASE #{i+1}]: {expr=}, {bundle=}"

    assert sourcemap, msg
    assert sourcemap.hybrid is True, msg
    assert sourcemap.source_inference is True, msg

    smis = sourcemap.as_list()
    expected_lines, unparsed = list(zip(*line2unparsed))

    msg = f"{msg}, {smis=}"
    assert list(expected_lines) == bundle.lines, msg
    assert list(expected_lines) == sourcemap.teal_chunks, msg
    assert list(unparsed) == unparse(smis), msg