from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from woke.ast.enums import ModifiesStateFlag
from woke.ast.ir.abc import SolidityAbc
from woke.ast.ir.statement.abc import StatementAbc
from woke.ast.ir.utils import IrInitTuple
from woke.ast.nodes import SolcBreak

if TYPE_CHECKING:
    from .block import Block
    from .do_while_statement import DoWhileStatement
    from .for_statement import ForStatement
    from .if_statement import IfStatement
    from .unchecked_block import UncheckedBlock
    from .while_statement import WhileStatement


class Break(StatementAbc):
    _ast_node: SolcBreak
    _parent: Union[
        Block,
        DoWhileStatement,
        ForStatement,
        IfStatement,
        UncheckedBlock,
        WhileStatement,
    ]

    __documentation: Optional[str]

    def __init__(self, init: IrInitTuple, break_: SolcBreak, parent: SolidityAbc):
        super().__init__(init, break_, parent)
        self.__documentation = break_.documentation

    @property
    def parent(
        self,
    ) -> Union[
        Block,
        DoWhileStatement,
        ForStatement,
        IfStatement,
        UncheckedBlock,
        WhileStatement,
    ]:
        return self._parent

    @property
    def documentation(self) -> Optional[str]:
        return self.__documentation

    @property
    def modifies_state(self) -> ModifiesStateFlag:
        return ModifiesStateFlag(0)
