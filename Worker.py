import pandas, Shift

class worker():
    def __init__(self, data, startRow, endRow):
        self._weeklyHours = 0
        self._name = data["name"][startRow]
        self._workShifts = [[], [], [], [], [], [], []]
        self._FOHwage = 0
        self._BOHwage = 0
        self._RECwage = 0
        self._FOHhours = 0
        self._BOHhours = 0
        self._REChours = 0

        data = trimData(data, startRow, endRow)
        data = workerPreProcessing(data)
        self.getWorkDays(data)
        self.workerPostProcessing()

    # creates Shift objects with relevant data
    def getWorkDays(self, data):
        for x in range(len(data["working"])):
            hoursTillNow = self._weeklyHours
            newDay = Shift.shift()
            if x == 0:
                newDay.construct(self._name, data, x)
                self._baseRate = newDay._rate
            else:
                newDay.construct(self._name, data, x, self._baseRate, hoursTillNow)
            hoursTillNow += newDay._hours

            # add shift to worker if not ignored by config file
            if not newDay.shiftIsIgnored():
                self._workShifts[newDay._weekDay].append(newDay)
                self._weeklyHours += newDay._hours

            # if shift split by overtime or double
            if newDay._subShift != []:
                newShift = Shift.shift()
                newShift.subShift(self._name, newDay._subShift[0], newDay._subShift[1], newDay._subShift[2], newDay._subShift[3], newDay._rate, newDay._baseRate, 0, newDay._hoursTillNow)
                # add shift to worker if not ignored by config file
                if not newShift.shiftIsIgnored():
                    self._workShifts[newShift._weekDay].append(newShift)
                    self._weeklyHours += newShift._hours

    # set unadjusted tips, set unpaid tips
    def workerPostProcessing(self):
        tips = 0
        unpaidTips = 0
        for day in self._workShifts:
            for shift in day:
                tips += shift._tips
                if shift.shiftIsIgnored():
                    unpaidTips += shift._unpaidTips
        self._tips = tips
        self._unpaidTips = unpaidTips

    def setPreTipWage(self, weeklyPay): # pay before tips
        self._wage = weeklyPay
    def setPostTipWage(self, postTipWage): # pay with adjusted tips
        self._pay = postTipWage

# removes all data without Shift tag in data
def trimData(data, start, end):
    trimmedData = {}
    workingTitle = ""
    for entry in data:
        trimmedData[entry] = []
        for x in range(start, end):
            if type(data["job"][x]) is str:
                workingTitle = data["job"][x]
            elif data["working"][x] == "Shift":
                if entry == "job":
                    trimmedData[entry].append(workingTitle)
                else:
                    trimmedData[entry].append(data[entry][x])
    return trimmedData

# reorders shifts chronologically before processing
def workerPreProcessing(data):
    startTimes = []
    for attribute in data["start"]:
        startTimes.append(pandas.to_datetime(attribute))

    indices = [*range(len(startTimes))]
    indices = [x for _,x in sorted(zip(startTimes, indices))]
    for key,list in data.items():
        data[key] = [x for _,x in sorted(zip(startTimes, list))]

    return data