#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import sys
from antlr3 import *
from antlr3.compat import set, frozenset

from antlr3.tree import *










HIDDEN = BaseRecognizer.HIDDEN


DOLLAR=35
GE=16
LT=13
LSQUARE=26
TO=28
LETTER=34
CONJUNCTION=4
NUMBER=8
UNDERSCORE=36
LCURLY=27
INT=23
NAME_START=32
NOT=19
RSQUARE=29
TEXT=24
VALUE=12
AND=17
EOF=-1
PHRASE=25
LPAREN=20
RESTRICTION=9
COLON=33
WORD=11
DISJUNCTION=5
RPAREN=21
WS=38
SELECTOR=22
NEGATION=6
NONE=7
RCURLY=30
OR=18
GT=15
DIGIT=31
MISC=37
LE=14
STRING=10


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "CONJUNCTION", "DISJUNCTION", "NEGATION", "NONE", "NUMBER", "RESTRICTION",
    "STRING", "WORD", "VALUE", "LT", "LE", "GT", "GE", "AND", "OR", "NOT",
    "LPAREN", "RPAREN", "SELECTOR", "INT", "TEXT", "PHRASE", "LSQUARE",
    "LCURLY", "TO", "RSQUARE", "RCURLY", "DIGIT", "NAME_START", "COLON",
    "LETTER", "DOLLAR", "UNDERSCORE", "MISC", "WS"
]




class QueryParser(Parser):
    grammarFileName = "apphosting/api/search/Query.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"
    tokenNames = tokenNames

    def __init__(self, input, state=None):
        if state is None:
            state = RecognizerSharedState()

        Parser.__init__(self, input, state)


        self.dfa12 = self.DFA12(
            self, 12,
            eot = self.DFA12_eot,
            eof = self.DFA12_eof,
            min = self.DFA12_min,
            max = self.DFA12_max,
            accept = self.DFA12_accept,
            special = self.DFA12_special,
            transition = self.DFA12_transition
            )







        self._adaptor = CommonTreeAdaptor()



    def getTreeAdaptor(self):
        return self._adaptor

    def setTreeAdaptor(self, adaptor):
        self._adaptor = adaptor

    adaptor = property(getTreeAdaptor, setTreeAdaptor)



    def trimLast(self, selector):
      return selector[:len(selector)-1]

    def normalizeSpace(self, phrase):

      return phrase


    class query_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def query(self, ):

        retval = self.query_return()
        retval.start = self.input.LT(1)

        root_0 = None

        EOF2 = None
        expression1 = None


        EOF2_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_expression_in_query131)
                expression1 = self.expression()

                self._state.following.pop()
                self._adaptor.addChild(root_0, expression1.tree)
                EOF2=self.match(self.input, EOF, self.FOLLOW_EOF_in_query133)

                EOF2_tree = self._adaptor.createWithPayload(EOF2)
                self._adaptor.addChild(root_0, EOF2_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class expression_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def expression(self, ):

        retval = self.expression_return()
        retval.start = self.input.LT(1)

        root_0 = None

        AND4 = None
        factor3 = None

        factor5 = None


        AND4_tree = None
        stream_AND = RewriteRuleTokenStream(self._adaptor, "token AND")
        stream_factor = RewriteRuleSubtreeStream(self._adaptor, "rule factor")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_factor_in_expression151)
                factor3 = self.factor()

                self._state.following.pop()
                stream_factor.add(factor3.tree)

                while True:
                    alt2 = 2
                    LA2_0 = self.input.LA(1)

                    if (LA2_0 == AND or (NOT <= LA2_0 <= LPAREN) or (SELECTOR <= LA2_0 <= PHRASE)) :
                        alt2 = 1


                    if alt2 == 1:

                        pass

                        alt1 = 2
                        LA1_0 = self.input.LA(1)

                        if (LA1_0 == AND) :
                            alt1 = 1
                        if alt1 == 1:

                            pass
                            AND4=self.match(self.input, AND, self.FOLLOW_AND_in_expression154)
                            stream_AND.add(AND4)



                        self._state.following.append(self.FOLLOW_factor_in_expression157)
                        factor5 = self.factor()

                        self._state.following.pop()
                        stream_factor.add(factor5.tree)


                    else:
                        break










                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                if not (stream_factor.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_factor.hasNext():
                    self._adaptor.addChild(root_1, stream_factor.nextTree())


                stream_factor.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class factor_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def factor(self, ):

        retval = self.factor_return()
        retval.start = self.input.LT(1)

        root_0 = None

        OR7 = None
        term6 = None

        term8 = None


        OR7_tree = None
        stream_OR = RewriteRuleTokenStream(self._adaptor, "token OR")
        stream_term = RewriteRuleSubtreeStream(self._adaptor, "rule term")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_term_in_factor185)
                term6 = self.term()

                self._state.following.pop()
                stream_term.add(term6.tree)

                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if (LA3_0 == OR) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        OR7=self.match(self.input, OR, self.FOLLOW_OR_in_factor188)
                        stream_OR.add(OR7)
                        self._state.following.append(self.FOLLOW_term_in_factor190)
                        term8 = self.term()

                        self._state.following.pop()
                        stream_term.add(term8.tree)


                    else:
                        break










                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(DISJUNCTION, "DISJUNCTION"), root_1)


                if not (stream_term.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_term.hasNext():
                    self._adaptor.addChild(root_1, stream_term.nextTree())


                stream_term.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class term_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def term(self, ):

        retval = self.term_return()
        retval.start = self.input.LT(1)

        root_0 = None

        NOT9 = None
        primitive10 = None

        primitive11 = None


        NOT9_tree = None
        stream_NOT = RewriteRuleTokenStream(self._adaptor, "token NOT")
        stream_primitive = RewriteRuleSubtreeStream(self._adaptor, "rule primitive")
        try:
            try:

                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == NOT) :
                    alt4 = 1
                elif (LA4_0 == LPAREN or (SELECTOR <= LA4_0 <= PHRASE)) :
                    alt4 = 2
                else:
                    nvae = NoViableAltException("", 4, 0, self.input)

                    raise nvae

                if alt4 == 1:

                    pass
                    NOT9=self.match(self.input, NOT, self.FOLLOW_NOT_in_term219)
                    stream_NOT.add(NOT9)
                    self._state.following.append(self.FOLLOW_primitive_in_term221)
                    primitive10 = self.primitive()

                    self._state.following.pop()
                    stream_primitive.add(primitive10.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(NEGATION, "NEGATION"), root_1)

                    self._adaptor.addChild(root_1, stream_primitive.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt4 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_primitive_in_term235)
                    primitive11 = self.primitive()

                    self._state.following.pop()
                    stream_primitive.add(primitive11.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_primitive.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class primitive_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def primitive(self, ):

        retval = self.primitive_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN14 = None
        RPAREN16 = None
        field = None

        value12 = None

        atom13 = None

        expression15 = None


        LPAREN14_tree = None
        RPAREN16_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_expression = RewriteRuleSubtreeStream(self._adaptor, "rule expression")
        stream_selector = RewriteRuleSubtreeStream(self._adaptor, "rule selector")
        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        stream_value = RewriteRuleSubtreeStream(self._adaptor, "rule value")
        try:
            try:

                alt5 = 3
                LA5 = self.input.LA(1)
                if LA5 == SELECTOR:
                    alt5 = 1
                elif LA5 == INT or LA5 == TEXT or LA5 == PHRASE:
                    alt5 = 2
                elif LA5 == LPAREN:
                    alt5 = 3
                else:
                    nvae = NoViableAltException("", 5, 0, self.input)

                    raise nvae

                if alt5 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_selector_in_primitive260)
                    field = self.selector()

                    self._state.following.pop()
                    stream_selector.add(field.tree)
                    self._state.following.append(self.FOLLOW_value_in_primitive262)
                    value12 = self.value()

                    self._state.following.pop()
                    stream_value.add(value12.tree)








                    retval.tree = root_0

                    if field is not None:
                        stream_field = RewriteRuleSubtreeStream(self._adaptor, "token field", field.tree)
                    else:
                        stream_field = RewriteRuleSubtreeStream(self._adaptor, "token field", None)


                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_field.nextTree())
                    self._adaptor.addChild(root_1, stream_value.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt5 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_atom_in_primitive279)
                    atom13 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom13.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(NONE, "NONE"))
                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt5 == 3:

                    pass
                    LPAREN14=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_primitive295)
                    stream_LPAREN.add(LPAREN14)
                    self._state.following.append(self.FOLLOW_expression_in_primitive297)
                    expression15 = self.expression()

                    self._state.following.pop()
                    stream_expression.add(expression15.tree)
                    RPAREN16=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_primitive299)
                    stream_RPAREN.add(RPAREN16)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_expression.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class value_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def value(self, ):

        retval = self.value_return()
        retval.start = self.input.LT(1)

        root_0 = None

        atom17 = None

        range18 = None


        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        stream_range = RewriteRuleSubtreeStream(self._adaptor, "rule range")
        try:
            try:

                alt6 = 2
                LA6_0 = self.input.LA(1)

                if ((INT <= LA6_0 <= PHRASE)) :
                    alt6 = 1
                elif ((LSQUARE <= LA6_0 <= LCURLY)) :
                    alt6 = 2
                else:
                    nvae = NoViableAltException("", 6, 0, self.input)

                    raise nvae

                if alt6 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_atom_in_value318)
                    atom17 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom17.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_atom.nextTree())



                    retval.tree = root_0


                elif alt6 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_range_in_value328)
                    range18 = self.range()

                    self._state.following.pop()
                    stream_range.add(range18.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_range.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class selector_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def selector(self, ):

        retval = self.selector_return()
        retval.start = self.input.LT(1)

        root_0 = None

        s = None

        s_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                s=self.match(self.input, SELECTOR, self.FOLLOW_SELECTOR_in_selector348)

                s_tree = self._adaptor.createWithPayload(s)
                self._adaptor.addChild(root_0, s_tree)


                s.setText(self.trimLast(s.text))




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class atom_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def atom(self, ):

        retval = self.atom_return()
        retval.start = self.input.LT(1)

        root_0 = None

        v = None
        t = None
        p = None

        v_tree = None
        t_tree = None
        p_tree = None
        stream_INT = RewriteRuleTokenStream(self._adaptor, "token INT")
        stream_TEXT = RewriteRuleTokenStream(self._adaptor, "token TEXT")
        stream_PHRASE = RewriteRuleTokenStream(self._adaptor, "token PHRASE")

        try:
            try:

                alt7 = 3
                LA7 = self.input.LA(1)
                if LA7 == INT:
                    alt7 = 1
                elif LA7 == TEXT:
                    alt7 = 2
                elif LA7 == PHRASE:
                    alt7 = 3
                else:
                    nvae = NoViableAltException("", 7, 0, self.input)

                    raise nvae

                if alt7 == 1:

                    pass
                    v=self.match(self.input, INT, self.FOLLOW_INT_in_atom370)
                    stream_INT.add(v)








                    retval.tree = root_0
                    stream_v = RewriteRuleTokenStream(self._adaptor, "token v", v)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(NUMBER, "NUMBER"))
                    self._adaptor.addChild(root_1, stream_v.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt7 == 2:

                    pass
                    t=self.match(self.input, TEXT, self.FOLLOW_TEXT_in_atom389)
                    stream_TEXT.add(t)








                    retval.tree = root_0
                    stream_t = RewriteRuleTokenStream(self._adaptor, "token t", t)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(WORD, "WORD"))
                    self._adaptor.addChild(root_1, stream_t.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt7 == 3:

                    pass
                    p=self.match(self.input, PHRASE, self.FOLLOW_PHRASE_in_atom408)
                    stream_PHRASE.add(p)

                    p.setText(self.normalizeSpace(p.text))









                    retval.tree = root_0
                    stream_p = RewriteRuleTokenStream(self._adaptor, "token p", p)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(STRING, "STRING"))
                    self._adaptor.addChild(root_1, stream_p.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class range_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def range(self, ):

        retval = self.range_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LSQUARE19 = None
        LCURLY20 = None
        TO21 = None
        RSQUARE23 = None
        LSQUARE24 = None
        LCURLY25 = None
        TO26 = None
        RCURLY28 = None
        LSQUARE29 = None
        TO31 = None
        RSQUARE32 = None
        RCURLY33 = None
        LCURLY34 = None
        TO36 = None
        RSQUARE37 = None
        RCURLY38 = None
        LSQUARE39 = None
        TO40 = None
        RSQUARE41 = None
        LCURLY42 = None
        TO43 = None
        RSQUARE44 = None
        LSQUARE45 = None
        TO46 = None
        RCURLY47 = None
        LCURLY48 = None
        TO49 = None
        RCURLY50 = None
        l = None

        h = None

        atom22 = None

        atom27 = None

        atom30 = None

        atom35 = None


        LSQUARE19_tree = None
        LCURLY20_tree = None
        TO21_tree = None
        RSQUARE23_tree = None
        LSQUARE24_tree = None
        LCURLY25_tree = None
        TO26_tree = None
        RCURLY28_tree = None
        LSQUARE29_tree = None
        TO31_tree = None
        RSQUARE32_tree = None
        RCURLY33_tree = None
        LCURLY34_tree = None
        TO36_tree = None
        RSQUARE37_tree = None
        RCURLY38_tree = None
        LSQUARE39_tree = None
        TO40_tree = None
        RSQUARE41_tree = None
        LCURLY42_tree = None
        TO43_tree = None
        RSQUARE44_tree = None
        LSQUARE45_tree = None
        TO46_tree = None
        RCURLY47_tree = None
        LCURLY48_tree = None
        TO49_tree = None
        RCURLY50_tree = None
        stream_LCURLY = RewriteRuleTokenStream(self._adaptor, "token LCURLY")
        stream_LSQUARE = RewriteRuleTokenStream(self._adaptor, "token LSQUARE")
        stream_RSQUARE = RewriteRuleTokenStream(self._adaptor, "token RSQUARE")
        stream_TO = RewriteRuleTokenStream(self._adaptor, "token TO")
        stream_RCURLY = RewriteRuleTokenStream(self._adaptor, "token RCURLY")
        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt12 = 8
                alt12 = self.dfa12.predict(self.input)
                if alt12 == 1:

                    pass

                    alt8 = 2
                    LA8_0 = self.input.LA(1)

                    if (LA8_0 == LSQUARE) :
                        alt8 = 1
                    elif (LA8_0 == LCURLY) :
                        alt8 = 2
                    else:
                        nvae = NoViableAltException("", 8, 0, self.input)

                        raise nvae

                    if alt8 == 1:

                        pass
                        LSQUARE19=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_range436)
                        stream_LSQUARE.add(LSQUARE19)


                    elif alt8 == 2:

                        pass
                        LCURLY20=self.match(self.input, LCURLY, self.FOLLOW_LCURLY_in_range440)
                        stream_LCURLY.add(LCURLY20)



                    TO21=self.match(self.input, TO, self.FOLLOW_TO_in_range443)
                    stream_TO.add(TO21)
                    self._state.following.append(self.FOLLOW_atom_in_range445)
                    atom22 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom22.tree)
                    RSQUARE23=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_range447)
                    stream_RSQUARE.add(RSQUARE23)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(LE, "LE"), root_1)

                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 2:

                    pass

                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if (LA9_0 == LSQUARE) :
                        alt9 = 1
                    elif (LA9_0 == LCURLY) :
                        alt9 = 2
                    else:
                        nvae = NoViableAltException("", 9, 0, self.input)

                        raise nvae

                    if alt9 == 1:

                        pass
                        LSQUARE24=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_range462)
                        stream_LSQUARE.add(LSQUARE24)


                    elif alt9 == 2:

                        pass
                        LCURLY25=self.match(self.input, LCURLY, self.FOLLOW_LCURLY_in_range466)
                        stream_LCURLY.add(LCURLY25)



                    TO26=self.match(self.input, TO, self.FOLLOW_TO_in_range469)
                    stream_TO.add(TO26)
                    self._state.following.append(self.FOLLOW_atom_in_range471)
                    atom27 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom27.tree)
                    RCURLY28=self.match(self.input, RCURLY, self.FOLLOW_RCURLY_in_range473)
                    stream_RCURLY.add(RCURLY28)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(LT, "LT"), root_1)

                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 3:

                    pass
                    LSQUARE29=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_range487)
                    stream_LSQUARE.add(LSQUARE29)
                    self._state.following.append(self.FOLLOW_atom_in_range489)
                    atom30 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom30.tree)
                    TO31=self.match(self.input, TO, self.FOLLOW_TO_in_range491)
                    stream_TO.add(TO31)

                    alt10 = 2
                    LA10_0 = self.input.LA(1)

                    if (LA10_0 == RSQUARE) :
                        alt10 = 1
                    elif (LA10_0 == RCURLY) :
                        alt10 = 2
                    else:
                        nvae = NoViableAltException("", 10, 0, self.input)

                        raise nvae

                    if alt10 == 1:

                        pass
                        RSQUARE32=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_range494)
                        stream_RSQUARE.add(RSQUARE32)


                    elif alt10 == 2:

                        pass
                        RCURLY33=self.match(self.input, RCURLY, self.FOLLOW_RCURLY_in_range498)
                        stream_RCURLY.add(RCURLY33)











                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(GE, "GE"), root_1)

                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 4:

                    pass
                    LCURLY34=self.match(self.input, LCURLY, self.FOLLOW_LCURLY_in_range513)
                    stream_LCURLY.add(LCURLY34)
                    self._state.following.append(self.FOLLOW_atom_in_range515)
                    atom35 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom35.tree)
                    TO36=self.match(self.input, TO, self.FOLLOW_TO_in_range517)
                    stream_TO.add(TO36)

                    alt11 = 2
                    LA11_0 = self.input.LA(1)

                    if (LA11_0 == RSQUARE) :
                        alt11 = 1
                    elif (LA11_0 == RCURLY) :
                        alt11 = 2
                    else:
                        nvae = NoViableAltException("", 11, 0, self.input)

                        raise nvae

                    if alt11 == 1:

                        pass
                        RSQUARE37=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_range520)
                        stream_RSQUARE.add(RSQUARE37)


                    elif alt11 == 2:

                        pass
                        RCURLY38=self.match(self.input, RCURLY, self.FOLLOW_RCURLY_in_range524)
                        stream_RCURLY.add(RCURLY38)











                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(GT, "GT"), root_1)

                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 5:

                    pass
                    LSQUARE39=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_range539)
                    stream_LSQUARE.add(LSQUARE39)
                    self._state.following.append(self.FOLLOW_atom_in_range543)
                    l = self.atom()

                    self._state.following.pop()
                    stream_atom.add(l.tree)
                    TO40=self.match(self.input, TO, self.FOLLOW_TO_in_range545)
                    stream_TO.add(TO40)
                    self._state.following.append(self.FOLLOW_atom_in_range549)
                    h = self.atom()

                    self._state.following.pop()
                    stream_atom.add(h.tree)
                    RSQUARE41=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_range551)
                    stream_RSQUARE.add(RSQUARE41)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    if l is not None:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", l.tree)
                    else:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", None)


                    if h is not None:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", h.tree)
                    else:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(GE, "GE"), root_2)

                    self._adaptor.addChild(root_2, stream_l.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(LE, "LE"), root_2)

                    self._adaptor.addChild(root_2, stream_h.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 6:

                    pass
                    LCURLY42=self.match(self.input, LCURLY, self.FOLLOW_LCURLY_in_range577)
                    stream_LCURLY.add(LCURLY42)
                    self._state.following.append(self.FOLLOW_atom_in_range581)
                    l = self.atom()

                    self._state.following.pop()
                    stream_atom.add(l.tree)
                    TO43=self.match(self.input, TO, self.FOLLOW_TO_in_range583)
                    stream_TO.add(TO43)
                    self._state.following.append(self.FOLLOW_atom_in_range587)
                    h = self.atom()

                    self._state.following.pop()
                    stream_atom.add(h.tree)
                    RSQUARE44=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_range589)
                    stream_RSQUARE.add(RSQUARE44)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    if l is not None:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", l.tree)
                    else:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", None)


                    if h is not None:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", h.tree)
                    else:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(GT, "GT"), root_2)

                    self._adaptor.addChild(root_2, stream_l.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(LE, "LE"), root_2)

                    self._adaptor.addChild(root_2, stream_h.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 7:

                    pass
                    LSQUARE45=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_range615)
                    stream_LSQUARE.add(LSQUARE45)
                    self._state.following.append(self.FOLLOW_atom_in_range619)
                    l = self.atom()

                    self._state.following.pop()
                    stream_atom.add(l.tree)
                    TO46=self.match(self.input, TO, self.FOLLOW_TO_in_range621)
                    stream_TO.add(TO46)
                    self._state.following.append(self.FOLLOW_atom_in_range625)
                    h = self.atom()

                    self._state.following.pop()
                    stream_atom.add(h.tree)
                    RCURLY47=self.match(self.input, RCURLY, self.FOLLOW_RCURLY_in_range627)
                    stream_RCURLY.add(RCURLY47)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    if l is not None:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", l.tree)
                    else:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", None)


                    if h is not None:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", h.tree)
                    else:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(GE, "GE"), root_2)

                    self._adaptor.addChild(root_2, stream_l.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(LT, "LT"), root_2)

                    self._adaptor.addChild(root_2, stream_h.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt12 == 8:

                    pass
                    LCURLY48=self.match(self.input, LCURLY, self.FOLLOW_LCURLY_in_range653)
                    stream_LCURLY.add(LCURLY48)
                    self._state.following.append(self.FOLLOW_atom_in_range657)
                    l = self.atom()

                    self._state.following.pop()
                    stream_atom.add(l.tree)
                    TO49=self.match(self.input, TO, self.FOLLOW_TO_in_range659)
                    stream_TO.add(TO49)
                    self._state.following.append(self.FOLLOW_atom_in_range663)
                    h = self.atom()

                    self._state.following.pop()
                    stream_atom.add(h.tree)
                    RCURLY50=self.match(self.input, RCURLY, self.FOLLOW_RCURLY_in_range665)
                    stream_RCURLY.add(RCURLY50)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    if l is not None:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", l.tree)
                    else:
                        stream_l = RewriteRuleSubtreeStream(self._adaptor, "token l", None)


                    if h is not None:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", h.tree)
                    else:
                        stream_h = RewriteRuleSubtreeStream(self._adaptor, "token h", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(GT, "GT"), root_2)

                    self._adaptor.addChild(root_2, stream_l.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(LT, "LT"), root_2)

                    self._adaptor.addChild(root_2, stream_h.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval









    DFA12_eot = DFA.unpack(
        u"\35\uffff"
        )

    DFA12_eof = DFA.unpack(
        u"\35\uffff"
        )

    DFA12_min = DFA.unpack(
        u"\1\32\3\27\6\34\3\35\2\27\3\uffff\3\35\1\uffff\3\35\4\uffff"
        )

    DFA12_max = DFA.unpack(
        u"\1\33\2\34\1\31\6\34\5\36\3\uffff\3\36\1\uffff\3\36\4\uffff"
        )

    DFA12_accept = DFA.unpack(
        u"\17\uffff\1\2\1\1\1\3\3\uffff\1\4\3\uffff\1\5\1\7\1\6\1\10"
        )

    DFA12_special = DFA.unpack(
        u"\35\uffff"
        )


    DFA12_transition = [
        DFA.unpack(u"\1\1\1\2"),
        DFA.unpack(u"\1\4\1\5\1\6\2\uffff\1\3"),
        DFA.unpack(u"\1\7\1\10\1\11\2\uffff\1\3"),
        DFA.unpack(u"\1\12\1\13\1\14"),
        DFA.unpack(u"\1\15"),
        DFA.unpack(u"\1\15"),
        DFA.unpack(u"\1\15"),
        DFA.unpack(u"\1\16"),
        DFA.unpack(u"\1\16"),
        DFA.unpack(u"\1\16"),
        DFA.unpack(u"\1\20\1\17"),
        DFA.unpack(u"\1\20\1\17"),
        DFA.unpack(u"\1\20\1\17"),
        DFA.unpack(u"\1\22\1\23\1\24\3\uffff\2\21"),
        DFA.unpack(u"\1\26\1\27\1\30\3\uffff\2\25"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\31\1\32"),
        DFA.unpack(u"\1\31\1\32"),
        DFA.unpack(u"\1\31\1\32"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\33\1\34"),
        DFA.unpack(u"\1\33\1\34"),
        DFA.unpack(u"\1\33\1\34"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA12 = DFA


    FOLLOW_expression_in_query131 = frozenset([])
    FOLLOW_EOF_in_query133 = frozenset([1])
    FOLLOW_factor_in_expression151 = frozenset([1, 17, 19, 20, 22, 23, 24, 25])
    FOLLOW_AND_in_expression154 = frozenset([17, 19, 20, 22, 23, 24, 25])
    FOLLOW_factor_in_expression157 = frozenset([1, 17, 19, 20, 22, 23, 24, 25])
    FOLLOW_term_in_factor185 = frozenset([1, 18])
    FOLLOW_OR_in_factor188 = frozenset([17, 19, 20, 22, 23, 24, 25])
    FOLLOW_term_in_factor190 = frozenset([1, 18])
    FOLLOW_NOT_in_term219 = frozenset([17, 19, 20, 22, 23, 24, 25])
    FOLLOW_primitive_in_term221 = frozenset([1])
    FOLLOW_primitive_in_term235 = frozenset([1])
    FOLLOW_selector_in_primitive260 = frozenset([23, 24, 25, 26, 27])
    FOLLOW_value_in_primitive262 = frozenset([1])
    FOLLOW_atom_in_primitive279 = frozenset([1])
    FOLLOW_LPAREN_in_primitive295 = frozenset([17, 19, 20, 22, 23, 24, 25])
    FOLLOW_expression_in_primitive297 = frozenset([21])
    FOLLOW_RPAREN_in_primitive299 = frozenset([1])
    FOLLOW_atom_in_value318 = frozenset([1])
    FOLLOW_range_in_value328 = frozenset([1])
    FOLLOW_SELECTOR_in_selector348 = frozenset([1])
    FOLLOW_INT_in_atom370 = frozenset([1])
    FOLLOW_TEXT_in_atom389 = frozenset([1])
    FOLLOW_PHRASE_in_atom408 = frozenset([1])
    FOLLOW_LSQUARE_in_range436 = frozenset([28])
    FOLLOW_LCURLY_in_range440 = frozenset([28])
    FOLLOW_TO_in_range443 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range445 = frozenset([29])
    FOLLOW_RSQUARE_in_range447 = frozenset([1])
    FOLLOW_LSQUARE_in_range462 = frozenset([28])
    FOLLOW_LCURLY_in_range466 = frozenset([28])
    FOLLOW_TO_in_range469 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range471 = frozenset([30])
    FOLLOW_RCURLY_in_range473 = frozenset([1])
    FOLLOW_LSQUARE_in_range487 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range489 = frozenset([28])
    FOLLOW_TO_in_range491 = frozenset([29, 30])
    FOLLOW_RSQUARE_in_range494 = frozenset([1])
    FOLLOW_RCURLY_in_range498 = frozenset([1])
    FOLLOW_LCURLY_in_range513 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range515 = frozenset([28])
    FOLLOW_TO_in_range517 = frozenset([29, 30])
    FOLLOW_RSQUARE_in_range520 = frozenset([1])
    FOLLOW_RCURLY_in_range524 = frozenset([1])
    FOLLOW_LSQUARE_in_range539 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range543 = frozenset([28])
    FOLLOW_TO_in_range545 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range549 = frozenset([29])
    FOLLOW_RSQUARE_in_range551 = frozenset([1])
    FOLLOW_LCURLY_in_range577 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range581 = frozenset([28])
    FOLLOW_TO_in_range583 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range587 = frozenset([29])
    FOLLOW_RSQUARE_in_range589 = frozenset([1])
    FOLLOW_LSQUARE_in_range615 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range619 = frozenset([28])
    FOLLOW_TO_in_range621 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range625 = frozenset([30])
    FOLLOW_RCURLY_in_range627 = frozenset([1])
    FOLLOW_LCURLY_in_range653 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range657 = frozenset([28])
    FOLLOW_TO_in_range659 = frozenset([23, 24, 25])
    FOLLOW_atom_in_range663 = frozenset([30])
    FOLLOW_RCURLY_in_range665 = frozenset([1])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from antlr3.main import ParserMain
    main = ParserMain("QueryLexer", QueryParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
