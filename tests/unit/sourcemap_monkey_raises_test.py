from configparser import ConfigParser
from unittest import mock

import pytest

# TODO - why is this failing when running together with other tests?
# Perhaps - I need proper setup/teardowns for this test

# TODO: this isn't actually an integration test. However, this is
# clashing with the monkey patching of `tests/unit/sourcemap_monkey_enabled_test.py`
# so I'm keeping this as a faux integration test for now


@mock.patch.object(ConfigParser, "getboolean", side_effect=Exception("1337"))
def test_sourcemap_fails_elegantly_when_no_ini(_):
    from examples.application.abi.algobank import router
    from pyteal import OptimizeOptions
    from pyteal.compiler.sourcemap import SourceMapDisabledError

    with pytest.raises(SourceMapDisabledError) as smde:
        router.compile_program_with_sourcemaps(
            version=6,
            optimize=OptimizeOptions(scratch_slots=True),
        )

    assert "pyteal.ini" in str(smde.value)
    assert "1337" not in str(smde.value)