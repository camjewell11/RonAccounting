import Shift

class worker():
    def __init__(self, data, startRow, endRow):
        self._weeklyHours = 0
        self._name = data["name"][startRow]
        self._workShifts = [[], [], [], [], [], [], []]
        self._staffed = [False, False, False, False, False, False, False]

        data = self.trimData(data, startRow, endRow)
        self.getWorkDays(data)

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

    def getWorkDays(self, data):
        for x in range(len(data["working"])):
            if x == 0:
                newDay = Shift.shift(data, x)
                baseRate = newDay._rate
                hoursTillNow = newDay._hours
            else:
                newDay = Shift.shift(data, x, baseRate, hoursTillNow)
                hoursTillNow += newDay._hours
            self._workShifts[newDay._weekDay].append(newDay)
            self._weeklyHours += newDay._hours
            self._staffed[newDay._weekDay] = True

    def setPreTipWage(self, weeklyPay):
        self._wage = weeklyPay
    def setPostTipWage(self, postTipWage):
        self._pay = postTipWage