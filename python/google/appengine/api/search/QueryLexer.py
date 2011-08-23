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
LPAREN=20
PHRASE=25
RESTRICTION=9
WORD=11
COLON=33
DISJUNCTION=5
RPAREN=21
SELECTOR=22
WS=38
NEGATION=6
NONE=7
OR=18
RCURLY=30
GT=15
DIGIT=31
MISC=37
LE=14
STRING=10


class QueryLexer(Lexer):

    grammarFileName = "apphosting/api/search/Query.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

        self.dfa5 = self.DFA5(
            self, 5,
            eot = self.DFA5_eot,
            eof = self.DFA5_eof,
            min = self.DFA5_min,
            max = self.DFA5_max,
            accept = self.DFA5_accept,
            special = self.DFA5_special,
            transition = self.DFA5_transition
            )







    def mOR(self, ):

        try:
            _type = OR
            _channel = DEFAULT_CHANNEL



            pass
            self.match("OR")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mAND(self, ):

        try:
            _type = AND
            _channel = DEFAULT_CHANNEL



            pass
            self.match("AND")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNOT(self, ):

        try:
            _type = NOT
            _channel = DEFAULT_CHANNEL



            pass
            self.match("NOT")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTO(self, ):

        try:
            _type = TO
            _channel = DEFAULT_CHANNEL



            pass
            self.match("TO")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLPAREN(self, ):

        try:
            _type = LPAREN
            _channel = DEFAULT_CHANNEL



            pass
            self.match(40)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mRPAREN(self, ):

        try:
            _type = RPAREN
            _channel = DEFAULT_CHANNEL



            pass
            self.match(41)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLSQUARE(self, ):

        try:
            _type = LSQUARE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(91)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mRSQUARE(self, ):

        try:
            _type = RSQUARE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(93)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLCURLY(self, ):

        try:
            _type = LCURLY
            _channel = DEFAULT_CHANNEL



            pass
            self.match(123)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mRCURLY(self, ):

        try:
            _type = RCURLY
            _channel = DEFAULT_CHANNEL



            pass
            self.match(125)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mINT(self, ):

        try:
            _type = INT
            _channel = DEFAULT_CHANNEL



            pass

            cnt1 = 0
            while True:
                alt1 = 2
                LA1_0 = self.input.LA(1)

                if ((48 <= LA1_0 <= 57)) :
                    alt1 = 1


                if alt1 == 1:

                    pass
                    self.mDIGIT()


                else:
                    if cnt1 >= 1:
                        break

                    eee = EarlyExitException(1, self.input)
                    raise eee

                cnt1 += 1





            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSELECTOR(self, ):

        try:
            _type = SELECTOR
            _channel = DEFAULT_CHANNEL



            pass
            self.mNAME_START()

            while True:
                alt2 = 2
                LA2_0 = self.input.LA(1)

                if (LA2_0 == 36 or (48 <= LA2_0 <= 57) or (65 <= LA2_0 <= 90) or LA2_0 == 95 or (97 <= LA2_0 <= 122) or (192 <= LA2_0 <= 214) or (216 <= LA2_0 <= 246) or (248 <= LA2_0 <= 8191) or (12352 <= LA2_0 <= 12687) or (13056 <= LA2_0 <= 13183) or (13312 <= LA2_0 <= 15661) or (19968 <= LA2_0 <= 40959) or (63744 <= LA2_0 <= 64255)) :
                    alt2 = 1


                if alt2 == 1:

                    pass
                    if self.input.LA(1) == 36 or (48 <= self.input.LA(1) <= 57) or (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    break


            self.mCOLON()



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTEXT(self, ):

        try:
            _type = TEXT
            _channel = DEFAULT_CHANNEL



            pass

            cnt3 = 0
            while True:
                alt3 = 2
                LA3_0 = self.input.LA(1)

                if (LA3_0 == 33 or (35 <= LA3_0 <= 39) or (44 <= LA3_0 <= 57) or LA3_0 == 59 or LA3_0 == 61 or (63 <= LA3_0 <= 90) or LA3_0 == 92 or (94 <= LA3_0 <= 122) or LA3_0 == 126 or (192 <= LA3_0 <= 214) or (216 <= LA3_0 <= 246) or (248 <= LA3_0 <= 8191) or (12352 <= LA3_0 <= 12687) or (13056 <= LA3_0 <= 13183) or (13312 <= LA3_0 <= 15661) or (19968 <= LA3_0 <= 40959) or (63744 <= LA3_0 <= 64255)) :
                    alt3 = 1


                if alt3 == 1:

                    pass
                    if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or (44 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or self.input.LA(1) == 61 or (63 <= self.input.LA(1) <= 90) or self.input.LA(1) == 92 or (94 <= self.input.LA(1) <= 122) or self.input.LA(1) == 126 or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    if cnt3 >= 1:
                        break

                    eee = EarlyExitException(3, self.input)
                    raise eee

                cnt3 += 1





            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mPHRASE(self, ):

        try:
            _type = PHRASE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(34)

            while True:
                alt4 = 2
                LA4_0 = self.input.LA(1)

                if ((0 <= LA4_0 <= 33) or (35 <= LA4_0 <= 91) or (93 <= LA4_0 <= 65535)) :
                    alt4 = 1


                if alt4 == 1:

                    pass
                    if (0 <= self.input.LA(1) <= 33) or (35 <= self.input.LA(1) <= 91) or (93 <= self.input.LA(1) <= 65535):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    break


            self.match(34)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWS(self, ):

        try:
            _type = WS
            _channel = DEFAULT_CHANNEL



            pass
            if (9 <= self.input.LA(1) <= 10) or self.input.LA(1) == 12 or self.input.LA(1) == 32:
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse


            self.skip()




            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLETTER(self, ):

        try:


            pass
            if (65 <= self.input.LA(1) <= 90) or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mDIGIT(self, ):

        try:


            pass
            self.matchRange(48, 57)




        finally:

            pass






    def mMISC(self, ):

        try:


            pass
            if self.input.LA(1) == 33 or self.input.LA(1) == 35 or (37 <= self.input.LA(1) <= 39) or (44 <= self.input.LA(1) <= 47) or self.input.LA(1) == 59 or self.input.LA(1) == 61 or (63 <= self.input.LA(1) <= 64) or self.input.LA(1) == 92 or self.input.LA(1) == 94 or self.input.LA(1) == 96 or self.input.LA(1) == 126:
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mUNDERSCORE(self, ):

        try:


            pass
            self.match(95)




        finally:

            pass






    def mNAME_START(self, ):

        try:


            pass
            if self.input.LA(1) == 36 or (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mDOLLAR(self, ):

        try:


            pass
            self.match(36)




        finally:

            pass






    def mCOLON(self, ):

        try:


            pass
            self.match(58)




        finally:

            pass





    def mTokens(self):

        alt5 = 15
        alt5 = self.dfa5.predict(self.input)
        if alt5 == 1:

            pass
            self.mOR()


        elif alt5 == 2:

            pass
            self.mAND()


        elif alt5 == 3:

            pass
            self.mNOT()


        elif alt5 == 4:

            pass
            self.mTO()


        elif alt5 == 5:

            pass
            self.mLPAREN()


        elif alt5 == 6:

            pass
            self.mRPAREN()


        elif alt5 == 7:

            pass
            self.mLSQUARE()


        elif alt5 == 8:

            pass
            self.mRSQUARE()


        elif alt5 == 9:

            pass
            self.mLCURLY()


        elif alt5 == 10:

            pass
            self.mRCURLY()


        elif alt5 == 11:

            pass
            self.mINT()


        elif alt5 == 12:

            pass
            self.mSELECTOR()


        elif alt5 == 13:

            pass
            self.mTEXT()


        elif alt5 == 14:

            pass
            self.mPHRASE()


        elif alt5 == 15:

            pass
            self.mWS()









    DFA5_eot = DFA.unpack(
        u"\1\uffff\4\15\6\uffff\1\26\1\15\3\uffff\1\27\1\15\1\uffff\2\15"
        u"\1\32\2\uffff\1\33\1\34\3\uffff"
        )

    DFA5_eof = DFA.unpack(
        u"\35\uffff"
        )

    DFA5_min = DFA.unpack(
        u"\1\11\4\44\6\uffff\1\41\1\44\3\uffff\1\41\1\44\1\uffff\2\44\1\41"
        u"\2\uffff\2\41\3\uffff"
        )

    DFA5_max = DFA.unpack(
        u"\5\ufaff\6\uffff\2\ufaff\3\uffff\2\ufaff\1\uffff\3\ufaff\2\uffff"
        u"\2\ufaff\3\uffff"
        )

    DFA5_accept = DFA.unpack(
        u"\5\uffff\1\5\1\6\1\7\1\10\1\11\1\12\2\uffff\1\15\1\16\1\17\2\uffff"
        u"\1\14\3\uffff\1\13\1\1\2\uffff\1\4\1\2\1\3"
        )

    DFA5_special = DFA.unpack(
        u"\35\uffff"
        )


    DFA5_transition = [
        DFA.unpack(u"\2\17\1\uffff\1\17\23\uffff\1\17\1\15\1\16\1\15\1\14"
        u"\3\15\1\5\1\6\2\uffff\4\15\12\13\1\uffff\1\15\1\uffff\1\15\1\uffff"
        u"\2\15\1\2\14\14\1\3\1\1\4\14\1\4\6\14\1\7\1\15\1\10\1\15\1\14\1"
        u"\15\32\14\1\11\1\uffff\1\12\1\15\101\uffff\27\14\1\uffff\37\14"
        u"\1\uffff\u1f08\14\u1040\uffff\u0150\14\u0170\uffff\u0080\14\u0080"
        u"\uffff\u092e\14\u10d2\uffff\u5200\14\u5900\uffff\u0200\14"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\21\21\1\20\10\21"
        u"\4\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\15\21\1\23\14\21"
        u"\4\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\16\21\1\24\13\21"
        u"\4\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\16\21\1\25\13\21"
        u"\4\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\15\1\uffff\5\15\4\uffff\4\15\12\13\1\uffff\1\15"
        u"\1\uffff\1\15\1\uffff\34\15\1\uffff\1\15\1\uffff\35\15\3\uffff"
        u"\1\15\101\uffff\27\15\1\uffff\37\15\1\uffff\u1f08\15\u1040\uffff"
        u"\u0150\15\u0170\uffff\u0080\15\u0080\uffff\u092e\15\u10d2\uffff"
        u"\u5200\15\u5900\uffff\u0200\15"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\32\21\4\uffff\1\21"
        u"\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff\u1f08\21\u1040"
        u"\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff\u092e\21\u10d2"
        u"\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\15\1\uffff\1\15\1\21\3\15\4\uffff\4\15\12\21\1\22"
        u"\1\15\1\uffff\1\15\1\uffff\2\15\32\21\1\uffff\1\15\1\uffff\1\15"
        u"\1\21\1\15\32\21\3\uffff\1\15\101\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\32\21\4\uffff\1\21"
        u"\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff\u1f08\21\u1040"
        u"\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff\u092e\21\u10d2"
        u"\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\3\21\1\30\26\21\4"
        u"\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\1\22\6\uffff\23\21\1\31\6\21\4"
        u"\uffff\1\21\1\uffff\32\21\105\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\15\1\uffff\1\15\1\21\3\15\4\uffff\4\15\12\21\1\22"
        u"\1\15\1\uffff\1\15\1\uffff\2\15\32\21\1\uffff\1\15\1\uffff\1\15"
        u"\1\21\1\15\32\21\3\uffff\1\15\101\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\15\1\uffff\1\15\1\21\3\15\4\uffff\4\15\12\21\1\22"
        u"\1\15\1\uffff\1\15\1\uffff\2\15\32\21\1\uffff\1\15\1\uffff\1\15"
        u"\1\21\1\15\32\21\3\uffff\1\15\101\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u"\1\15\1\uffff\1\15\1\21\3\15\4\uffff\4\15\12\21\1\22"
        u"\1\15\1\uffff\1\15\1\uffff\2\15\32\21\1\uffff\1\15\1\uffff\1\15"
        u"\1\21\1\15\32\21\3\uffff\1\15\101\uffff\27\21\1\uffff\37\21\1\uffff"
        u"\u1f08\21\u1040\uffff\u0150\21\u0170\uffff\u0080\21\u0080\uffff"
        u"\u092e\21\u10d2\uffff\u5200\21\u5900\uffff\u0200\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA5 = DFA




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from antlr3.main import LexerMain
    main = LexerMain(QueryLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
