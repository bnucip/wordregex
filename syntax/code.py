import sys
from dataclasses import dataclass, replace
from typing import List, Text, Dict, Any, Union
from enum import IntEnum
from .tree import (
    PositionNodeType,
    ConcatenateNode,
    AlternateNode,  # |
    RepeatNode,  # *?+{m,n}
    CaptureNode,  # ()(?<name>)
    ConditionNode,  # (?=)(?!)(?<=)(?<!)
    # leaf node
    AnyNode,  # .
    PositionNode,  # ^$
    RefNode,  # \n \p<name>
    EmptyNode,
    WordNode,
    WordSetNode,
    DynamicWordNode,
    DynamicWordSetNode,
    SthNode,
)


class CodeType(IntEnum):
    Alt = 1  # save textpos,trackpos
    Goto = 2

    SetMark = 3
    CaptureMark = 4

    SetJump = 7
    GetJump = 8
    ForeJump = 9  # 结束当前alt分支
    BackJump = 10  # 结束当前所有alt分支，回溯trackpos

    Stop = 49

    # leaf node
    Any = 50
    Position = 51
    Ref = 52

    Word = 53
    WordSet = 54
    DynamicWord = 55
    DynamicWordSet = 56

    Back = 99
    Nop = 100


class PositionType(IntEnum):
    BeginLine = PositionNodeType.BeginLine
    EndLine = PositionNodeType.EndLine


CodeNames = {
    CodeType.Alt: "Alt",
    CodeType.Goto: "Goto",
    CodeType.SetMark: "SetMark",
    CodeType.CaptureMark: "CaptureMark",
    # 打上跳转标记
    CodeType.SetJump: "SetJump",
    CodeType.GetJump: "GetJump",
    # 恢复至最近的SetJump指令的状态，执行下条语句
    CodeType.ForeJump: "ForeJump",
    # 恢复至最近的SetJump指令标记的状态，进入回溯
    CodeType.BackJump: "BackJump",
    CodeType.Stop: "Stop",
    # leaf node
    CodeType.Any: "Any",
    CodeType.Position: "Position",
    CodeType.Ref: "Ref",
    CodeType.Back: "Back",
    CodeType.Nop: "Nop",
    CodeType.Word: "Word",
    CodeType.WordSet: "WordSet",
    CodeType.DynamicWord: "DynamicWord",
    CodeType.DynamicWordSet: "DynamicWordSet",
}


@dataclass
class Code:
    id: int = -1
    t: CodeType = -1
    arg: List[int] = None
    params: Dict[Text, Any] = None
    wordn: Union[WordNode, WordSetNode, DynamicWordNode, DynamicWordSetNode] = None
    RightToLeft: bool = False

    def copy(self) -> "Code":
        return replace(self)


def dump_codes(codelst):
    res_str = ""
    back_code_type = [
        CodeType.Alt,
        CodeType.SetMark,
        CodeType.CaptureMark,
        CodeType.SetJump,
        CodeType.ForeJump,
    ]
    for _code in codelst:
        codemark = "*" if _code.t in back_code_type else " "
        if CodeNames.get(_code.t) is not None:
            res_str += f"{_code.id} {codemark}{CodeNames.get(_code.t)}"
            if _code.RightToLeft:
                res_str += "\t-Rtl"
            if _code.t in [
                CodeType.Word,
                CodeType.WordSet,
                CodeType.DynamicWord,
                CodeType.DynamicWordSet,
            ]:
                if _code.t == CodeType.Word:
                    res_str += "\t" + f'"{_code.wordn.shape}"'
                if _code.t == CodeType.WordSet:
                    word_list = [w.shape for w in _code.wordn.word_list]
                    res_str += "\t" + "[" + ",".join(word_list) + "]"
                if _code.t == CodeType.DynamicWord:
                    res_str += "\t" + f'"{_code.wordn.pos}"'
                if _code.t == CodeType.DynamicWordSet:
                    word_list = [str(w) for w in _code.wordn.word_list]
                    res_str += "\t" + "[" + ",".join(word_list) + "]"
            if _code.params is not None:
                res_str += f"\t{_code.params}"
            res_str += f" -> {_code.arg}\n"
        else:
            print("dumpcode error\n")
    return res_str


@dataclass
class TreeParser:
    codestack: List[Code] = None
    paramStack: List[Any] = None
    auto_codeid: int = -1
    groupsInfo: Dict[int, Text] = None

    def printCodes(self):
        print(dump_codes(self.codestack))

    def Init_state(self):
        self.codestack = []
        self.paramStack = []
        self.auto_codeid = -1
        self.groupsInfo = {}
        return self

    # curIndex既表示下一个要遍历的子树索引，又表示第几次遍历node
    # curIndex=0表示下一个要遍历node的第一个子孩子，同时表示第一次遍历到node
    # emit(node)用于生成node对应的指令，curIndex表示下一次指令会生成curIndex子节点的指令

    # emit(node,0)表示第一次遍历node
    # emit(node,len(node.subs))表示遍历完所有node的子节点
    def emit(self, node, curIndex) -> bool:
        # ConcatenateNode将所有的子节点前后拼接
        if isinstance(node, ConcatenateNode):
            return True

        # 分支选择
        elif isinstance(node, AlternateNode):
            if curIndex == 0:
                alt_pos = len(self.codestack)
                self.auto_codeid += 1
                alt_id = self.auto_codeid
                self.codestack.append(Code(t=CodeType.Alt, arg=[alt_id + 1], id=alt_id))
                self.paramStack.append(alt_pos)
                return True
            elif 0 < curIndex < len(node.subs):
                self.paramStack.append(len(self.codestack) - 1)
                return True
            else:  # 遍历结束
                code_ends = self.paramStack[-len(node.subs) + 1 :]
                self.paramStack = self.paramStack[: -len(node.subs) + 1]
                alt_pos = self.paramStack.pop()
                for pos in code_ends:
                    self.codestack[pos].arg = [self.auto_codeid + 1]
                    self.codestack[alt_pos].arg.append(self.codestack[pos + 1].id)
                self.codestack[-1].arg = [self.auto_codeid + 1]
                return True
        # 量词限定
        elif isinstance(node, RepeatNode):
            if curIndex == 0:
                m = node.min
                n = node.max
                is_nongreedy = node.is_nongreedy
                self.paramStack.append([m, n, is_nongreedy])
                self.paramStack.append(len(self.codestack))
                return True
            else:
                INTMAX = sys.maxsize
                pos = self.paramStack.pop()
                unit = self.codestack[pos:]
                self.codestack = self.codestack[:pos]
                m, n, is_nongreedy = self.paramStack.pop()
                if m == 0 and n == INTMAX:  # star
                    alt_pos = len(self.codestack)
                    self.auto_codeid += 1
                    alt_id = self.auto_codeid
                    self.codestack[-1].arg = [alt_id]
                    self.codestack.append(
                        Code(t=CodeType.Alt, arg=[unit[0].id], id=self.auto_codeid)
                    )
                    self.codestack += unit
                    unit[-1].arg = [alt_id]
                    self.codestack[alt_pos].arg.append(self.auto_codeid + 1)  # 跳出循环
                    if is_nongreedy:
                        self.codestack[alt_pos].arg.reverse()
                    return True
                elif m == 1 and n == INTMAX:  # plus
                    unit_begin = unit[0].id
                    self.codestack[-1].arg = [unit_begin]
                    self.codestack += unit
                    alt_pos = len(self.codestack)
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(
                            t=CodeType.Alt,
                            arg=[unit_begin, self.auto_codeid + 1],
                            id=self.auto_codeid,
                        )
                    )
                    if is_nongreedy:
                        self.codestack[alt_pos].arg.reverse()
                    return True
                elif m == 0 and n == 1:  # quest
                    alt_pos = len(self.codestack)
                    self.auto_codeid += 1
                    alt_id = self.auto_codeid
                    self.codestack[-1].arg = [alt_id]
                    self.codestack.append(
                        Code(t=CodeType.Alt, arg=[unit[0].id, alt_id + 1], id=alt_id)
                    )
                    self.codestack += unit
                    unit[-1].arg = [self.auto_codeid + 1]
                    if is_nongreedy:
                        self.codestack[alt_pos].arg.reverse()
                    return True
                elif 1000 > n >= m >= 1:
                    unit_len = len(unit)
                    for j in range(m):
                        new_unit = [code.copy() for code in unit]
                        for i in range(unit_len):
                            new_unit[i].id += j * len(unit)
                        self.codestack[-1].arg = [new_unit[0].id]
                        self.codestack += new_unit
                    self.auto_codeid = self.codestack[-1].id
                    self.codestack[-1].arg = [self.auto_codeid + 1]
                    if n > m:
                        altpos = len(self.codestack)
                        self.auto_codeid += 1
                        self.codestack.append(
                            Code(
                                t=CodeType.Alt,
                                arg=[self.auto_codeid + 1],
                                id=self.auto_codeid,
                            )
                        )
                        for j in range(n - m):
                            new_unit = [code.copy() for code in unit]
                            for i in range(len(new_unit)):
                                self.auto_codeid += 1
                                new_unit[i].id = self.auto_codeid
                            self.codestack += new_unit
                            self.codestack[-1].arg = [self.auto_codeid + 1]
                            self.codestack[altpos].arg.append(self.auto_codeid + 1)
                        if is_nongreedy:
                            self.codestack[altpos].arg.reverse()
                    return True
                else:
                    return False
        # 结果捕获
        elif isinstance(node, CaptureNode):
            if curIndex == 0:
                self.auto_codeid += 1
                self.codestack.append(
                    Code(
                        t=CodeType.SetMark,
                        arg=[self.auto_codeid + 1],
                        id=self.auto_codeid,
                    )
                )
            else:
                self.auto_codeid += 1
                name = node.name
                cap_index = node.index
                if name == "":
                    name = f"<{cap_index}>"
                self.groupsInfo[cap_index] = name
                self.codestack.append(
                    Code(
                        t=CodeType.CaptureMark,
                        arg=[self.auto_codeid + 1],
                        params={"name": name, "cap_id": cap_index},
                        id=self.auto_codeid,
                    )
                )
            return True
        # 零宽断言
        elif isinstance(node, ConditionNode):
            if curIndex == 0:
                self.paramStack.append(len(self.codestack))
                return True
            else:
                pos = self.paramStack.pop()
                test_code = self.codestack[pos:]
                self.codestack = self.codestack[:pos]
                is_positive = node.is_positive

                if is_positive:
                    if len(self.codestack) > 0:
                        self.codestack[-1].arg = [self.auto_codeid + 1]
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(
                            t=CodeType.SetJump,
                            id=self.auto_codeid,
                            arg=[test_code[0].id],
                        )
                    )
                    self.codestack += test_code
                    self.codestack[-1].arg = [self.auto_codeid + 1]
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(
                            t=CodeType.ForeJump,
                            id=self.auto_codeid,
                            arg=[self.auto_codeid + 1],
                        )
                    )

                elif not is_positive:
                    if len(self.codestack) > 0:
                        self.codestack[-1].arg = [self.auto_codeid + 1]
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(
                            t=CodeType.SetJump,
                            id=self.auto_codeid,
                            arg=[self.auto_codeid + 1],
                        )
                    )
                    alt_pos = len(self.codestack)
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(t=CodeType.Alt, arg=[test_code[0].id], id=self.auto_codeid)
                    )
                    self.codestack += test_code
                    self.codestack[-1].arg = [self.auto_codeid + 1]
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(t=CodeType.BackJump, id=self.auto_codeid, arg=[])
                    )
                    self.auto_codeid += 1
                    self.codestack.append(
                        Code(
                            t=CodeType.ForeJump,
                            id=self.auto_codeid,
                            arg=[self.auto_codeid + 1],
                        )
                    )
                    self.codestack[alt_pos].arg.append(self.auto_codeid)
                return True
        # leaf node
        elif isinstance(node, AnyNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.Any,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, PositionNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.Position,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    params={"position_type": node.tt},
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, RefNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.Ref,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    params={"ref_id": node.index, "isReversed": node.isReversed},
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, EmptyNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.Nop,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, WordNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.Word,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    wordn=node,
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, WordSetNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.WordSet,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    wordn=node,
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, DynamicWordNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.DynamicWord,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    wordn=node,
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, DynamicWordSetNode):
            self.auto_codeid += 1
            self.codestack.append(
                Code(
                    t=CodeType.DynamicWordSet,
                    id=self.auto_codeid,
                    arg=[self.auto_codeid + 1],
                    wordn=node,
                    RightToLeft=node.RightToLeft,
                )
            )
            return True

        elif isinstance(node, SthNode):
            print(f'SthNode "{node.name}" is not expand')
            return False

        return False

    def ScanTree(self, t):
        self.auto_codeid += 1
        # 用于跳转至结尾的Stop指令，表示匹配失败
        # 0号Alt指令为开始指令
        self.codestack.append(
            Code(t=CodeType.Alt, arg=[self.auto_codeid + 1], id=self.auto_codeid)
        )

        # 生成指令主体
        int_stack = []  # 维护子树的遍历路径
        curNode = t
        curChild = 0
        while True:
            if hasattr(curNode, "sub") and curChild < 1:  # 只有一个子节点
                ok = self.emit(curNode, 0)  # 生成该节点对应的指令
                if not ok:
                    return False
                curNode = curNode.sub  # 深度优先遍历
                int_stack.append(0)  # 维护树的遍历路径：保存路径中子树的索引
                continue

            elif hasattr(curNode, "subs") and curChild < len(
                curNode.subs
            ):  # 有多个子节点
                ok = self.emit(curNode, curChild)
                if not ok:
                    return False
                curNode = curNode.subs[curChild]
                int_stack.append(curChild)
                curChild = 0
                continue

            # 叶节点生成指令，开始回溯
            elif not (hasattr(curNode, "subs") or hasattr(curNode, "sub")):
                ok = self.emit(curNode, 0)
                if not ok:
                    return False
            # 回溯部分

            if len(int_stack) == 0:  # 遍历路径为空，即遍历完所有子树
                break

            # 叶节点回溯
            curChild = int_stack.pop()
            curNode = curNode.fa  # 回到父节点
            curChild += 1

            # 遍历完成所有子节点，执行一次emit表示所有子节点完成，生成结尾指令
            if hasattr(curNode, "subs") and curChild == len(curNode.subs):
                ok = self.emit(curNode, curChild)
                if not ok:
                    return False
            elif hasattr(curNode, "sub") and curChild == 1:
                ok = self.emit(curNode, 1)
                if not ok:
                    return False

        # 生成匹配终止指令，包裹主体指令
        # Stop为终止指令
        self.auto_codeid += 1
        self.codestack[0].arg.append(self.auto_codeid)
        self.codestack.append(Code(t=CodeType.Stop, arg=[], id=self.auto_codeid))
        return True

    def groups_info(self):
        return self.groupsInfo

    def Codes(self):
        return self.codestack


def tree_to_code(root):
    tp = TreeParser().Init_state()
    ok = tp.ScanTree(root)
    codes = tp.Codes()
    codes.sort(key=lambda x: x.id)
    if not ok:
        return None, False
    return codes, tp.groups_info(), ok
