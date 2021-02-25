import accounting, copy, xlsxwriter
from tkinter import Tk
from tkinter.filedialog import askdirectory

# prompts user for output location, defaults to outputLocation
def getOutputLocation(outputLocation):
    # hides second tk dialogue
    root = Tk()
    root.withdraw()

    fileName = outputLocation + "consolidatedPayroll.xlsx"
    if not accounting.debugOutput:
        chosenLocation = askdirectory(title="Select output location")
        if chosenLocation != "":
            return chosenLocation + "/consolidatedPayroll.xlsx"
    print ("Using default output directory " + outputLocation + ".")
    return fileName

# writes corrected output to file
def generateOutput(outputFileName, workers, FOH, BOH, reception, managers, mTips, aTips, mWorkers, aWorkers):
    # set columns for each sheet
    frontOfHousePay = [["Worker","Hours","Base Rate",       "Pay","Ind. Tips","Adj. Tips","Total"]]
    backOfHousePay  = [["Worker","Hours","Base Rate",       "Pay"]]
    receptionPay    = [["Worker","Hours","Base Rate","Tips","Pay"]]
    managersPay     = [["Worker","Hours",            "Tips"]]
    shifts          = [["Worker","Raw Start Time","Raw End Time","Adj. Start Time","Adj. End Time","Hours","Paid Rate","Tips","Pay","Comments"]]
    tipsData        = [["Worker","Start Time","End Time","Raw Tips","Adj. Tips","# Coworkers","Co-Tips","Tips Average","Paid Tips"]]

    frontOfHousePay,backOfHousePay,receptionPay,managersPay,shifts,tips,pay = getDetailsFromWorkers(workers, FOH, BOH, reception, managers, frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts)
    shifts.append(["Grand Totals","","","","","","",tips,"",pay,""])
    tipsData = getTipsData(workers, tipsData, mTips, aTips, mWorkers, aWorkers)

    # write worksheets
    with xlsxwriter.Workbook(outputFileName) as workbook:
        summaryWorksheet = workbook.add_worksheet("Summary")

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

        summaryData = generateSummaryData(frontOfHousePay, backOfHousePay, receptionPay, managersPay)
        for rowNum,row in enumerate(summaryData):
            summaryWorksheet.write_row(rowNum, 0, row)

        setSheetFormatting(workbook, FOHworksheet, BOHworksheet, RECworksheet, MANworksheet, shiftWorksheet, tipsWorksheet, summaryWorksheet)

# calculates data to be outputted in tips sheet
def getTipsData(workers, tipsData, mTips, aTips, mWorkers, aWorkers):
    for worker in workers:
        totalRawtips = 0
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                # if worker can earn tips and shift is not overtime
                if not shift.jobIsIgnored() and not shift._overtime:
                    numCoworkers = 0
                    if shift._morningShift:
                        dayTips = copy.deepcopy(mTips[day])
                        numCoworkers = mWorkers[day]
                    elif shift._afternoonShift:
                        dayTips = copy.deepcopy(aTips[day])
                        numCoworkers = aWorkers[day]
                    if shift._tips in dayTips:
                        dayTips.remove(shift._tips)
                    tipsData.append([shift._name, shift._startTime, shift._endTime, shift._rawTips, shift._tips, numCoworkers-1, sum(dayTips), (shift._tips+sum(dayTips))/numCoworkers])
                # if worker cannot earn tips and tips are nonzero
                elif shift._tips != 0:
                    tipsData.append([shift._name, shift._startTime, shift._endTime, shift._rawTips, shift._tips, "-", "-", "-"])

                totalRawtips += shift._rawTips

        if totalRawtips != 0:
            tipsData.append(["","","",totalRawtips,"","","","",worker._adjustedTips])

    return tipsData

# parses other sheets for data to populate summary page
def generateSummaryData(frontOfHousePay, backOfHousePay, receptionPay, managersPay):
    summaryData = frontOfHousePay
    summaryData.append([])
    summaryData[0] = ["Worker","Hours","Base Rate","Pay","Ind. Tips","Adj. Tips","Total"]
    for entry in backOfHousePay[1:]:
        summaryData.append([entry[0],entry[1],entry[2],entry[3],"-","-",entry[3]])
    summaryData.append([])
    for entry in receptionPay[1:]:
        summaryData.append([entry[0],entry[1],entry[2],entry[4],entry[3],0,entry[4]])
    summaryData.append([])
    for entry in managersPay[1:]:
        summaryData.append([entry[0],entry[1],"-","-",entry[2],0,"-"])
    summaryData.append([])

    payTotal      = 0
    indTipsTotal  = 0
    adjTipsTotal  = 0
    totalTotal    = 0
    # totals columns in summary for sanity check
    for entry in summaryData[1:]:
        if entry != []:
            if entry[3] != "-":
                payTotal += entry[3]
            if entry[4] != "-":
                indTipsTotal += entry[4]
            if entry[5] != "-":
                adjTipsTotal += entry[5]
            if entry[6] != "-":
                totalTotal += entry[6]
    summaryData.append(["Totals","","",payTotal,indTipsTotal,adjTipsTotal,totalTotal])

    return summaryData

# set column widths and formats
def setSheetFormatting(workbook, FOHworksheet, BOHworksheet, RECworksheet, MANworksheet, shiftWorksheet, tipsWorksheet, summaryWorksheet):
    money = workbook.add_format({'num_format':'$#,##0.00'})

    FOHworksheet.set_column(0,0,15)
    FOHworksheet.set_column(4,5,10)
    FOHworksheet.set_column(2,6,None,money)
    BOHworksheet.set_column(0,0,25)
    BOHworksheet.set_column(2,3,None,money)
    RECworksheet.set_column(0,0,15)
    RECworksheet.set_column(2,5,None,money)
    MANworksheet.set_column(0,0,15)
    MANworksheet.set_column(2,2,None,money)

    shiftWorksheet.set_column(0,4,18)
    shiftWorksheet.set_column(6,9,None,money)
    shiftWorksheet.set_column(9,9,60)
    shiftWorksheet.freeze_panes(1,1)

    tipsWorksheet.set_column(0,2,20)
    tipsWorksheet.set_column(5,5,10)
    tipsWorksheet.set_column(3,4,10,money)
    tipsWorksheet.set_column(6,8,10,money)
    tipsWorksheet.freeze_panes(1,1)

    summaryWorksheet.set_column(0,0,20)
    summaryWorksheet.set_column(2,6,10,money)
    summaryWorksheet.freeze_panes(1,1)

# parses every worker and their individual shifts for information to be outputted
def getDetailsFromWorkers(workers, FOH, BOH, reception, managers, frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts):
    for worker in FOH:
        details = [worker._name, worker._FOHhours, worker._baseRate, worker._FOHwage, worker._tips, worker._adjustedTips, worker._pay]
        frontOfHousePay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime,shift._rawEndTime,  shift._startTime, shift._endTime,
                                shift._hours, shift._rate, shift._tips, "-", shift._error]
                shifts.append(shiftDetails)
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-",worker._adjustedTips,worker._pay,""])
        shifts.append([])

    for worker in BOH:
        details = [worker._name, worker._BOHhours, worker._baseRate, worker._BOHwage]
        backOfHousePay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-","-",worker._pay,""])
        shifts.append([])

    for worker in reception:
        details = [worker._name, worker._REChours, worker._baseRate, worker._tips, worker._RECwage]
        receptionPay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-",worker._tips,worker._pay,""])
        shifts.append([])

    for worker in managers:
        details = [worker._name, worker._weeklyHours, worker._tips]
        managersPay.append(details)
        for day in worker._workShifts:
            for shift in day:
                shiftDetails = [shift._name, shift._rawStartTime, shift._rawEndTime, shift._startTime, shift._endTime,
                                shift._hours, shift._rate, "-", "-", shift._error]
                shifts.append(shiftDetails)
        shifts.append([worker._name+" Total","-","-","-","-",worker._weeklyHours,"-","-","",""])
        shifts.append([])

    totalTips = 0
    totalPay = 0
    totalHours = 0
    for worker in workers:
        for day in worker._workShifts:
            for shift in day:
                if shift._job not in ["Manager", "Comp"]:
                    totalPay += shift._rate * shift._hours
                    totalHours += shift._hours
        totalTips += worker._tips

    return frontOfHousePay, backOfHousePay, receptionPay, managersPay, shifts, totalTips, totalPay