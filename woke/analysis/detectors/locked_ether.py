from collections import defaultdict, deque
from typing import DefaultDict, List, Set, Tuple

from woke.analysis.cfg import CfgBlock
from woke.analysis.detectors import DetectorAbc, DetectorResult, detector
from woke.ast.enums import ContractKind, GlobalSymbolsEnum, StateMutability
from woke.ast.ir.declaration.contract_definition import ContractDefinition
from woke.ast.ir.declaration.function_definition import FunctionDefinition
from woke.ast.ir.expression.function_call import FunctionCall
from woke.ast.ir.expression.function_call_options import FunctionCallOptions
from woke.ast.ir.expression.member_access import MemberAccess
from woke.ast.ir.statement.expression_statement import ExpressionStatement
from woke.ast.ir.statement.revert_statement import RevertStatement


@detector(-1009, "locked-ether")
class LockedEtherDetector(DetectorAbc):
    _receiving_ether: Set[FunctionDefinition]
    _sending_ether: Set[FunctionDefinition]

    def __init__(self):
        self._receiving_ether = set()
        self._sending_ether = set()

    @staticmethod
    def _process_child_contracts(
        fn: FunctionDefinition,
        contracts: DefaultDict[ContractDefinition, Set[FunctionDefinition]],
    ) -> None:
        parent = fn.parent
        if not isinstance(parent, ContractDefinition):
            return

        queue = deque([parent])
        visited = {parent}
        while len(queue) > 0:
            contract = queue.popleft()

            if contract.abstract or contract.kind in {
                ContractKind.INTERFACE,
                ContractKind.LIBRARY,
            }:
                continue

            if len(contract.functions) > 0 and any(
                fn in f.base_functions for f in contract.functions
            ):
                continue

            contracts[contract].add(fn)

            for child in contract.child_contracts:
                if child not in visited:
                    visited.add(child)
                    queue.append(child)

    def report(self) -> List[DetectorResult]:
        receiving_contracts: DefaultDict[
            ContractDefinition, Set[FunctionDefinition]
        ] = defaultdict(set)
        sending_contracts: DefaultDict[
            ContractDefinition, Set[FunctionDefinition]
        ] = defaultdict(set)

        # TODO free function sending ether
        # TODO internal unused function sending ether

        for func in self._receiving_ether:
            self._process_child_contracts(func, receiving_contracts)

        for func in self._sending_ether:
            self._process_child_contracts(func, sending_contracts)

        ret = []

        for contract in receiving_contracts.keys() - sending_contracts.keys():
            ret.append(
                DetectorResult(
                    contract,
                    "Contract receives ether but does not send ether",
                    tuple(
                        DetectorResult(f, "Receives ether here")
                        for f in receiving_contracts[contract]
                    ),
                )
            )

        for contract in sending_contracts.keys() - receiving_contracts.keys():
            ret.append(
                DetectorResult(
                    contract,
                    "Contract sends ether but does not receive ether (except for selfdestruct)",
                    tuple(
                        DetectorResult(f, "Sends ether here")
                        for f in sending_contracts[contract]
                    ),
                )
            )

        return ret

    def visit_function_definition(self, node: FunctionDefinition):
        if node.state_mutability != StateMutability.PAYABLE or not node.implemented:
            return

        cfg = node.cfg
        assert cfg is not None

        graph = cfg.graph
        queue = deque([cfg.end_block])
        while len(queue) > 0:
            block: CfgBlock = queue.popleft()

            reverts = False
            for stmt in block.statements:
                if isinstance(stmt, RevertStatement):
                    reverts = True
                    break
                elif isinstance(stmt, ExpressionStatement):
                    if (
                        isinstance(stmt.expression, FunctionCall)
                        and stmt.expression.function_called == GlobalSymbolsEnum.REVERT
                    ):
                        reverts = True
                        break

            if reverts:
                continue

            for from_, _ in graph.in_edges(block):
                if from_ == cfg.start_block:
                    self._receiving_ether.add(node)
                    return
                else:
                    queue.append(from_)

    def visit_member_access(self, node: MemberAccess):
        if node.referenced_declaration not in {
            GlobalSymbolsEnum.ADDRESS_SEND,
            GlobalSymbolsEnum.ADDRESS_TRANSFER,
            GlobalSymbolsEnum.FUNCTION_VALUE,
        }:
            return

        func = node
        while func is not None:
            if isinstance(func, FunctionDefinition):
                break
            func = func.parent

        if func is None:
            return

        self._sending_ether.add(func)

    def visit_function_call_options(self, node: FunctionCallOptions):
        if not isinstance(node.parent, FunctionCall) or "value" not in node.names:
            return

        func = node
        while func is not None:
            if isinstance(func, FunctionDefinition):
                break
            func = func.parent

        if func is None:
            return

        self._sending_ether.add(func)
