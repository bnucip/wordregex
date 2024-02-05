########   3个主要API
from syntax.parser import regex_to_tree
from syntax.code import tree_to_code, dump_codes, CodeType
from runner import Runner
from typing import Optional, Tuple, List, Dict, Any, Text


def compile_regex(
    regex_raw, DEBUG=False, regex_others=None
) -> Tuple[Optional[Runner], bool]:
    t, ok = regex_to_tree(regex_raw, regex_others)
    if not ok:
        print("regex to tree error")
        return None, False
    if DEBUG:
        print(t.to_string())
    codes, groupsInfo, ok = tree_to_code(t)
    if not ok:
        print("tree to code error")
        return None, False
    if DEBUG:
        print(dump_codes(codes))
    return Runner(codes=codes, matchesInfo=groupsInfo), True


# 从第一个词对象开始进行一次匹配
def find_word_string(
    regex_raw, words_lst, DEBUG=False, options_regex=None
) -> Tuple[List[Dict[Text, Any]], bool]:
    r, ok = compile_regex(regex_raw, DEBUG, options_regex)
    if not ok:
        print("compile error")
        return None, False
    return find_word_string_r(r, words_lst, DEBUG)


def find_all_word_string(
    regex_raw, words_lst, DEBUG=False, options_regex=None
) -> Tuple[List[List[Dict[Text, Any]]], bool]:
    r, ok = compile_regex(regex_raw, DEBUG, options_regex)
    if not ok:
        print("compile error")
        return None, False
    return find_all_word_string_r(r, words_lst, DEBUG)


def find_word_string_r(
    runner, words_lst, DEBUG=False
) -> Tuple[List[Dict[Text, Any]], bool]:
    for i in range(len(words_lst)):
        matches = runner.run(words_lst, i, DEBUG)
        if matches is not None:
            res = {}
            for k, v in matches.items():
                res[k] = words_lst[v[0] : v[1]]
            return res, True
    print("fail match")
    return None, False


def find_all_word_string_r(
    runner, words_lst, DEBUG=False
) -> Tuple[List[List[Dict[Text, Any]]], bool]:
    all_res = []
    for i in range(len(words_lst)):
        matches = runner.run(words_lst, i, DEBUG)
        if matches is not None:
            res = {}
            for k, v in matches.items():
                res[k] = words_lst[v[0] : v[1]]
            all_res.append(res)
    if len(all_res) == 0:
        print("fail match")
        return None, False
    return all_res, True
