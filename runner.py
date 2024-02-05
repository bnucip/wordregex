from dataclasses import dataclass, fields
from syntax.code import Code, CodeType, PositionType, CodeNames
from syntax.tree import WordNode, DynamicWordNode, WordSetNode, DynamicWordSetNode
from typing import (
    List,
    Any,
    Text,
    Dict,
    Tuple,
)


# 匹配规则
def is_dynamic_word_match(node, word, DEBUG=False):
    if node.pos2 != "":
        pos2 = node.pos + node.pos2
        w_pos2 = word.get("pos2", "")
        if w_pos2.find(pos2) == -1:
            if DEBUG:
                print(f"{str(node)} and {word} not match pos2 ")
            return False
    if node.pos != "" and node.pos not in word.get("pos", ""):
        if DEBUG:
            print(f"{str(node)} and {word}  not match pos")
        return False
    if node.length != -1 and node.length != len(word.get("shape", "")):
        if DEBUG:
            print(f"{str(node)} and {word}  not match shape length")
        return False
    if node.word_struct != "" and node.word_struct != word.get("struct", ""):
        if DEBUG:
            print(f"{str(node)} and {word}  not match word struct")
        return False
    # 语义类匹配
    if node.semantic_tag != "" and node.semantic_tag in word.get("semantic", ""):
        if DEBUG:
            print(f"{str(node)} and {word}  not match tag")
        return False
    return True


@dataclass(repr=False)
class Runner:
    codes: List[Code] = None
    inputLst: List[Any] = None
    codePos: int = -1  # 按id执行
    wordStart: int = -1
    wordEnd: int = -1
    wordPos: int = -1
    # 指令对传递信息
    paramStack: List[Dict[Text, Any]] = None
    # 记录回溯状态
    trackStack: List[Tuple[int, int, List[Any]]] = None  # codepos,back_time,list[any]
    matches: Dict[int, List[int]] = None
    matchesInfo: Dict[int, Text] = None

    def goto(self, codepos):
        self.codePos = codepos

    def word_to(self, wordpos):
        self.wordPos = wordpos

    def get_word(self, wordpos_):
        return self.inputLst[wordpos_]

    def track_to(self, trackpos):
        self.trackStack = self.trackStack[:trackpos]

    def track_push(self, back_time, param_lst):
        self.trackStack.append((self.codePos, back_time, param_lst))

    def track_pop(self):
        return self.trackStack.pop()

    def track_empty(self) -> bool:
        return len(self.trackStack) == 0

    def param_push(self, item: Dict[Text, Any]):
        self.paramStack.append(item)

    def param_pop(self):
        return self.paramStack.pop()

    def param_peek(self, i):
        return self.paramStack[len(self.paramStack) - i - 1]

    def execute(self, DEBUG=False) -> bool:
        self.goto(0)
        while True:
            if self.codePos >= len(self.codes) or self.codePos < 0:
                return False
            code = self.codes[self.codePos]
            if DEBUG:
                print(
                    f"code_type:{CodeNames[code.t]} ",
                    f"wordpos:{self.wordPos} ",
                    f"word:{self.get_word(self.wordPos)}",
                )
                print("trackStack(codepos,back_time,track_param):", self.trackStack)
                print("paramStack:", self.paramStack)
                print("------------")
            if code.t == CodeType.Stop:
                return True  # 匹配成功，存在以位置0开头的符合正则表达式的子串

            elif code.t == CodeType.Nop:
                self.goto(code.arg[0])  # 匹配空字符（词）
                continue

            elif code.t == CodeType.Alt:  # backtrace code
                # 首次执行回溯指令保存状态
                # trackpos,wordpos
                self.track_push(0, [self.wordPos])  # 保存指令状态， 以便回溯返回
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.SetMark:  # backtrace code
                self.param_push(
                    {"codeid": code.id, "wordpos": self.wordPos}
                )  # 把信息传给CaptureMark
                self.track_push(0, [])  # 回溯时不需要恢复textpos
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.CaptureMark:  # backtrace code
                cap_id = code.params["cap_id"]
                # cap_name = code.params['name']
                # 弹出Setmark的数据，因为
                # SetMark SetMark [...] CaptureMark CaptureMark嵌套需要内部数据清除
                # 为保证paramStack在回溯时变为原有数据，需要将param放入trackStack
                param = self.param_pop()
                cap_startpos = param.get("wordpos")
                cap_stoppos = self.wordPos

                self.matches[cap_id] = [cap_startpos, cap_stoppos]
                # self.matchesInfo[cap_id] = cap_name
                # 进入回溯，记录捕获信息
                self.track_push(0, [cap_id, param])
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.SetJump:  # backtrace code
                param_len = len(self.paramStack)
                track_len = len(self.trackStack)

                word_pos = self.wordPos
                self.param_push(
                    {
                        "codeid": code.id,
                        "paramStackLength": param_len,
                        "trackStackLength": track_len,
                        "wordpos": word_pos,
                    }
                )
                self.track_push(0, [])
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.GetJump:
                param = self.param_pop()
                param_len = param.get("paramStackLength")
                track_len = param.get("trackStackLength")
                word_pos = param.get("wordpos")
                self.paramStack = self.paramStack[:param_len]
                self.trackStack = self.trackStack[:track_len]
                self.wordPos = word_pos

                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.ForeJump:  # backtrace code
                param = self.param_pop()
                param_len = param.get("paramStackLength")
                track_len = param.get("trackStackLength")
                word_pos = param.get("wordpos")
                self.paramStack = self.paramStack[:param_len]
                self.trackStack = self.trackStack[:track_len]
                self.wordPos = word_pos
                # 存储param，回溯时恢复Setjump状态
                self.track_push(0, [param])
                # 进入下一条指令
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.BackJump:
                param = self.param_pop()
                param_len = param.get("paramStackLength")
                track_len = param.get("trackStackLength")
                word_pos = param.get("wordpos")
                self.paramStack = self.paramStack[:param_len]
                self.trackStack = self.trackStack[:track_len]
                self.wordPos = word_pos

                self.backtrack()
                continue

            # leaf code
            # 要求Word有词的词形构成且词之间连接在一起
            elif code.t == CodeType.Word:  # 一个Word指令可能与多个字典输入匹配
                ok = True
                old_pos = self.wordPos
                if code.RightToLeft:
                    if self.wordPos <= 0:
                        self.backtrack()
                        continue
                    # shape有多个字符
                    # s为单个字符
                    code_shape = code.wordn.shape
                    while code_shape != "" and self.wordPos > 0:
                        self.wordPos -= 1
                        word = self.get_word(self.wordPos)
                        word_shape = word.get("shape", "")
                        if word_shape == "" or not code_shape.startswith(word_shape):
                            ok = False
                            break
                        # 减去前缀
                        code_shape = code_shape[len(word_shape) :]

                else:
                    if self.wordPos >= self.wordEnd:
                        self.backtrack()
                        continue

                    # shape有多个字符
                    # s为单个字符
                    code_shape = code.wordn.shape
                    while code_shape != "" and self.wordPos < self.wordEnd:
                        word = self.get_word(self.wordPos)
                        self.wordPos += 1
                        word_shape = word.get("shape", "")
                        if word_shape == "" or not code_shape.startswith(word_shape):
                            ok = False
                            break
                        # 减去前缀
                        code_shape = code_shape[len(word_shape) :]

                if not ok:
                    self.wordPos = old_pos
                    self.backtrack()
                    continue
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.WordSet:
                ok = False
                old_pos = self.wordPos

                if code.RightToLeft:
                    if self.wordPos <= 0:
                        self.backtrack()
                        continue
                    for wn in code.wordn.word_list:
                        ok2 = True
                        pos = self.wordPos

                        code_shape = wn.shape
                        while code_shape != "":
                            pos -= 1
                            word = self.get_word(pos)
                            word_shape = word.get("shape", "")
                            if word_shape == "" or not code_shape.startswith(
                                word_shape
                            ):
                                ok2 = False
                                break
                            # 减去前缀
                            code_shape = code_shape[len(word_shape) :]
                        if ok2:
                            self.wordPos = pos
                            ok = True
                            break
                else:
                    if self.wordPos >= self.wordEnd:
                        self.backtrack()
                        continue

                    for wn in code.wordn.word_list:
                        ok2 = True
                        pos = self.wordPos

                        code_shape = wn.shape
                        while code_shape != "":
                            word = self.get_word(pos)
                            pos += 1
                            word_shape = word.get("shape", "")

                            if word_shape == "" or not code_shape.startswith(
                                word_shape
                            ):
                                ok2 = False
                                break
                            # 减去前缀
                            code_shape = code_shape[len(word_shape) :]
                        if ok2:
                            self.wordPos = pos
                            ok = True
                            break

                if not ok:
                    self.wordPos = old_pos
                    self.backtrack()
                    continue

                self.goto(code.arg[0])
                continue
            # a
            elif code.t == CodeType.DynamicWord:
                old_pos = self.wordPos
                if code.RightToLeft:
                    if self.wordPos <= 0:
                        self.backtrack()
                        continue
                    self.wordPos -= 1
                    word = self.get_word(self.wordPos)
                    ok = is_dynamic_word_match(code.wordn, word, DEBUG)
                else:
                    if self.wordPos >= self.wordEnd:
                        self.backtrack()
                        continue
                    word = self.get_word(self.wordPos)
                    self.wordPos += 1
                    ok = is_dynamic_word_match(code.wordn, word, DEBUG)

                if not ok:
                    self.wordPos = old_pos
                    self.backtrack()
                    continue
                self.goto(code.arg[0])
                continue
            # [a①1c①]
            elif code.t == CodeType.DynamicWordSet:
                ok = False
                old_pos = self.wordPos

                if code.RightToLeft:
                    if self.wordPos <= 0:
                        self.backtrack()
                        continue
                    self.wordPos -= 1
                    word = self.get_word(self.wordPos)
                    word_list: List[DynamicWordNode] = code.wordn.word_list
                    for wn in word_list:
                        if is_dynamic_word_match(wn, word, DEBUG):
                            ok = True
                            break
                else:
                    if self.wordPos >= self.wordEnd:
                        self.backtrack()
                        continue

                    word = self.get_word(self.wordPos)
                    self.wordPos += 1
                    word_list: List[DynamicWordNode] = code.wordn.word_list
                    for wn in word_list:
                        if is_dynamic_word_match(wn, word, DEBUG):
                            ok = True
                            break

                if not ok:
                    self.wordPos = old_pos
                    self.backtrack()
                    continue
                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.Any:
                if code.RightToLeft:
                    if self.wordPos <= 0:
                        self.backtrack()
                        continue
                    self.wordPos -= 1

                else:
                    if self.wordPos >= self.wordEnd:
                        self.backtrack()
                        continue
                    self.wordPos += 1

                self.goto(code.arg[0])
                continue

            elif code.t == CodeType.Position:
                if self.wordPos > self.wordEnd:
                    self.backtrack()
                    continue
                p_t = code.params.get("position_type")
                if p_t == PositionType.BeginLine:
                    if self.wordPos == self.wordEnd:
                        self.backtrack()
                        continue
                    if (
                        self.wordPos == 0
                        or self.get_word(self.wordPos - 1).get("cixing", "") == "\n"
                    ):
                        self.goto(code.arg[0])
                        continue
                    else:
                        self.backtrack()
                        continue
                elif p_t == PositionType.EndLine:
                    if (
                        self.wordPos == self.wordEnd
                        or self.get_word(self.wordPos).get("cixing", "") == "\n"
                    ):
                        self.goto(code.arg[0])
                        continue
                    else:
                        self.backtrack()
                        continue
                else:
                    break

            elif code.t == CodeType.Ref:
                ref_id = code.params.get("ref_id")
                isRevered = code.params.get("isReversed")
                m_start, m_end = self.matches[ref_id]  # 获得匹配结果
                l = m_end - m_start
                if not code.RightToLeft:
                    if l > self.wordEnd - self.wordPos:
                        self.backtrack()
                        continue
                    pos = self.wordPos
                else:
                    if l > self.wordPos - 0:
                        self.backtrack()
                        continue
                    pos = self.wordPos - (m_end - m_start)

                ok = True
                step_ = 1
                if isRevered:
                    step_ = -1
                    m_start, m_end = m_end - 1, m_start - 1
                for m_i in range(m_start, m_end, step_):
                    old_w = self.get_word(m_i)  # 来源于匹配串
                    new_w = self.get_word(pos)
                    pos += 1

                    if old_w != new_w:  # 判断字典内容是否相同
                        ok = False
                        break

                if not ok:
                    self.backtrack()
                    continue

                self.wordPos = pos
                self.goto(code.arg[0])
                continue

        return False

    def backtrack(self):  # codepos会变，wordpos不一定
        while not self.track_empty():
            codepos, back_time, codeparams = self.track_pop()
            back_time += 1
            code = self.codes[codepos]
            self.goto(codepos)
            if code.t == CodeType.Alt:
                (wordpos,) = codeparams  # 恢复匹配串位置
                self.word_to(wordpos)
                if back_time >= len(code.arg):
                    continue
                else:
                    self.track_push(back_time, [wordpos])
                    self.goto(code.arg[back_time])
                    break
            # 以下指令加入回溯的主要目的是为了恢复paramStack状态
            elif code.t == CodeType.SetMark:
                self.param_pop()  # 清空指令状态记录
                continue  # 匹配失败，继续回溯

            elif code.t == CodeType.CaptureMark:
                cap_id, param = codeparams
                self.param_push(param)  # 恢复至setmark的param和track状态
                if self.matches.get(cap_id):
                    del self.matches[cap_id]
                continue  # 匹配失败，继续回溯

            elif code.t == CodeType.SetJump:
                self.param_pop()
                continue  # 匹配失败，继续回溯

            elif code.t == CodeType.ForeJump:
                (param,) = codeparams
                self.param_push(param)  # 恢复至刚执行至setjump时的状态
                continue  # 匹配失败，继续回溯

    # 从wordstart位置的字符开始匹配
    def init_state(self, input_lst, wordstart):
        self.wordStart = wordstart
        self.wordEnd = len(input_lst)
        self.paramStack = []
        self.trackStack = []
        self.wordPos = self.wordStart
        self.matches = {}
        self.inputLst = input_lst

    def run(self, input_lst: list, wordstart, DEBUG=False):
        self.init_state(input_lst, wordstart)
        ok = self.execute(DEBUG)
        if not ok or len(self.matches.keys()) == 0:
            return None
        res = {}
        for ind, group_name in self.matchesInfo.items():
            res[group_name] = self.matches[ind]
        return res

    def groups_info(self):
        lst = [""] * len(self.matchesInfo.keys())
        for ind, group_name in self.matchesInfo.items():
            lst[ind] = group_name
        return lst

    def __repr__(self):
        fields_filters = ["codes", "inputLst"]
        fields_expr = [
            f"{f.name}={getattr(self, f.name)}"
            for f in fields(self)
            if f.name not in fields_filters
        ]
        fields_expr = "(" + ",".join(fields_expr) + ")"
        return f"Runner{fields_expr}"
