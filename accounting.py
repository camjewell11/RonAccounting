import copy, pandas, sys, xlsxwriter
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import Worker

debug = False
if len(sys.argv) > 1 and sys.argv[1] == "-nopick":
    debug = True

dataFile = "Data/payroll.xlsx"
outputLocation = "Data/consolidatedPayroll.xlsx"

# prompts user for file in explorer, defaults to dataFile
def getInputFile():
    root = Tk()
    root.withdraw()

    fileName = dataFile
    if not debug:
        fileName = askopenfilename(title="Select payroll file(s)")
        if fileName == dataFile:
            print ("Using default datafile Data/payroll.xlsx")
    return fileName

# prompts user for output location, defaults to outputLocation
def getOutputLocation():
    fileName = outputLocation
    if not debug:
        fileName = askdirectory(title="Select output location")
        if fileName == outputLocation:
            print ("Using default output directory Data/")
        else:
            fileName += "/consolidatedPayroll.xlsx"
    return fileName

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
                    mCoworkers, aCoworkers = findCoworkers(workers, worker._workShifts[day][shift], worker._workShifts[day][shift+1])

                    # this block calculates the average tips for the coworkers for each half of the shift in question
                    # the tips for each half of the double are calculated based on the average for each half
                    # typically, the afternoon will have more tips, so the average tips will be what is counted in
                    # the second half of the double assuming the total tips are greater than the average for the
                    # afternoon. Example: Eli makes 90 in tips on a double. The average tips for the afternoon is 60.
                    # Eli's tips will be split across his double shift as 30-60.
                    mTips = 0
                    aTips = 0

                    for coworker in mCoworkers:
                        mTips += coworker._tips
                    for coworker in aCoworkers:
                        aTips += coworker._tips

                    morningAverage = 0
                    afternoonAverage = 0
                    if len(mCoworkers) > 0:
                        morningAverage = mTips / len(mCoworkers)
                    if len(aCoworkers) > 0:
                        afternoonAverage = aTips / len(aCoworkers)

                    doubleShiftTips = worker._workShifts[day][shift]._tips
                    # morning tips > afternoon
                    if doubleShiftTips < afternoonAverage:
                        worker._workShifts[day][shift]._tips = morningAverage
                        worker._workShifts[day][shift+1]._tips = doubleShiftTips - morningAverage
                    # afternoon tips < morning
                    else:
                        worker._workShifts[day][shift+1]._tips = afternoonAverage
                        worker._workShifts[day][shift]._tips = doubleShiftTips - afternoonAverage

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
    morningTipsByDay   = [[],[],[],[],[],[],[]]
    afternoonTipsByDay = [[],[],[],[],[],[],[]]
    for worker in workers:
        # sum tips per shift per day
        for day in worker._workShifts:
            for shift in day:
                if shift.isMorningShift():
                    morningTipsByDay[shift._weekDay].append(shift._tips)
                elif shift.isAfternoonShift():
                    afternoonTipsByDay[shift._weekDay].append(shift._tips)

                # morningTipsByDay[shift._weekDay] = list(filter(lambda num: num != 0, morningTipsByDay[shift._weekDay]))
                # afternoonTipsByDay[shift._weekDay] = list(filter(lambda num: num != 0, afternoonTipsByDay[shift._weekDay]))

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
                    totalTips += sum(morningTips[day]) / morningWorkers[day]
                elif shift.isAfternoonShift() and not shift.jobIsIgnored():
                    totalTips += sum(afternoonTips[day]) / afternoonWorkers[day]
        worker._adjustedTips = totalTips
        worker.setPostTipWage(totalPay + totalTips)

    return workers

# returns list of shifts on same day as provided shift
def findCoworkers(workers, findShift, secondHalf):
    morningCoworkers = []
    afternoonCoworkers = []
    for worker in workers:
        for day in worker._workShifts:
            for shift in day:
                # shift isn't self and is same time of day
                if shift != findShift and shift._morningShift == findShift._morningShift:
                    if shift._startTime[:10] == findShift._startTime[:10] and not shift.jobIsIgnored():
                        morningCoworkers.append(shift)
                if shift != secondHalf and shift._afternoonShift == secondHalf._afternoonShift:
                    if shift._startTime[:10] == secondHalf._startTime[:10] and not shift.jobIsIgnored():
                        afternoonCoworkers.append(shift)

    return morningCoworkers, afternoonCoworkers

# split FOH, BOH, and reception into their own lists
# workers that worked both reception and bar have their shifts split into FOH and BOH
def sortWorkersByLocation(workers):
    FOH = []
    BOH = []
    reception = []
    managers = []
    for worker in workers:
        # create temporary copies of workers to populate positional attendance with empty shifts
        FOHworkerCopy = copy.deepcopy(worker)
        FOHworkerCopy._workShifts = [[], [], [], [], [], [], []]
        BOHworkerCopy = copy.deepcopy(worker)
        BOHworkerCopy._workShifts = [[], [], [], [], [], [], []]
        recWorkerCopy = copy.deepcopy(worker)
        recWorkerCopy._workShifts = [[], [], [], [], [], [], []]
        managerCopy   = copy.deepcopy(worker)
        managerCopy  ._workShifts = [[], [], [], [], [], [], []]

        # examine each shift to determine location
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isFOH():
                    FOHworkerCopy._workShifts[day].append(shift)
                elif shift.isBOH():
                    BOHworkerCopy._workShifts[day].append(shift)
                elif shift.isReception():
                    recWorkerCopy._workShifts[day].append(shift)
                elif shift.isManager():
                    managerCopy._workShifts[day].append(shift)

        # if shifts added to copy, append to workers list
        if FOHworkerCopy._workShifts != [[], [], [], [], [], [], []]:
            FOH.append(FOHworkerCopy)
        if BOHworkerCopy._workShifts != [[], [], [], [], [], [], []]:
            BOH.append(BOHworkerCopy)
        if recWorkerCopy._workShifts != [[], [], [], [], [], [], []]:
            reception.append(recWorkerCopy)
        if managerCopy._workShifts != [[], [], [], [], [], [], []]:
            managers.append(managerCopy)

    return FOH, BOH, reception, managers

# parses every worker and their individual shifts for information to be outputted
def getDetailsFromWorkers(FOH, BOH, reception, managers, frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts):
    totalTips = 0
    totalPay = 0

    for worker in FOH:
        details = [worker._name, worker._weeklyHours, worker._baseRate, worker._wage, worker._tips, worker._adjustedTips, worker._pay]
        frontOfHousePay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime,shift._rawEndTime,  shift._startTime, shift._endTime,
                                shift._hours, shift._rate, shift._tips, "-", shift._error]
                shifts.append(shiftDetails)
                totalTips += shift._tips
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-",worker._adjustedTips,worker._pay,""])
        totalPay += worker._pay

    for worker in BOH:
        details = [worker._name, worker._weeklyHours, worker._baseRate, worker._pay]
        backOfHousePay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-","-",worker._pay,""])
        totalPay += worker._pay

    for worker in reception:
        details = [worker._name, worker._weeklyHours, worker._baseRate, worker._pay]
        receptionPay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
                totalTips += shift._tips
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-","-",worker._pay,""])
        totalPay += worker._pay

    for worker in managers:
        details = [worker._name, worker._weeklyHours, worker._tips]
        managersPay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
                totalTips += shift._tips
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-","-","",""])

    return frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts, totalTips, totalPay

# writes corrected output to file
def generateOutput(outputFileName, workers, FOH, BOH, reception, managers, mTips, aTips, mWorkers, aWorkers):
    # set columns for each sheet
    frontOfHousePay = [["Worker","Hours","Base Rate","Pay","Individual Tips","Adjusted Tips","Total"]]
    backOfHousePay = [["Worker","Hours","Base Rate","Total"]]
    receptionPay = [["Worker","Hours","Base Rate","Total"]]
    managersPay = [["Worker","Hours","Tips"]]
    shifts = [["Worker","Raw Start Time","Raw End Time","Adj. Start Time","Adj. End Time","Hours","Paid Rate","Tips","Pay","Comments"]]
    tipsData = [["Worker","Start Time","End Time","Raw Tips","Adjusted Tips","# Coworkers","Coworkers' Tips","Tips Average","Paid Tips"]]

    frontOfHousePay,backOfHousePay,receptionPay,managersPay,shifts,tips,pay = getDetailsFromWorkers(FOH, BOH, reception, managers, frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts)
    shifts.append(["Grand Totals","","","","","","",tips,"",pay,""])

    for worker in workers:
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if not shift.jobIsIgnored():
                    dayTips = []
                    numCoworkers = 0
                    if shift._morningShift:
                        dayTips = copy.deepcopy(mTips[day])
                        numCoworkers = mWorkers[day]
                    elif shift._afternoonShift:
                        dayTips = copy.deepcopy(aTips[day])
                        numCoworkers = aWorkers[day]
                    dayTips.remove(shift._tips)
                    tipsData.append([shift._name, shift._startTime, shift._endTime, shift._rawTips, shift._tips, numCoworkers-1, sum(dayTips), (shift._tips+sum(dayTips))/numCoworkers])
        if worker._adjustedTips != 0:
            tipsData.append(["","","","","","","","",worker._adjustedTips])

    # write worksheets
    with xlsxwriter.Workbook(outputFileName) as workbook:
        FOHworksheet = workbook.add_worksheet("FOH")
        for rowNum,row in enumerate(frontOfHousePay):
            FOHworksheet.write_row(rowNum, 0, row)
        BOHworksheet = workbook.add_worksheet("BOH")
        for rowNum,row in enumerate(backOfHousePay):
            BOHworksheet.write_row(rowNum, 0, row)
        RECworksheet = workbook.add_worksheet("Reception")
        for rowNum,row in enumerate(receptionPay):
            RECworksheet.write_row(rowNum, 0, row)
        MANworksheet = workbook.add_worksheet("Managers")
        for rowNum,row in enumerate(managersPay):
            MANworksheet.write_row(rowNum, 0, row)
        shiftWorksheet = workbook.add_worksheet("Shifts")
        for rowNum,row in enumerate(shifts):
            shiftWorksheet.write_row(rowNum, 0, row)
        tipsWorksheet = workbook.add_worksheet("Tips")
        for rowNum,row in enumerate(tipsData):
            tipsWorksheet.write_row(rowNum, 0, row)

        # set column widths and formats
        money = workbook.add_format({'num_format':'$#,##0.00'})

        FOHworksheet.set_column(0,0,15)
        FOHworksheet.set_column(4,5,15)
        FOHworksheet.set_column(2,6,None,money)

        BOHworksheet.set_column(0,0,25)
        BOHworksheet.set_column(2,3,None,money)
        RECworksheet.set_column(0,0,15)
        RECworksheet.set_column(2,4,None,money)
        MANworksheet.set_column(0,0,15)
        MANworksheet.set_column(2,2,None,money)

        shiftWorksheet.set_column(0,4,18)
        shiftWorksheet.set_column(6,9,None,money)
        shiftWorksheet.set_column(9,9,60)
        shiftWorksheet.freeze_panes(1,0)

        tipsWorksheet.set_column(0,2,20)
        tipsWorksheet.set_column(5,5,15)
        tipsWorksheet.set_column(3,4,15,money)
        tipsWorksheet.set_column(6,8,15,money)
        tipsWorksheet.freeze_panes(1,0)

# main
def run():
    # get input filename, defaults to dataFile
    fileName = getInputFile()
    # get data from file
    rawData = getDataFromFile(fileName)
    # pull out useful data
    trimmedData = trimFileData(rawData)
    # consolidate into single line entries
    usefulData = consolidateData(trimmedData)

    # create worker objects with their own shift objects
    workers = createWorkers(usefulData)
    # recursive check of tip calculations
    workers = postProcessing(workers)
    # sets workers' wage based on hours and rate per shift
    calculateTotals(workers)

    # calculate total tips per shift; returns morning list and afternoon value for each day in list
    mTips,aTips = calculateTotalTipsPerShift(workers)
    # returns lists of workers by location (FOH is only one used)
    FOH,_,_,_ = sortWorkersByLocation(workers)
    # splits workers into list by shift for use in tips averaging
    mWorkers, aWorkers = calculateWorkersPerShift(FOH)
    # finalizes all total pay (tips and wage)
    workers = calculatePayroll(workers, mTips, aTips, mWorkers, aWorkers)
    # returns lists of workers by location for use in output
    FOH,BOH,reception,managers = sortWorkersByLocation(workers)

    # get output location
    fileName = getOutputLocation()
    # generate output
    generateOutput(fileName, workers, FOH, BOH, reception, managers, mTips, aTips, mWorkers, aWorkers)

    print ("Finished generating output.")

if __name__=="__main__":
    run()
