from ast import unparse
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
from executing import Source
from inspect import FrameInfo
import os
from typing import cast, Any, OrderedDict, Optional, Sequence, Union

from tabulate import tabulate

from algosdk.source_map import SourceMapping

from pyteal.util import Frame, FrameSequence
import pyteal as pt


class SourceMapItemStatus(IntEnum):
    """integer values indicate 'confidence' on a scale of 0 - 10"""

    MISSING = 0
    MISSING_AST = 1
    MISSING_CODE = 2
    PYTEAL_GENERATED = 3
    PATCHED_BY_PREV_OVERRIDE_NEXT = 4
    PATCHED_BY_NEXT_OVERRIDE_PREV = 5
    PATCHED_BY_PREV = 6
    PATCHED_BY_NEXT = 7
    PATCHED_BY_PREV_AND_NEXT = 8
    COPACETIC = 9  # currently, 90% confidient is as good as it gets

    def human(self) -> str:
        match self:
            case self.MISSING:
                return "sourcemapping line: total failure"
            case self.MISSING_AST:
                return "unreliable as missing AST"
            case self.MISSING_CODE:
                return "unreliable as couldn't retrieve source"
            case self.PYTEAL_GENERATED:
                return "INCOMPLETE"  # "incomplete as source not user generated"
            case self.PATCHED_BY_PREV_OVERRIDE_NEXT:
                return "previously INCOMPLETE- patched to previous frame (ambiguous)"
            case self.PATCHED_BY_NEXT_OVERRIDE_PREV:
                return "previously INCOMPLETE- patched to next frame (ambiguous)"
            case self.PATCHED_BY_PREV:
                return "previously INCOMPLETE- patched to previous frame"
            case self.PATCHED_BY_NEXT:
                return "previously INCOMPLETE- patched to next frame"
            case self.PATCHED_BY_PREV_AND_NEXT:
                return "previously INCOMPLETE- patched"
            case self.COPACETIC:
                return "COPACETIC"

        raise Exception(f"unrecognized {type(self)} - THIS SHOULD NEVER HAPPEN!")


PyTealFrameSequence = Union["PyTealFrame", list["PyTealFrameSequence"]]

PT_GENERATED_PRAGMA = "PyTeal generated pragma"
PT_GENERATED_SUBR_LABEL = "PyTeal generated subroutine label"
PT_GENERATED_RETURN_NONE = "PyTeal generated return for TealType.none"
PT_GENERATED_RETURN_VALUE = "PyTeal generated return for non-null TealType"
PT_GENERATED_SUBR_PARAM = "PyTeal generated subroutine parameter handler instruction"
PT_GENERATED_BRANCH = "PyTeal generated branching"
PT_GENERATED_BRANCH_LABEL = "PyTeal generated branching label"
PT_GENERATED_TYPE_ENUM_TXN = "PyTeal generated transaction Type Enum"
PT_GENERATED_TYPE_ENUM_ONCOMPLETE = "PyTeal generated OnComplete Type Enum"


_PT_GEN = {
    "# T2PT0": PT_GENERATED_PRAGMA,
    "# T2PT1": PT_GENERATED_SUBR_LABEL,
    "# T2PT2": PT_GENERATED_RETURN_NONE,
    "# T2PT3": PT_GENERATED_RETURN_VALUE,
    "# T2PT4": PT_GENERATED_SUBR_PARAM,
    "# T2PT5": PT_GENERATED_BRANCH,
    "# T2PT6": PT_GENERATED_BRANCH_LABEL,
    "# T2PT7": PT_GENERATED_TYPE_ENUM_TXN,
    "# T2PT8": PT_GENERATED_TYPE_ENUM_ONCOMPLETE,
}


class PyTealFrame:
    def __init__(
        self,
        frame: Frame,
        rel_paths: bool = True,
        parent: Optional["PyTealFrame"] | None = None,
    ):
        self.frame_info = frame.frame_info
        self.node = frame.node
        self.rel_paths = rel_paths
        self.parent = parent

        self._raw_code: str | None = None
        self._status: SourceMapItemStatus | None = None

    def frame(self) -> Frame:
        return Frame(self.frame_info, self.node)

    def __eq__(self, other: "PyTealFrame") -> bool:
        """We don't care about parents here. TODO: this comment is too rude"""
        if not isinstance(other, PyTealFrame):
            return False

        return all(
            [
                self.frame_info == other.frame_info,
                self.node == other.node,
                self.rel_paths == other.rel_paths,
            ]
        )

    def spawn(
        self, other: "PyTealFrame", status: "SourceMapItemStatus"
    ) -> "PyTealFrame":
        assert isinstance(other, PyTealFrame)

        ptf = PyTealFrame(other.frame(), other.rel_paths, self)
        ptf._status = status

        return ptf

    def location(self) -> str:
        return f"{self.file()}:{self.lineno()}" if self.frame_info else ""

    def file(self) -> str:
        if not self.frame_info:
            return ""

        path = self.frame_info.filename
        return os.path.relpath(path) if self.rel_paths else path

    def code_qualname(self) -> str:
        return (
            Source.executing(self.frame_info.frame).code_qualname()
            if self.frame_info
            else ""
        )

    def lineno(self) -> int | None:
        return self.frame_info.lineno if self.frame_info else None

    def raw_code(self) -> str:
        if self._raw_code is None:
            self._raw_code = (
                ("".join(self.frame_info.code_context)).strip()
                if self.frame_info and self.frame_info.code_context
                else ""
            )

        return self._raw_code

    def compiler_generated(self) -> bool | None:
        """
        None indicates "unknown".

        i.e. `not x.compiler_generated()` === NOT or UNKNOWN
        """
        if not self.raw_code():
            return None  # we don't know / NA

        return "# T2PT" in self.raw_code()

    def compiler_generated_reason(self) -> str | None:
        """
        None indicates either "unkown" or "not compiler generated".
        To distinguish between these two usages, call `compiler_generated()` first.
        """
        if not self.compiler_generated():
            return None

        for k, v in _PT_GEN.items():
            if k in self.raw_code():
                return v

        raise AssertionError(
            "This should never happen as the call to self.compiler_generated() should have prevented this case."
        )

    def code(self) -> str:
        raw = self.raw_code()
        if not self.compiler_generated():
            return raw

        for k, v in _PT_GEN.items():
            if k in raw:
                return f"{v}: {raw}"

        return f"Unhandled # T2PT commentary: {raw}"

    def failed_ast(self) -> bool:
        return not self.node

    def status_code(self) -> SourceMapItemStatus:
        if self._status is not None:
            return self._status

        if self.frame_info is None:
            return SourceMapItemStatus.MISSING

        if self.node is None:
            return SourceMapItemStatus.MISSING_AST

        if self.compiler_generated():
            return SourceMapItemStatus.PYTEAL_GENERATED

        if not self.raw_code():
            return SourceMapItemStatus.MISSING_CODE

        return SourceMapItemStatus.COPACETIC

    def status(self) -> str:
        return self.status_code().human()

    def node_source(self) -> str:
        return unparse(self.node) if self.node else ""

    def node_lineno(self) -> int | None:
        return getattr(self.node, "lineno", None) if self.node else None

    def node_col_offset(self) -> int | None:
        return getattr(self.node, "col_offset", None) if self.node else None

    def node_end_lineno(self) -> int | None:
        return getattr(self.node, "end_lineno", None) if self.node else None

    def node_end_col_offset(self) -> int | None:
        return getattr(self.node, "end_col_offset", None) if self.node else None

    def node_source_window(self) -> str:
        boundaries = (
            self.node_lineno(),
            self.node_col_offset(),
            self.node_end_lineno(),
            self.node_end_col_offset(),
        )
        if not all(b is not None for b in boundaries):
            return ""
        return "L{}:{}-L{}:{}".format(*boundaries)

    def __str__(self, verbose: bool = True) -> str:
        if not self.frame_info:
            return "None"

        spaces = "\n\t\t\t"
        short = f"<{self.code()}>{spaces}@{self.location()}"
        if not verbose:
            return short

        # {self.source=}
        # {self.ast=}
        return f"""{short}
{self.frame_info.index=}
{self.frame_info.function=}
{self.frame_info.frame=}"""

    def __repr__(self) -> str:
        """TODO: this repr isn't compliant. Should we keep it anyway for convenience?"""
        return self.__str__(verbose=False)

    @classmethod
    def convert(
        cls, frames: FrameSequence, rel_paths: bool = True
    ) -> "PyTealFrameSequence":  # type: ignore
        if isinstance(frames, Frame):
            return cls(frames, rel_paths)
        return [cls.convert(f) for f in cast(Sequence[Frame], frames)]


_TL = "TL"
_Teal = "Teal"
_PTE = "PTE"
_PTQ = "PTQ"
_PTC = "PTC"
_PTCW = "PTCW"
_PT_path = "PT path"
_PTL = "PTL"
_PTCC = "PTCC"
_PT_AST = "PT AST"
_PT_frame = "PT frame"
_failed = "FAILED"
_status_code = "Sourcemap Status Code"
_status = "Sourcemap Status"


@dataclass
class SourceMapItem:
    line: int
    teal: str
    component: "pt.TealComponent"
    frame: PyTealFrame
    extras: dict[str, Any] | None = None  # TODO: probly these shouldn't exist

    def asdict(self, **kwargs) -> OrderedDict:
        """kwargs serve as a rename mapping when present
        TODO: is this overly complicated?
        """
        attrs = {
            _TL: self.line,
            _Teal: self.teal,
            _PTE: self.frame.node_source(),
            _PTQ: self.frame.code_qualname(),
            _PTC: self.component,
            _PTCW: self.frame.node_source_window(),
            _PT_path: self.frame.file(),
            _PTL: self.frame.lineno(),
            _PTCC: self.frame.code(),
            _PT_AST: self.frame.node,
            _PT_frame: self.frame,
            _failed: self.frame.failed_ast(),
            _status_code: self.frame.status_code(),
            _status: self.frame.status(),
        }

        assert (
            kwargs.keys() <= attrs.keys()
        ), f"unrecognized parameters {kwargs.keys() - attrs.keys()}"

        return OrderedDict(((kwargs[k], attrs[k]) for k in kwargs))

    def source_mapping(self) -> SourceMapping:
        return SourceMapping(
            line=self.line - 1,
            column=0,
            column_rbound=len(self.teal),
            source=self.frame.node_source(),
            source_line=self.frame.lineno(),
            source_column=self.frame.node_col_offset(),
            source_line_end=self.frame.node_end_lineno(),
            source_column_rbound=self.frame.node_end_col_offset(),
            source_extract=self.frame.code(),
            target_extract=self.teal,
        )


class PyTealSourceMap:
    def __init__(
        self,
        lines: list[str],
        components: list["pt.TealComponent"],
        build: bool = False,
        source_inference: bool = True,
        x: bool = False,
    ):
        # TODO: get rid of x and add_extras ???
        self.teal_lines: list[str] = lines
        self.components: list["pt.TealComponent"] = components
        self.source_inference: bool = source_inference
        self.add_extras: bool = x
        self._cached_source_map: dict[int, SourceMapItem] = {}
        self.inferred_frames_at: list[int] = []

        if build:
            self.get_map()

    def get_map(self) -> dict[int, SourceMapItem]:
        if not self._cached_source_map:
            N = len(self.teal_lines)
            assert N == len(
                self.components
            ), f"expected same number of teal lines {N} and components {len(self.components)}"

            best_frames = []
            before, after = [], []
            for tc in self.components:
                f, a, b = self.best_frame_and_windows_around_it(tc)
                best_frames.append(f)
                before.append(b)
                after.append(a)

            if self.source_inference:
                mutated = self._search_for_better_frames_and_modify(best_frames)
                if mutated:
                    self.inferred_frames_at = mutated

            def source_map_item(i, tc):
                extras: dict[str, Any] | None = None
                if self.add_extras:
                    extras = {
                        "after_frames": after[i],
                        "before_frames": before[i],
                    }
                return SourceMapItem(
                    i + 1, self.teal_lines[i], tc, best_frames[i], extras
                )

            self._cached_source_map = {
                i + 1: source_map_item(i, tc) for i, tc in enumerate(self.components)
            }

        return self._cached_source_map

    def _search_for_better_frames_and_modify(
        self, frames: list[PyTealFrame]
    ) -> list[int]:
        N = len(frames)
        mutated = []

        def infer_source(i: int) -> PyTealFrame | None:
            frame = frames[i]
            prev_frame = None if i <= 0 else frames[i - 1]
            next_frame = None if N <= i + 1 else frames[i + 1]
            if prev_frame and next_frame:
                if prev_frame == next_frame:
                    return frame.spawn(
                        prev_frame, SourceMapItemStatus.PATCHED_BY_PREV_AND_NEXT
                    )

                # PT Generated TypeEnum's presumably happened because of setting an transaction
                # field in the next step:
                reason = frame.compiler_generated_reason()
                if reason in [
                    PT_GENERATED_TYPE_ENUM_ONCOMPLETE,
                    PT_GENERATED_TYPE_ENUM_TXN,
                ]:
                    return frame.spawn(
                        next_frame, SourceMapItemStatus.PATCHED_BY_NEXT_OVERRIDE_PREV
                    )

                # NO-OP otherwise:
                return None

            if prev_frame:
                return frame.spawn(prev_frame, SourceMapItemStatus.PATCHED_BY_PREV)

            if next_frame:
                return frame.spawn(next_frame, SourceMapItemStatus.PATCHED_BY_NEXT)

            return None

        for i in range(N):
            if frames[i].status_code() <= SourceMapItemStatus.PYTEAL_GENERATED:
                ptf_or_none = infer_source(i)
                if ptf_or_none:
                    mutated.append(i)
                    frames[i] = ptf_or_none

        return mutated

    @classmethod
    def best_frame_and_windows_around_it(
        cls, t: "pt.TealComponent"
    ) -> tuple[FrameInfo | None, list[FrameInfo], list[FrameInfo]]:
        """
        # TODO: probly need to REMOVE the extra before and after
        # TODO: this is too complicated!!!
        """

        # TODO: Do I need to resurrect these assertions?
        # def call_out_emptys(xs):
        #     f"The following indices were empty {[x for x in xs if not x]}"

        # frames = cast(List[inspect.FrameInfo], frames)
        # frame_nodes = cast(List[ast.AST | None], frame_nodes)
        # assert all(frame_infos), call_out_emptys(frame_infos)
        # assert len(frame_nodes) == len(frame_infos)

        pyteals = [
            # "pyteal/__init__.py",
            "pyteal/ast",
            "pyteal/compiler",
            "pyteal/ir",
            "pyteal/pragma",
            "tests/abi_roundtrip.py",
            "tests/blackbox.py",
            "tests/compile_asserts.py",
            "tests/mock_version.py",
        ]

        frames = t.frames()
        frame_infos = frames.frame_infos()
        pyteal_idx = [any(w in f.filename for w in pyteals) for f in frame_infos]

        def is_code_file(idx):
            f = frame_infos[idx].filename
            return not (f.startswith("<") and f.endswith(">"))

        in_pt, first_pt_entrancy = False, None
        for i, is_pyteal in enumerate(pyteal_idx):
            if is_pyteal and not in_pt:
                in_pt = True
                continue
            if not is_pyteal and in_pt and is_code_file(i):
                first_pt_entrancy = i
                break

        if first_pt_entrancy is None:
            return None, [], []

        frame_nodes = frames.nodes()
        if frame_nodes[first_pt_entrancy] is None:
            # FAILURE CASE: Look for first pyteal generated code entry in stack trace:
            found = False
            i = -1
            for i in range(len(frame_infos) - 1, -1, -1):
                f = frame_infos[i]
                if not f.code_context:
                    continue

                cc = "".join(f.code_context)
                if "# T2PT" in cc:
                    found = True
                    break

            if found and i >= 0:
                first_pt_entrancy = i

        # TODO: probly don't need to keep `extras` param of SourceMapItem
        # nor the 2nd and 3rd elements of the following tuple being returned
        return tuple(
            PyTealFrame.convert(
                [
                    frames[first_pt_entrancy],  # type: ignore
                    [frames[i] for i in range(first_pt_entrancy - 1, -1, -1)],
                    [frames[i] for i in range(first_pt_entrancy + 1, len(frame_infos))],
                ]
            )
        )

    def teal(self) -> str:
        return "\n".join(smi.teal for smi in self.get_map().values())

    def tabulate(
        self,
        *,
        tablefmt="fancy_grid",
        **kwargs,
    ) -> str:
        defaults = dict(
            teal_line_col=_TL,
            teal_code_col=_Teal,
            pyteal_exec_col=_PTE,
            pyteal_qualname_col=_PTQ,
            pyteal_component_col=_PTC,
            pyteal_code_window=_PTCW,
            pyteal_path_col=_PT_path,
            pyteal_line_col=_PTL,
            pyteal_code_context_col=_PTCC,
            pyteal_ast_col=_PT_AST,
            linemap_failed=_failed,
            linemap_status_code=_status_code,
            linemap_status=_status,
        )
        for k in kwargs:
            assert k in defaults, f"unrecognized parameter '{k}'"

        required = ["teal_line_col", "teal_code_col", "pyteal_exec_col"]
        renames = {defaults[k]: v for k, v in kwargs.items()}
        for r in required:
            if r not in kwargs:
                renames[defaults[r]] = defaults[r]

        rows = (item.asdict(**renames) for item in self.get_map().values())
        return tabulate(rows, headers=renames, tablefmt=tablefmt)