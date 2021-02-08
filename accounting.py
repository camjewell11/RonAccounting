import pandas
import Worker

dataFile = "Data/payroll.xlsx"
specialTips = [ "CLINT BROWN", "DOUG", "Comp" ]

# pulls raw data from excel file
def getDataFromFile(fileName):
    xls = pandas.ExcelFile(fileName)
    dataFromFile = xls.parse(xls.sheet_names[0]).to_dict()
    return dataFromFile

# pulls out relevant columns from excel sheet
def trimFileData(fileData):
    data = {}

    data["name"]    = list(fileData["Employee Name"].values())
    data["job"]     = list(fileData["Job"].values())
    data["working"] = list(fileData["Shift/Break"].values())
    data["start"]   = list(fileData["Shift Start"].values())
    data["end"]     = list(fileData["Shift End"].values())
    data["rate"]    = list(fileData["$ Rate"].values())
    data["tips"]    = list(fileData["$ Total Tips"].values())

    return data

# timecard entries are stored on two rows for non-overtime; combine 'em
def consolidateData(data):
    for entry in range(len(data["name"])-1):
        if data["start"][entry] == data["start"][entry+1] and data["end"][entry] == data["end"][entry+1]:
            if data["working"][entry] == "Shift":
                data["tips"][entry] = data["tips"][entry+1]
            else:
                data["tips"][entry+1] = data["tips"][entry]
    return data

# creates a list of worker data types for processing
def createWorkers(data):
    workers = []
    startRow = 0
    endRow = 0
    for x in range(len(data["name"])):
        if type(data["name"][x]) is str:
            if x > 0:
                endRow = x
                newWorker = Worker.worker(data, startRow, endRow)
                workers.append(newWorker)
                startRow = x
            else:
                startRow = x
    # ignore "Grand Total"
    # workers.append(worker(data, startRow, len(data["name"])))

    return workers

# calculates pay for each worker
def calculateTotals(workers):
    for worker in workers:
        weeklyPay = 0
        # calculates wage totals per shift
        for day in worker._workShifts:
            for shift in day:
                if shift != None:
                    weeklyPay += shift._rate*shift._hours
        worker.setPreTipWage(weeklyPay)
    return workers

# sums tips per shift by day of the week
def calculateTotalTipsPerShift(workers):
    morningTipsByDay   = [0,0,0,0,0,0,0]
    afternoonTipsByDay = [0,0,0,0,0,0,0]
    for worker in workers:
        # sum tips per day
        for day in worker._workShifts:
            for shift in day:
                if shift.isMorningShift():
                    morningTipsByDay[shift._weekDay] += shift._tips
                elif shift.isAfternoonShift():
                    afternoonTipsByDay[shift._weekDay] += shift._tips
    return [morningTipsByDay, afternoonTipsByDay]

def calculateWorkersPerShift(workers):
    morningWorkersPerDay   = [0,0,0,0,0,0,0]
    afternoonWorkersPerDay = [0,0,0,0,0,0,0]
    for worker in workers:
        mShifts = [0,0,0,0,0,0,0]
        aShifts = [0,0,0,0,0,0,0]
        # count number of workers per shift per day
        for day in range(len(worker._staffed)):
            for shift in worker._workShifts[day]:
                if shift.isMorningShift() and not shift.jobIsIgnored(shift._job):
                    mShifts[day] +=1
                elif shift.isAfternoonShift() and not shift.jobIsIgnored(shift._job):
                    aShifts[day] +=1

        for day in range(len(mShifts)):
            if mShifts[day] != 0:
                morningWorkersPerDay[day] += 1
        for day in range(len(aShifts)):
            if aShifts[day] != 0:
                afternoonWorkersPerDay[day] += 1
    return [morningWorkersPerDay, afternoonWorkersPerDay]

# adds wages and tips at the hourly rate for each worker
def calculatePayroll(workers, morningTips, afternoonTips, morningWorkers, afternoonWorkers):
    for worker in workers:
        totalPay = worker._wage
        # only count tips when working and allowed tips
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isMorningShift() and not shift.jobIsIgnored(shift._job):
                    totalPay += morningTips[day] / morningWorkers[day]
                elif shift.isAfternoonShift() and not shift.jobIsIgnored(shift._job):
                    totalPay += afternoonTips[day] / afternoonWorkers[day]
        worker.setPostTipWage(totalPay)

# writes corrected output to file
def generateOutput(workers):
    pass

# main
def run():
    rawData = getDataFromFile(dataFile)
    trimmedData = trimFileData(rawData)
    usefulData = consolidateData(trimmedData)

    workers = createWorkers(usefulData)
    workers = calculateTotals(workers)

    mTips,aTips = calculateTotalTipsPerShift(workers)
    mWorkers, aWorkers = calculateWorkersPerShift(workers)
    calculatePayroll(workers, mTips, aTips, mWorkers, aWorkers)
    generateOutput(workers)

if __name__=="__main__":
    run()