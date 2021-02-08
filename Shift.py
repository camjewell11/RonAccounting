import datetime, pandas

ignoredWorkers = [ "cook", "reception", "manager", "mezzanine server" ]

class shift():
    def __init__(self, data, shiftNum, baseRate=None, hoursTillNow=0):
        self._subshift = []
        self._error = ""
        self._job = data["job"][shiftNum]
        self._hoursTillNow = hoursTillNow
        self._tipableHours = 0
        self._weekDay = 0

        startTime = data["start"][shiftNum]
        endTime = data["end"][shiftNum]
        self._hours = self.getTime(startTime, endTime)
        self._hoursTillNow += self._hours

        self._rate = self.checkRate(data["rate"][shiftNum], baseRate)
        self._tips = data["tips"][shiftNum]
        if pandas.isnull(self._tips):
            self._tips = 0

        if self._error == '':
            self._error = False

    def getTime(self, start, end):
        # convert clock-in error to 9AM
        if "4:00AM" in start:
            start = start[:-7] + "9:00AM"
            self._error = "Didn't clock out previous shift (4:00AM)."
        start = pandas.to_datetime(start)
        if "4:00AM" in end:
            # convert clock-out error to 3PM (morning shift)
            if start.hour < 12:
                end = end[:-7] + "3:00PM"
                self._error = "Didn't clock out afternoon (4:00AM)."
            # convert clock-out error to 10PM (afternoon shift)
            else:
                end = end[:3] + str(int(end[3:5])-1) + end[5:-7] + "10:00PM"
                self._error = "Didn't clock out evening (4:00AM)."
        end = pandas.to_datetime(end)

        # set morning shift or afternoon shift based on time
        if start.hour < 12:
            self._morningShift = True
            self._afternoonShift = False
        else:
            self._morningShift = False
            self._afternoonShift = True

        self._weekDay = start.dayofweek
        totalTime = (end-start) / datetime.timedelta(hours=1)
        return totalTime

    # ensures correct rate is being paid when clock-in/out not proper
    def checkRate(self, rate, baseRate):
        if self._hoursTillNow > 40 and rate != baseRate * 1.5:
            self._error = "Overtime mismatch. Not awarded overtime for working 40+ hours."
            rate = baseRate * 1.5
        elif baseRate != None and self._hoursTillNow < 40 and rate != baseRate:
            if rate == baseRate * 1.5:
                self._error = "Overtime mismatch. Overtime awarded under 40 hours."
                rate = baseRate
                newHours = self._hoursTillNow + self._hours
                if newHours > 40:
                    self._subshift.append(newHours-40)
        return rate

    # returns true if job title contains keyword in ignoredWorkers list
    def jobIsIgnored(self, job):
        for ignoredJob in ignoredWorkers:
            if ignoredJob in job.lower():
                return True
        return False

    def isMorningShift(self):
        return self._morningShift

    def isAfternoonShift(self):
        return self._afternoonShift