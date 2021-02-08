import Shift

class worker():
    def __init__(self, data, startRow, endRow):
        self._weeklyHours = 0
        self._name = data["name"][startRow]
        self._workShifts = [[], [], [], [], [], [], []]

        data = self.trimData(data, startRow, endRow)
        self.getWorkDays(data)
        # self.postProcessing()

    # removes all data without Shift tag in data
    def trimData(self, data, start, end):
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

    # creates Shift objects with relevant data
    def getWorkDays(self, data):
        for x in range(len(data["working"])):
            if x == 0:
                newDay = Shift.shift()
                newDay.construct(self._name, data, x)
                baseRate = newDay._rate
                hoursTillNow = newDay._hours
            else:
                newDay = Shift.shift()
                newDay.construct(self._name, data, x, baseRate, hoursTillNow)
                hoursTillNow += newDay._hours

            # add shift to worker if not ignored by config file
            if not newDay.shiftIsIgnored():
                self._workShifts[newDay._weekDay].append(newDay)
                self._weeklyHours += newDay._hours

            if newDay._subShift != []:
                newShift = Shift.shift()
                newShift.subShift(self._name, newDay._subShift[0], newDay._subShift[1], newDay._subShift[2], newDay._rate, newDay._baseRate, newDay._tips, newDay._hoursTillNow)
                # add shift to worker if not ignored by config file
                if not newShift.shiftIsIgnored():
                    self._workShifts[newShift._weekDay].append(newShift)
                    self._weeklyHours += newShift._hours

    def setPreTipWage(self, weeklyPay):
        self._wage = weeklyPay
    def setPostTipWage(self, postTipWage):
        self._pay = postTipWage