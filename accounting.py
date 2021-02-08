import copy, json, pandas
import Worker
from tkinter import Tk
from tkinter.filedialog import askopenfilename

dataFile = "Data/payroll.xlsx"

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

# if clock-in/out changes are made that affect rate due to overtime,
# recreate shifts and pay calculations for corrected shifts;
# adjust tips based on double shifts
def postProcessing(workers):
    for worker in workers:
        for day in range(len(worker._workShifts)):
            for shift in range(len(worker._workShifts[day])-1):
                # double shift
                if worker._workShifts[day][shift]._double and not worker._workShifts[day][shift].jobIsIgnored():
                    coworkers = findCoworkers(workers, worker._workShifts[day][shift])

    return workers

# calculates pay for each worker
def calculateTotals(workers):
    for worker in workers:
        weeklyPay = 0
        # calculates wage totals per shift per day
        for day in worker._workShifts:
            for shift in day:
                if shift != None:
                    weeklyPay += shift._rate*shift._hours
        worker.setPreTipWage(weeklyPay)

# sums tips per shift by day of the week
def calculateTotalTipsPerShift(workers):
    morningTipsByDay   = [0,0,0,0,0,0,0]
    afternoonTipsByDay = [0,0,0,0,0,0,0]
    for worker in workers:
        # sum tips per shift per day
        for day in worker._workShifts:
            for shift in day:
                if shift.isMorningShift():
                    morningTipsByDay[shift._weekDay] += shift._tips
                elif shift.isAfternoonShift():
                    afternoonTipsByDay[shift._weekDay] += shift._tips

    return morningTipsByDay, afternoonTipsByDay

# checks all shifts against config for ignored positions and counts workers per shift
def calculateWorkersPerShift(workers):
    morningWorkersPerDay   = [0,0,0,0,0,0,0]
    afternoonWorkersPerDay = [0,0,0,0,0,0,0]
    for worker in workers:
        mShifts = [0,0,0,0,0,0,0]
        aShifts = [0,0,0,0,0,0,0]
        # count number of workers per shift per day
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isMorningShift() and not shift.jobIsIgnored():
                    mShifts[day] +=1
                elif shift.isAfternoonShift() and not shift.jobIsIgnored():
                    aShifts[day] +=1

        # workers can have more than one shift object per object (overtime, clock-int/out,
        # breaks), but only increment once per shift counter
        for day in range(len(mShifts)):
            if mShifts[day] != 0:
                morningWorkersPerDay[day] += 1
        for day in range(len(aShifts)):
            if aShifts[day] != 0:
                afternoonWorkersPerDay[day] += 1

    return morningWorkersPerDay, afternoonWorkersPerDay

# adds wages and tips at the hourly rate for each worker
def calculatePayroll(workers, morningTips, afternoonTips, morningWorkers, afternoonWorkers):
    for worker in workers:
        totalPay = worker._wage
        totalTips = 0
        # only count tips when working and allowed tips
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isMorningShift() and not shift.jobIsIgnored():
                    totalTips += morningTips[day] / morningWorkers[day]
                elif shift.isAfternoonShift() and not shift.jobIsIgnored():
                    totalTips += afternoonTips[day] / afternoonWorkers[day]
        worker._tips = totalTips
        worker.setPostTipWage(totalPay + totalTips)
    return workers

# split workers by day
def sortWorkersByDay(workers):
    return workers

# returns list of shifts on same day as provided shift
def findCoworkers(workers, findShift):
    coworkers = []
    for worker in workers:
        for day in worker._workShifts:
            for shift in day:
                # shift isn't self and is same time of day
                if shift != findShift and shift._morningShift == findShift._morningShift:
                    if shift._startTime[10:] == findShift._startTime[10:] and not shift.jobIsIgnored():
                        coworkers.append(shift)
    return coworkers

# split FOH, BOH, and reception into their own lists
# workers that worked both reception and bar have their shifts split into FOH and BOH
def sortWorkersByLocation(workers):
    FOH = []
    BOH = []
    reception = []
    for worker in workers:
        # create temporary copies of workers to populate positional attendance with empty shifts
        FOHworkerCopy = copy.deepcopy(worker)
        FOHworkerCopy._workShifts = [[], [], [], [], [], [], []]
        BOHworkerCopy = copy.deepcopy(worker)
        BOHworkerCopy._workShifts = [[], [], [], [], [], [], []]
        recWorkerCopy = copy.deepcopy(worker)
        recWorkerCopy._workShifts = [[], [], [], [], [], [], []]

        # examine each shift to determine location
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isFOH():
                    FOHworkerCopy._workShifts[day].append(shift)
                elif shift.isBOH():
                    BOHworkerCopy._workShifts[day].append(shift)
                elif shift.isReception():
                    recWorkerCopy._workShifts[day].append(shift)

        # if shifts added to copy, append to workers list
        if FOHworkerCopy._workShifts != [[], [], [], [], [], [], []]:
            FOH.append(FOHworkerCopy)
        if BOHworkerCopy._workShifts != [[], [], [], [], [], [], []]:
            BOH.append(BOHworkerCopy)
        if recWorkerCopy._workShifts != [[], [], [], [], [], [], []]:
            reception.append(recWorkerCopy)

    return FOH, BOH, reception

# writes corrected output to file
def generateOutput(FOH, BOH, reception):
    pass

# main
def run():
    # fileName = askopenfilename(title="Select payroll file(s)")
    # rawData = getDataFromFile(fileName)
    rawData = getDataFromFile(dataFile)
    trimmedData = trimFileData(rawData)
    usefulData = consolidateData(trimmedData)

    workers = createWorkers(usefulData)
    workers = postProcessing(workers)
    calculateTotals(workers)

    mTips,aTips = calculateTotalTipsPerShift(workers)
    FOH,BOH,reception = sortWorkersByLocation(workers)
    mWorkers, aWorkers = calculateWorkersPerShift(FOH)
    workers = calculatePayroll(workers, mTips, aTips, mWorkers, aWorkers)
    generateOutput(FOH,BOH,reception)

if __name__=="__main__":
    run()