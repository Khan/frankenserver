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
SEPTEMBER=34
FOURTH=13
SECOND=11
WEDNESDAY=20
NOVEMBER=36
SATURDAY=23
JULY=32
APRIL=29
DIGITS=8
OCTOBER=35
MAY=30
EVERY=6
FEBRUARY=27
MONDAY=18
SUNDAY=24
JUNE=31
MARCH=28
OF=4
EOF=-1
JANUARY=26
MONTH=25
FRIDAY=22
FIFTH=14
MINUTES=17
TIME=5
WS=39
QUARTER=38
THURSDAY=21
COMMA=9
DECEMBER=37
AUGUST=33
DIGIT=7
TUESDAY=19
HOURS=16
FIRST=10
FOURTH_OR_FIFTH=15

tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "OF", "TIME", "EVERY", "DIGIT", "DIGITS", "COMMA", "FIRST", "SECOND",
    "THIRD", "FOURTH", "FIFTH", "FOURTH_OR_FIFTH", "HOURS", "MINUTES", "MONDAY",
    "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
    "MONTH", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
    "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER", "QUARTER",
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
                    elif ((MONDAY <= LA1_1 <= SUNDAY)) :
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
                pass
                pass
                pass
                self._state.following.append(self.FOLLOW_ordinals_in_specifictime69)
                self.ordinals()

                self._state.following.pop()
                self._state.following.append(self.FOLLOW_weekdays_in_specifictime71)
                self.weekdays()

                self._state.following.pop()






                self.match(self.input, OF, self.FOLLOW_OF_in_specifictime75)
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
                    self._state.following.append(self.FOLLOW_monthspec_in_specifictime78)
                    self.monthspec()

                    self._state.following.pop()


                elif alt2 == 2:
                    pass
                    self._state.following.append(self.FOLLOW_quarterspec_in_specifictime80)
                    self.quarterspec()

                    self._state.following.pop()






                TIME1=self.match(self.input, TIME, self.FOLLOW_TIME_in_specifictime93)
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
                self.match(self.input, EVERY, self.FOLLOW_EVERY_in_interval112)
                intervalnum = self.input.LT(1)
                if (DIGIT <= self.input.LA(1) <= DIGITS):
                    self.input.consume()
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse



                self.interval_mins = int(intervalnum.text)

                self._state.following.append(self.FOLLOW_period_in_interval138)
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
                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == EVERY) :
                    alt4 = 1
                elif ((FIRST <= LA4_0 <= FOURTH_OR_FIFTH)) :
                    alt4 = 2
                else:
                    nvae = NoViableAltException("", 4, 0, self.input)

                    raise nvae

                if alt4 == 1:
                    pass
                    self.match(self.input, EVERY, self.FOLLOW_EVERY_in_ordinals157)
                    self.ordinal_set = self.ordinal_set.union(allOrdinals)


                elif alt4 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_ordinal_in_ordinals173)
                    self.ordinal()

                    self._state.following.pop()
                    while True:
                        alt3 = 2
                        LA3_0 = self.input.LA(1)

                        if (LA3_0 == COMMA) :
                            alt3 = 1


                        if alt3 == 1:
                            pass
                            self.match(self.input, COMMA, self.FOLLOW_COMMA_in_ordinals176)
                            self._state.following.append(self.FOLLOW_ordinal_in_ordinals178)
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
                pass
                self._state.following.append(self.FOLLOW_weekday_in_weekdays261)
                self.weekday()

                self._state.following.pop()
                while True:
                    alt5 = 2
                    LA5_0 = self.input.LA(1)

                    if (LA5_0 == COMMA) :
                        alt5 = 1


                    if alt5 == 1:
                        pass
                        self.match(self.input, COMMA, self.FOLLOW_COMMA_in_weekdays264)
                        self._state.following.append(self.FOLLOW_weekday_in_weekdays266)
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
                alt6 = 2
                LA6_0 = self.input.LA(1)

                if (LA6_0 == MONTH) :
                    alt6 = 1
                elif ((JANUARY <= LA6_0 <= DECEMBER)) :
                    alt6 = 2
                else:
                    nvae = NoViableAltException("", 6, 0, self.input)

                    raise nvae

                if alt6 == 1:
                    pass
                    self.match(self.input, MONTH, self.FOLLOW_MONTH_in_monthspec344)

                    self.month_set = self.month_set.union(set([
                        self.ValueOf(JANUARY), self.ValueOf(FEBRUARY), self.ValueOf(MARCH),
                        self.ValueOf(APRIL), self.ValueOf(MAY), self.ValueOf(JUNE),
                        self.ValueOf(JULY), self.ValueOf(AUGUST), self.ValueOf(SEPTEMBER),
                        self.ValueOf(OCTOBER), self.ValueOf(NOVEMBER),
                        self.ValueOf(DECEMBER)]))



                elif alt6 == 2:
                    pass
                    self._state.following.append(self.FOLLOW_months_in_monthspec354)
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
                self._state.following.append(self.FOLLOW_month_in_months371)
                self.month()

                self._state.following.pop()
                while True:
                    alt7 = 2
                    LA7_0 = self.input.LA(1)

                    if (LA7_0 == COMMA) :
                        alt7 = 1


                    if alt7 == 1:
                        pass
                        self.match(self.input, COMMA, self.FOLLOW_COMMA_in_months374)
                        self._state.following.append(self.FOLLOW_month_in_months376)
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
                alt8 = 2
                LA8_0 = self.input.LA(1)

                if (LA8_0 == QUARTER) :
                    alt8 = 1
                elif ((FIRST <= LA8_0 <= THIRD)) :
                    alt8 = 2
                else:
                    nvae = NoViableAltException("", 8, 0, self.input)

                    raise nvae

                if alt8 == 1:
                    pass
                    self.match(self.input, QUARTER, self.FOLLOW_QUARTER_in_quarterspec468)

                    self.month_set = self.month_set.union(set([
                        self.ValueOf(JANUARY), self.ValueOf(APRIL), self.ValueOf(JULY),
                        self.ValueOf(OCTOBER)]))


                elif alt8 == 2:
                    pass
                    pass
                    self._state.following.append(self.FOLLOW_quarter_ordinals_in_quarterspec480)
                    self.quarter_ordinals()

                    self._state.following.pop()
                    self.match(self.input, MONTH, self.FOLLOW_MONTH_in_quarterspec482)
                    self.match(self.input, OF, self.FOLLOW_OF_in_quarterspec484)
                    self.match(self.input, QUARTER, self.FOLLOW_QUARTER_in_quarterspec486)










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
                self._state.following.append(self.FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals505)
                self.month_of_quarter_ordinal()

                self._state.following.pop()
                while True:
                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if (LA9_0 == COMMA) :
                        alt9 = 1


                    if alt9 == 1:
                        pass
                        self.match(self.input, COMMA, self.FOLLOW_COMMA_in_quarter_ordinals508)
                        self._state.following.append(self.FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals510)
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







    FOLLOW_specifictime_in_timespec44 = frozenset([1])
    FOLLOW_interval_in_timespec48 = frozenset([1])
    FOLLOW_ordinals_in_specifictime69 = frozenset([18, 19, 20, 21, 22, 23, 24])
    FOLLOW_weekdays_in_specifictime71 = frozenset([4])
    FOLLOW_OF_in_specifictime75 = frozenset([10, 11, 12, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38])
    FOLLOW_monthspec_in_specifictime78 = frozenset([5])
    FOLLOW_quarterspec_in_specifictime80 = frozenset([5])
    FOLLOW_TIME_in_specifictime93 = frozenset([1])
    FOLLOW_EVERY_in_interval112 = frozenset([7, 8])
    FOLLOW_set_in_interval122 = frozenset([16, 17])
    FOLLOW_period_in_interval138 = frozenset([1])
    FOLLOW_EVERY_in_ordinals157 = frozenset([1])
    FOLLOW_ordinal_in_ordinals173 = frozenset([1, 9])
    FOLLOW_COMMA_in_ordinals176 = frozenset([10, 11, 12, 13, 14, 15])
    FOLLOW_ordinal_in_ordinals178 = frozenset([1, 9])
    FOLLOW_set_in_ordinal199 = frozenset([1])
    FOLLOW_set_in_period238 = frozenset([1])
    FOLLOW_weekday_in_weekdays261 = frozenset([1, 9])
    FOLLOW_COMMA_in_weekdays264 = frozenset([18, 19, 20, 21, 22, 23, 24])
    FOLLOW_weekday_in_weekdays266 = frozenset([1, 9])
    FOLLOW_set_in_weekday285 = frozenset([1])
    FOLLOW_MONTH_in_monthspec344 = frozenset([1])
    FOLLOW_months_in_monthspec354 = frozenset([1])
    FOLLOW_month_in_months371 = frozenset([1, 9])
    FOLLOW_COMMA_in_months374 = frozenset([25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37])
    FOLLOW_month_in_months376 = frozenset([1, 9])
    FOLLOW_set_in_month395 = frozenset([1])
    FOLLOW_QUARTER_in_quarterspec468 = frozenset([1])
    FOLLOW_quarter_ordinals_in_quarterspec480 = frozenset([25])
    FOLLOW_MONTH_in_quarterspec482 = frozenset([4])
    FOLLOW_OF_in_quarterspec484 = frozenset([38])
    FOLLOW_QUARTER_in_quarterspec486 = frozenset([1])
    FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals505 = frozenset([1, 9])
    FOLLOW_COMMA_in_quarter_ordinals508 = frozenset([10, 11, 12, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38])
    FOLLOW_month_of_quarter_ordinal_in_quarter_ordinals510 = frozenset([1, 9])
    FOLLOW_set_in_month_of_quarter_ordinal529 = frozenset([1])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from antlr3.main import ParserMain
    main = ParserMain("GrocLexer", GrocParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
