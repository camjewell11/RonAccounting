import config, datetime, pandas

class shift():
    def __init__(self):
        self._subShift = []
        self._error = ""
        self._weekDay = 0
        self._double = False
        self._overtime = False
        self._unpaidTips = 0

    # default "constructor" for shift
    def construct(self, name, data, shiftNum, baseRate=None, hoursTillNow=0):
        self._name = name
        self._job = data["job"][shiftNum]
        self._baseRate = baseRate
        self._hoursTillNow = hoursTillNow

        self._tips = data["tips"][shiftNum]
        self._rawTips = self._tips

        self._rawStartTime = data["start"][shiftNum]
        self._rawEndTime = data["end"][shiftNum]
        self._hours = self.getTime(self._rawStartTime, self._rawEndTime)
        self._hoursTillNow += self._hours
        self._rate = self.checkRate(data["rate"][shiftNum])

        if pandas.isnull(self._tips):
            self._tips = 0
            self._rawTips = 0
        self.shiftPostProcessing()

    # "constructor" used when splitting shifts
    def subShift(self, name, job, start, midPoint, end, rate, baseRate, tips, hoursTillNow):
        self._name = name
        self._job = job
        self._hoursTillNow = hoursTillNow
        self._baseRate = baseRate

        self._rawTips = 0
        self._tips = tips

        self._rawStartTime = start
        self._rawEndTime = end
        self._hours = self.getTime(midPoint, self._rawEndTime)
        self._hoursTillNow += self._hours
        self._rate = self.checkRate(rate)

        if pandas.isnull(self._tips):
            self._tips = 0
        self.shiftPostProcessing()

    # reads raw input time and adjusts for clock errors and subshifts
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
                # special case for 1st of month rollback
                if int(endTime[3:5])-1 == 0:
                    tempTime = pandas.to_datetime(endTime)
                    yesterday = tempTime - datetime.timedelta(days = 1)
                    endTime = str(yesterday.month).zfill(2) + "/" + str(yesterday.day) + endTime[5:-7] + "10:00PM"
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

        # double shift
        if totalTime > 10:
            self._error += "Worked a double.\n"
            midpoint = start[:-7] + "02:00PM"
            self._endTime = midpoint
            self._subShift = [self._job, self._rawStartTime, midpoint, self._rawEndTime, self._rawTips, self._tips]
            self._double = True

            # rare case where double started after noon
            # set first portion of double to morning shift regardless of start time
            self._morningShift = True

            # split shift in two; designated midpoint for subshift to be created
            midpoint = pandas.to_datetime(midpoint)
            secondHalf = (endTime-midpoint) / datetime.timedelta(hours=1)
            totalTime -= secondHalf

        return totalTime

    # ensures correct rate is being paid when clock-in/out not proper
    def checkRate(self, rate):
        # hours including shift > 40, but overtime not applied
        if self._hoursTillNow > 40 and rate != self._baseRate * 1.5:
            self._error = "Overtime mismatch. Not awarded overtime for working 40+ hours.\n"
            # applied only to subshift split from overtime calculation
            if self._hoursTillNow - self._hours == 40:
                self._error = "Adjusted rate to overtime rate."
                rate = self._baseRate * 1.5
            else:
                midpoint = pandas.to_datetime(self._startTime)
                midpoint += datetime.timedelta(hours=(self._hours - (self._hoursTillNow - 40)))
                midpoint = datetimeToDateString(midpoint)
                self._endTime = midpoint

                self._hoursTillNow = 40
                self._subShift = [self._job, self._rawStartTime, midpoint, self._rawEndTime, self._rawTips, self._tips]

        # hours inclding shift < 40 and overtime being wrongly applied
        elif self._hoursTillNow < 40 and self._baseRate != None and rate == self._baseRate * 1.5:
            self._error = "Overtime mismatch. Overtime awarded under 40 hours.\n"
            rate = self._baseRate
            newHours = self._hoursTillNow + self._hours
            if newHours > 40:
                rate = self._baseRate * 1.5

        # correctly applying overtime
        elif self._hoursTillNow > 40 and rate == self._baseRate * 1.5:
            self._error = "Overtime."
            self._overtime = True
        # normal shift
        else:
            self._baseRate = rate

        return rate

    # returns true if job title contains keyword in ignoredWorkers list
    def jobIsIgnored(self):
        for ignoredJob in config.ignoredTipsWorkers:
            if ignoredJob in self._job:
                return True
        return False

    # returns false if shift attributes match shift in config file
    def shiftIsIgnored(self):
        for shift in config.ignoredShifts:
            if self._name == shift["worker"] and shift["date"] in self._startTime:
                if self.isMorningShift and shift["shift"] == "AM" or self.isAfternoonShift and shift["shift"] == "PM":
                    return True
        # ignore shifts that start at 4am and end at 4am
        if pandas.to_datetime(self._rawStartTime).hour == 4 and pandas.to_datetime(self._rawEndTime).hour == 4:
            if self._job != "Manager" and self._tips == 0:
                return True
        return False

    # if shift doesn't earn tips, store tips in another variable for output
    def shiftPostProcessing(self):
        if self.shiftIsIgnored():
            self._unpaidTips = self._tips

    # used to calculate tips split
    def isMorningShift(self):
        return self._morningShift
    def isAfternoonShift(self):
        return self._afternoonShift

    # used to determine if awarded tips for shift
    def isFOH(self):
        return True if self._job in config.frontOfHouseJobs else False
    def isBOH(self):
        return True if self._job in config.backOfHouseJobs  else False
    def isReception(self):
        return True if self._job in config.receptionJobs    else False
    def isManager(self):
        return True if self._job in config.managerJobs      else False

    # returns location for use in output
    def getLocation(self):
        if self.isFOH():
            return "FOH"
        elif self.isBOH():
            return "BOH"
        elif self.isReception():
            return "Reception"
        elif self.isManager():
            return "Manager"

# converts datetime object to string "mm/dd/yyyy hh:mm?M"
def datetimeToDateString(point):
    dateString = point._repr_base[5:-3].replace("-","/")
    dateString = dateString[:2] + dateString[2:5].replace("/" + str(point.day), "/" + str(point.day)+ "/" + str(point.year)) + dateString[5:]
    if point.hour > 12:
        dateString = dateString[:11] + dateString[11:13].replace(str(point.hour), str(point.hour % 12).zfill(2)) + dateString[13:]
        dateString += "PM"
    else:
        dateString += "AM"

    return dateString