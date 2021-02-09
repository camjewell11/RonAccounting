import config, datetime, pandas

class shift():
    def __init__(self):
        pass

    # default "constructor" for shift
    def construct(self, name, data, shiftNum, baseRate=None, hoursTillNow=0):
        self._name = name
        self._subShift = []
        self._error = ""
        self._job = data["job"][shiftNum]
        self._baseRate = baseRate
        self._hoursTillNow = hoursTillNow
        self._weekDay = 0
        self._double = False

        self._tips = data["tips"][shiftNum]
        self._rawTips = self._tips
        self._unpaidTips = 0

        self._rawStartTime = data["start"][shiftNum]
        self._rawEndTime = data["end"][shiftNum]
        self._hours = self.getTime(self._rawStartTime, self._rawEndTime)
        self._hoursTillNow += self._hours
        self._rate = self.checkRate(data["rate"][shiftNum])

        if pandas.isnull(self._tips):
            self._tips = 0
        self.postProcessing()

    # "constructor" used when splitting shifts
    def subShift(self, name, job, start, midPoint, end, rate, baseRate, tips, hoursTillNow):
        self._name = name
        self._subShift = []
        self._error = ""
        self._job = job
        self._hoursTillNow = hoursTillNow
        self._baseRate = baseRate
        self._weekDay = 0
        self._double = False

        self._rawTips = 0
        self._tips = tips
        self._unpaidTips = 0

        self._rawStartTime = start
        self._rawEndTime = end
        self._hours = self.getTime(midPoint, self._rawEndTime)
        self._hoursTillNow += self._hours
        self._rate = self.checkRate(rate)

        if pandas.isnull(self._tips):
            self._tips = 0
        self.postProcessing()

    def getTime(self, startTime, endTime):
        start = startTime
        # convert clock-in error to 9AM
        if "4:00AM" in startTime:
            startTime = startTime[:-7] + "9:00AM"
            self._error = "Didn't clock out previous shift (4:00AM).\n"
        self._startTime = startTime
        startTime = pandas.to_datetime(startTime)
        if "4:00AM" in endTime:
            # convert clock-out error to 3PM (morning shift)
            if startTime.hour < 12:
                endTime = endTime[:-7] + "3:00PM"
                self._error = "Didn't clock out afternoon (4:00AM).\n"
            # convert clock-out error to 10PM (afternoon shift)
            else:
                endTime = endTime[:3] + str(int(endTime[3:5])-1) + endTime[5:-7] + "10:00PM"
                self._error = "Didn't clock out evening (4:00AM).\n"
        self._endTime = endTime
        endTime = pandas.to_datetime(endTime)

        # set morning shift or afternoon shift based on time
        if startTime.hour < 12:
            self._morningShift = True
            self._afternoonShift = False
        else:
            self._morningShift = False
            self._afternoonShift = True

        self._weekDay = startTime.dayofweek
        totalTime = (endTime-startTime) / datetime.timedelta(hours=1)

        if totalTime > 10:
            tips = self._tips
            self._error += "Worked a double.\n"
            midpoint = start[:-7] + "02:00PM"
            self._endTime = midpoint
            self._subShift = [self._job, self._rawStartTime, midpoint, self._rawEndTime, self._rawTips, tips]
            self._double = True

            # split shift in two; designated midpoint for subshift to be created
            midpoint = pandas.to_datetime(midpoint)
            secondHalf = (endTime-midpoint) /datetime.timedelta(hours=1)
            totalTime -= secondHalf

        return totalTime

    # ensures correct rate is being paid when clock-in/out not proper
    def checkRate(self, rate):
        if self._hoursTillNow > 40 and rate != self._baseRate * 1.5:
            self._error = "Overtime mismatch. Not awarded overtime for working 40+ hours.\n"
            rate = self._baseRate * 1.5
        elif self._baseRate != None and self._hoursTillNow < 40 and rate != self._baseRate:
            if rate == self._baseRate * 1.5:
                self._error = "Overtime mismatch. Overtime awarded under 40 hours.\n"
                rate = self._baseRate
                newHours = self._hoursTillNow + self._hours
                if newHours > 40:
                    rate = self._baseRate * 1.5
                # self._subShift = [self._job, self._rawStartTime, self._rawStartTime, self._rawEndTime, 0]
        elif self._hoursTillNow > 40 and rate == self._baseRate * 1.5:
            self._error = "Overtime."
        else:
            self._baseRate = rate
        return rate

    # returns true if job title contains keyword in ignoredWorkers list
    def jobIsIgnored(self):
        for ignoredJob in config.ignoredTipsWorkers:
            if ignoredJob in self._job.lower():
                return True
        return False

    # returns false if shift attributes match shift in config file
    def shiftIsIgnored(self):
        for shift in config.ignoredShifts:
            if self._name == shift["worker"] and shift["date"] in self._startTime:
                if self.isMorningShift and shift["shift"] == "AM":
                    return True
                elif self.isAfternoonShift and shift["shift"] == "PM":
                    return True
        return False

    # if shift doesn't earn tips, store tips in another variable for output
    def postProcessing(self):
        if self.shiftIsIgnored():
            self._unpaidTips = self._tips

    # used to calculate tips split
    def isMorningShift(self):
        return self._morningShift
    def isAfternoonShift(self):
        return self._afternoonShift

    # used to determine if awarded tips for shift
    def isFOH(self):
        if self._job in config.frontOfHouseJobs:
            return True
        return False
    def isBOH(self):
        if self._job in config.backOfHouseJobs:
            return True
        return False
    def isReception(self):
        if self._job in config.receptionJobs:
            return True
        return False
    def isManager(self):
        if self._job in config.managerJobs:
            return True
        return False