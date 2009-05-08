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





allOrdinals = set([1, 2, 3, 4, 5])
numOrdinals = len(allOrdinals)




HIDDEN = BaseRecognizer.HIDDEN

THIRD=12
SEPTEMBER=35
FOURTH=13
SECOND=11
WEDNESDAY=21
NOVEMBER=37
SATURDAY=24
JULY=33
APRIL=30
DIGITS=8
OCTOBER=36
MAY=31
EVERY=6
FEBRUARY=28
MONDAY=19
SUNDAY=25
JUNE=32
DAY=18
MARCH=29
OF=4
EOF=-1
JANUARY=27
MONTH=26
FRIDAY=23
FIFTH=14
MINUTES=17
TIME=5
WS=40
QUARTER=39
THURSDAY=22
COMMA=9
DECEMBER=38
AUGUST=34
DIGIT=7
TUESDAY=20
HOURS=16
FIRST=10
FOURTH_OR_FIFTH=15

tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "OF", "TIME", "EVERY", "DIGIT", "DIGITS", "COMMA", "FIRST", "SECOND",
    "THIRD", "FOURTH", "FIFTH", "FOURTH_OR_FIFTH", "HOURS", "MINUTES", "DAY",
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY",
    "SUNDAY", "MONTH", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER", "QUARTER",
    "WS"
]




class GrocParser(Parser):
    grammarFileName = "Groc.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"
    tokenNames = tokenNames

    def __init__(self, input, state=None):
        if state is None:
            state = RecognizerSharedState()

        Parser.__init__(self, input, state)


        self.dfa3 = self.DFA3(
            self, 3,
            eot = self.DFA3_eot,
            eof = self.DFA3_eof,
            min = self.DFA3_min,
            max = self.DFA3_max,
            accept = self.DFA3_accept,
            special = self.DFA3_special,
            transition = self.DFA3_transition
            )




        self.ordinal_set = set()
        self.weekday_set = set()
        self.month_set = set()
        self.time_string = '';
        self.interval_mins = 0;
        self.period_string = '';










    valuesDict = {
        SUNDAY: 0,
        FIRST: 1,
        MONDAY: 1,
        JANUARY: 1,
        TUESDAY: 2,
        SECOND: 2,
        FEBRUARY: 2,
        WEDNESDAY: 3,
        THIRD: 3,
        MARCH: 3,
        THURSDAY: 4,
        FOURTH: 4,
        APRIL: 4,
        FRIDAY: 5,
        FIFTH: 5,
        MAY: 5,
        SATURDAY: 6,
        JUNE: 6,
        JULY: 7,
        AUGUST: 8,
        SEPTEMBER: 9,
        OCTOBER: 10,
        NOVEMBER: 11,
        DECEMBER: 12,
      }

    def ValueOf(self, token_type):
      return self.valuesDict.get(token_type, -1)




    def timespec(self, ):

        try:
            try:
                pass
                alt1 = 2
                LA1_0 = self.input.LA(1)

                if (LA1_0 == EVERY) :
                    LA1_1 = self.input.LA(2)

                    if ((DIGIT <= LA1_1 <= DIGITS)) :
                        alt1 = 2
                    elif ((DAY <= LA1_1 <= SUNDAY)) :
                        alt1 = 1
                    else:
                        nvae = NoViableAltException("", 1, 1, self.input)

                        raise nvae

                elif ((FIRST <= LA1_0 <= FOURTH_OR_FIFTH)) :
                    alt1 = 1
                else:
                    nvae = NoViableAltException("", 1, 0, self.input)

                    raise nvae

                if alt1 == 1:
                    pass
                    self._state.following.append(self.FOLLOW_specifictime_in_timespec44)
                    self.specifictime()

                    self._state.following.pop()


                elif alt1 == 2:
                    pass
                    self._state.following.append(self.FOLLOW_interval_in_timespec48)
                    self.interval()

                    self._state.following.pop()







            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def specifictime(self, ):

        TIME1 = None

        try:
            try:
                pass
                pass
                alt3 = 2
                alt3 = self.dfa3.predict(self.input)
                if alt3 == 1:
                    pass
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_ordinals_in_specifictime69)
                    self.ordinals()

                    self._state.following.pop()
                    self._state.following.append(self.FOLLOW_weekdays_in_specifictime71)
                    self.weekdays()

                    self._state.following.pop()



                    self.match(self.input, OF, self.FOLLOW_OF_in_specifictime74)
                    alt2 = 2
                    LA2_0 = self.input.LA(1)

                    if ((MONTH <= LA2_0 <= DECEMBER)) :
                        alt2 = 1
                    elif ((FIRST <= LA2_0 <= THIRD) or LA2_0 == QUARTER) :
                        alt2 = 2
                    else:
                        nvae = NoViableAltException("", 2, 0, self.input)

                        raise nvae

                    if alt2 == 1:
                        pass
                        self._state.following.append(self.FOLLOW_monthspec_in_specifictime77)
                        self.monthspec()

                        self._state.following.pop()


                    elif alt2 == 2:
                        pass
                        self._state.following.append(self.FOLLOW_quarterspec_in_specifictime79)
                        self.quarterspec()

                        self._state.following.pop()








                elif alt3 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_ordinals_in_specifictime96)
                    self.ordinals()

                    self._state.following.pop()
                    self._state.following.append(self.FOLLOW_weekdays_in_specifictime98)
                    self.weekdays()

                    self._state.following.pop()
                    self.month_set = set(range(1,13))






                TIME1=self.match(self.input, TIME, self.FOLLOW_TIME_in_specifictime112)
                self.time_string = TIME1.text







            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def interval(self, ):

        intervalnum = None
        period2 = None


        try:
            try:
                pass
                pass
                self.match(self.input, EVERY, self.FOLLOW_EVERY_in_interval131)
                intervalnum = self.input.LT(1)
                if (DIGIT <= self.input.LA(1) <= DIGITS):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse



                self.interval_mins = int(intervalnum.text)

                self._state.following.append(self.FOLLOW_period_in_interval157)
                period2 = self.period()

                self._state.following.pop()

                if ((period2 is not None) and [self.input.toString(period2.start,period2.stop)] or [None])[0] == "hours":
                  self.period_string = "hours"
                else:
                  self.period_string = "minutes"








            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def ordinals(self, ):

        try:
            try:
                pass
                alt5 = 2
                LA5_0 = self.input.LA(1)

                if (LA5_0 == EVERY) :
                    alt5 = 1
                elif ((FIRST <= LA5_0 <= FOURTH_OR_FIFTH)) :
                    alt5 = 2
                else:
                    nvae = NoViableAltException("", 5, 0, self.input)

                    raise nvae

                if alt5 == 1:
                    pass
                    self.match(self.input, EVERY, self.FOLLOW_EVERY_in_ordinals176)
                    self.ordinal_set = self.ordinal_set.union(allOrdinals)


                elif alt5 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_ordinal_in_ordinals192)
                    self.ordinal()

                    self._state.following.pop()
                    while True:
                        alt4 = 2
                        LA4_0 = self.input.LA(1)

                        if (LA4_0 == COMMA) :
                            alt4 = 1


                        if alt4 == 1:
                            pass
                            self.match(self.input, COMMA, self.FOLLOW_COMMA_in_ordinals195)
                            self._state.following.append(self.FOLLOW_ordinal_in_ordinals197)
                            self.ordinal()

                            self._state.following.pop()


                        else:
                            break












            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def ordinal(self, ):

        ord = None

        try:
            try:
                pass
                ord = self.input.LT(1)
                if (FIRST <= self.input.LA(1) <= FOURTH_OR_FIFTH):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse



                self.ordinal_set.add(self.ValueOf(ord.type));





            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return


    class period_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)





    def period(self, ):

        retval = self.period_return()
        retval.start = self.input.LT(1)

        try:
            try:
                pass
                if (HOURS <= self.input.LA(1) <= MINUTES):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return retval



    def weekdays(self, ):

        try:
            try:
                pass
                alt7 = 2
                LA7_0 = self.input.LA(1)

                if (LA7_0 == DAY) :
                    alt7 = 1
                elif ((MONDAY <= LA7_0 <= SUNDAY)) :
                    alt7 = 2
                else:
                    nvae = NoViableAltException("", 7, 0, self.input)

                    raise nvae

                if alt7 == 1:
                    pass
                    self.match(self.input, DAY, self.FOLLOW_DAY_in_weekdays280)

                    self.weekday_set = set([self.ValueOf(SUNDAY), self.ValueOf(MONDAY),
                            self.ValueOf(TUESDAY), self.ValueOf(WEDNESDAY),
                            self.ValueOf(THURSDAY), self.ValueOf(FRIDAY),
                            self.ValueOf(SATURDAY), self.ValueOf(SUNDAY)])



                elif alt7 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_weekday_in_weekdays288)
                    self.weekday()

                    self._state.following.pop()
                    while True:
                        alt6 = 2
                        LA6_0 = self.input.LA(1)

                        if (LA6_0 == COMMA) :
                            alt6 = 1


                        if alt6 == 1:
                            pass
                            self.match(self.input, COMMA, self.FOLLOW_COMMA_in_weekdays291)
                            self._state.following.append(self.FOLLOW_weekday_in_weekdays293)
                            self.weekday()

                            self._state.following.pop()


                        else:
                            break












            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def weekday(self, ):

        dayname = None

        try:
            try:
                pass
                dayname = self.input.LT(1)
                if (MONDAY <= self.input.LA(1) <= SUNDAY):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse



                self.weekday_set.add(self.ValueOf(dayname.type))





            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def monthspec(self, ):

        try:
            try:
                pass
                alt8 = 2
                LA8_0 = self.input.LA(1)

                if (LA8_0 == MONTH) :
                    alt8 = 1
                elif ((JANUARY <= LA8_0 <= DECEMBER)) :
                    alt8 = 2
                else:
                    nvae = NoViableAltException("", 8, 0, self.input)

                    raise nvae

                if alt8 == 1:
                    pass
                    self.match(self.input, MONTH, self.FOLLOW_MONTH_in_monthspec373)

                    self.month_set = self.month_set.union(set([
                        self.ValueOf(JANUARY), self.ValueOf(FEBRUARY), self.ValueOf(MARCH),
                        self.ValueOf(APRIL), self.ValueOf(MAY), self.ValueOf(JUNE),
                        self.ValueOf(JULY), self.ValueOf(AUGUST), self.ValueOf(SEPTEMBER),
                        self.ValueOf(OCTOBER), self.ValueOf(NOVEMBER),
                        self.ValueOf(DECEMBER)]))



                elif alt8 == 2:
                    pass
                    self._state.following.append(self.FOLLOW_months_in_monthspec383)
                    self.months()

                    self._state.following.pop()







            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def months(self, ):

        try:
            try:
                pass
                pass
                self._state.following.append(self.FOLLOW_month_in_months400)
                self.month()

                self._state.following.pop()
                while True:
                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if (LA9_0 == COMMA) :
                        alt9 = 1


                    if alt9 == 1:
                        pass
                        self.match(self.input, COMMA, self.FOLLOW_COMMA_in_months403)
                        self._state.following.append(self.FOLLOW_month_in_months405)
                        self.month()

                        self._state.following.pop()


                    else:
                        break









            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def month(self, ):

        monthname = None

        try:
            try:
                pass
                monthname = self.input.LT(1)
                if (JANUARY <= self.input.LA(1) <= DECEMBER):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse


                self.month_set.add(self.ValueOf(monthname.type));




            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def quarterspec(self, ):

        try:
            try:
                pass
                alt10 = 2
                LA10_0 = self.input.LA(1)

                if (LA10_0 == QUARTER) :
                    alt10 = 1
                elif ((FIRST <= LA10_0 <= THIRD)) :
                    alt10 = 2
                else:
                    nvae = NoViableAltException("", 10, 0, self.input)

                    raise nvae

                if alt10 == 1:
                    pass
                    self.match(self.input, QUARTER, self.FOLLOW_QUARTER_in_quarterspec497)

                    self.month_set = self.month_set.union(set([
                        self.ValueOf(JANUARY), self.ValueOf(APRIL), self.ValueOf(JULY),
                        self.ValueOf(OCTOBER)]))


                elif alt10 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_quarter_ordinals_in_quarterspec509)
                    self.quarter_ordinals()

                    self._state.following.pop()
                    self.match(self.input, MONTH, self.FOLLOW_MONTH_in_quarterspec511)
                    self.match(self.input, OF, self.FOLLOW_OF_in_quarterspec513)
                    self.match(self.input, QUARTER, self.FOLLOW_QUARTER_in_quarterspec515)










            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def quarter_ordinals(self, ):

        try:
            try:
                pass
                pass
                self._state.following.append(self.FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals534)
                self.month_of_quarter_ordinal()

                self._state.following.pop()
                while True:
                    alt11 = 2
                    LA11_0 = self.input.LA(1)

                    if (LA11_0 == COMMA) :
                        alt11 = 1


                    if alt11 == 1:
                        pass
                        self.match(self.input, COMMA, self.FOLLOW_COMMA_in_quarter_ordinals537)
                        self._state.following.append(self.FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals539)
                        self.month_of_quarter_ordinal()

                        self._state.following.pop()


                    else:
                        break









            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return



    def month_of_quarter_ordinal(self, ):

        offset = None

        try:
            try:
                pass
                offset = self.input.LT(1)
                if (FIRST <= self.input.LA(1) <= THIRD):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse



                jOffset = self.ValueOf(offset.type) - 1
                self.month_set = self.month_set.union(set([
                    jOffset + self.ValueOf(JANUARY), jOffset + self.ValueOf(APRIL),
                    jOffset + self.ValueOf(JULY), jOffset + self.ValueOf(OCTOBER)]))




            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
        finally:

            pass

        return






    DFA3_eot = DFA.unpack(
        u"\13\uffff"
        )

    DFA3_eof = DFA.unpack(
        u"\13\uffff"
        )

    DFA3_min = DFA.unpack(
        u"\1\6\1\22\1\11\2\4\1\12\2\uffff\1\23\1\11\1\4"
        )

    DFA3_max = DFA.unpack(
        u"\1\17\2\31\1\5\1\11\1\17\2\uffff\2\31\1\11"
        )

    DFA3_accept = DFA.unpack(
        u"\6\uffff\1\1\1\2\3\uffff"
        )

    DFA3_special = DFA.unpack(
        u"\13\uffff"
        )


    DFA3_transition = [
        DFA.unpack(u"\1\1\3\uffff\6\2"),
        DFA.unpack(u"\1\3\7\4"),
        DFA.unpack(u"\1\5\10\uffff\1\3\7\4"),
        DFA.unpack(u"\1\6\1\7"),
        DFA.unpack(u"\1\6\1\7\3\uffff\1\10"),
        DFA.unpack(u"\6\11"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\7\12"),
        DFA.unpack(u"\1\5\10\uffff\1\3\7\4"),
        DFA.unpack(u"\1\6\1\7\3\uffff\1\10")
    ]


    DFA3 = DFA


    FOLLOW_specifictime_in_timespec44 = frozenset([1])
    FOLLOW_interval_in_timespec48 = frozenset([1])
    FOLLOW_ordinals_in_specifictime69 = frozenset([18, 19, 20, 21, 22, 23, 24, 25])
    FOLLOW_weekdays_in_specifictime71 = frozenset([4])
    FOLLOW_OF_in_specifictime74 = frozenset([10, 11, 12, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39])
    FOLLOW_monthspec_in_specifictime77 = frozenset([5])
    FOLLOW_quarterspec_in_specifictime79 = frozenset([5])
    FOLLOW_ordinals_in_specifictime96 = frozenset([18, 19, 20, 21, 22, 23, 24, 25])
    FOLLOW_weekdays_in_specifictime98 = frozenset([5])
    FOLLOW_TIME_in_specifictime112 = frozenset([1])
    FOLLOW_EVERY_in_interval131 = frozenset([7, 8])
    FOLLOW_set_in_interval141 = frozenset([16, 17])
    FOLLOW_period_in_interval157 = frozenset([1])
    FOLLOW_EVERY_in_ordinals176 = frozenset([1])
    FOLLOW_ordinal_in_ordinals192 = frozenset([1, 9])
    FOLLOW_COMMA_in_ordinals195 = frozenset([10, 11, 12, 13, 14, 15])
    FOLLOW_ordinal_in_ordinals197 = frozenset([1, 9])
    FOLLOW_set_in_ordinal218 = frozenset([1])
    FOLLOW_set_in_period257 = frozenset([1])
    FOLLOW_DAY_in_weekdays280 = frozenset([1])
    FOLLOW_weekday_in_weekdays288 = frozenset([1, 9])
    FOLLOW_COMMA_in_weekdays291 = frozenset([18, 19, 20, 21, 22, 23, 24, 25])
    FOLLOW_weekday_in_weekdays293 = frozenset([1, 9])
    FOLLOW_set_in_weekday314 = frozenset([1])
    FOLLOW_MONTH_in_monthspec373 = frozenset([1])
    FOLLOW_months_in_monthspec383 = frozenset([1])
    FOLLOW_month_in_months400 = frozenset([1, 9])
    FOLLOW_COMMA_in_months403 = frozenset([26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38])
    FOLLOW_month_in_months405 = frozenset([1, 9])
    FOLLOW_set_in_month424 = frozenset([1])
    FOLLOW_QUARTER_in_quarterspec497 = frozenset([1])
    FOLLOW_quarter_ordinals_in_quarterspec509 = frozenset([26])
    FOLLOW_MONTH_in_quarterspec511 = frozenset([4])
    FOLLOW_OF_in_quarterspec513 = frozenset([39])
    FOLLOW_QUARTER_in_quarterspec515 = frozenset([1])
    FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals534 = frozenset([1, 9])
    FOLLOW_COMMA_in_quarter_ordinals537 = frozenset([10, 11, 12, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39])
    FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals539 = frozenset([1, 9])
    FOLLOW_set_in_month_of_quarter_ordinal558 = frozenset([1])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from antlr3.main import ParserMain
    main = ParserMain("GrocLexer", GrocParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
