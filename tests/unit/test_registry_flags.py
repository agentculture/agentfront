"""Unit tests for per-verb FLAG declarations (t5)."""

import argparse

import pytest

from agentfront._registry import Flag, ToolEntry, apply_flags


def _make_entry(flags: tuple[Flag, ...]) -> ToolEntry:
    """Build a minimal ToolEntry with the given flags."""

    def _fn() -> None:
        pass

    return ToolEntry(
        name="test_op",
        description="test",
        input_schema={"type": "object", "properties": {}},
        func=_fn,
        flags=flags,
    )


def test_typed_flag_parses_int():
    entry = _make_entry((Flag(names=("--count",), type=int, default=0),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--count", "5"])
    assert ns.count == 5
    assert isinstance(ns.count, int)


def test_boolean_optional_flag():
    entry = _make_entry((Flag(names=("--verbose",), action="boolean_optional"),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--verbose"])
    assert ns.verbose is True
    ns2 = parser.parse_args(["--no-verbose"])
    assert ns2.verbose is False


def test_dest_rename():
    entry = _make_entry((Flag(names=("--out",), dest="output_path"),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--out", "x"])
    assert ns.output_path == "x"


def test_combined_flags_parse_correctly():
    entry = _make_entry(
        (
            Flag(names=("--count",), type=int, default=0),
            Flag(names=("--verbose",), action="boolean_optional"),
            Flag(names=("--out",), dest="output_path"),
        )
    )
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--count", "5", "--verbose", "--out", "x"])
    assert ns.count == 5
    assert ns.verbose is True
    assert ns.output_path == "x"


def test_combined_flags_no_verbose():
    entry = _make_entry(
        (
            Flag(names=("--count",), type=int, default=0),
            Flag(names=("--verbose",), action="boolean_optional"),
            Flag(names=("--out",), dest="output_path"),
        )
    )
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--no-verbose"])
    assert ns.verbose is False


def test_default_flags_empty():
    entry = _make_entry(())
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args([])
    # no extra attributes beyond _flags_holder or similar internals
    assert not hasattr(ns, "count")


def test_flag_with_short_and_long_name():
    entry = _make_entry((Flag(names=("-c", "--count"), type=int, default=0),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["-c", "10"])
    assert ns.count == 10


def test_flag_required():
    entry = _make_entry((Flag(names=("--name",), required=True),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_flag_help():
    entry = _make_entry((Flag(names=("--msg",), help="A message"),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    # Just verify it doesn't raise; help text is stored on the action
    action = parser._actions[-1]
    assert action.help == "A message"


def test_flag_nargs():
    entry = _make_entry((Flag(names=("--files",), nargs=3),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--files", "a", "b", "c"])
    assert ns.files == ["a", "b", "c"]


def test_choices_flag_accepts_in_set_value():
    entry = _make_entry((Flag(names=("--algo",), choices=("sha256", "md5")),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    ns = parser.parse_args(["--algo", "sha256"])
    assert ns.algo == "sha256"


def test_choices_flag_rejects_out_of_set_value():
    entry = _make_entry((Flag(names=("--algo",), choices=("sha256", "md5")),))
    parser = argparse.ArgumentParser()
    apply_flags(parser, entry)
    with pytest.raises(SystemExit):
        parser.parse_args(["--algo", "crc32"])


def test_flag_without_choices_is_unchanged():
    """A choices-less Flag forwards no ``choices`` kwarg — byte-identical to before."""
    from agentfront._registry import _flag_kwargs

    assert "choices" not in _flag_kwargs(Flag(names=("--x",)))
    assert _flag_kwargs(Flag(names=("--algo",), choices=("sha256", "md5")))["choices"] == (
        "sha256",
        "md5",
    )
