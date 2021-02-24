import copy, inputManager, outputManager, Worker

debugInput = False
debugOutput = False
dataFile = "Data/payroll2.xlsx"
outputLocation = "Data/"

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
    return workers

# split worker pay totals by location
def workerLocationPostProcessing(workers):
    for worker in workers:
        # if worker.haveMultipleLocations():
        for day in worker._workShifts:
            for shift in day:
                if shift.isFOH():
                    worker._FOHwage += shift._hours*shift._rate
                    worker._FOHhours += shift._hours
                elif shift.isBOH():
                    worker._BOHwage += shift._hours*shift._rate
                    worker._BOHhours += shift._hours
                elif shift.isReception():
                    worker._RECwage += shift._hours*shift._rate
                    worker._REChours += shift._hours
    return workers

# if clock-in/out changes are made that affect rate due to overtime,
# recreate shifts and pay calculations for corrected shifts;
# adjust tips based on double shifts
def tipsPostProcessing(workers):
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
                if shift._tips != 0:
                    if shift.isMorningShift():
                        morningTipsByDay[shift._weekDay].append(shift._tips)
                    elif shift.isAfternoonShift():
                        afternoonTipsByDay[shift._weekDay].append(shift._tips)

    return morningTipsByDay, afternoonTipsByDay

# checks all shifts against config for ignored positions and counts workers per shift
def calculateWorkersPerShift(workers):
    # returns lists of workers by location (FOH is only one used)
    FOH,_,_,_ = sortWorkersByLocation(workers)

    morningWorkersPerDay   = [0,0,0,0,0,0,0]
    afternoonWorkersPerDay = [0,0,0,0,0,0,0]
    for worker in FOH:
        mShifts = [0,0,0,0,0,0,0]
        aShifts = [0,0,0,0,0,0,0]
        # count number of workers per shift per day
        for day in range(len(worker._workShifts)):
            for shift in worker._workShifts[day]:
                if shift.isMorningShift() and not shift.jobIsIgnored() and not shift._overtime:
                    mShifts[day] += 1
                elif shift.isAfternoonShift() and not shift.jobIsIgnored() and not shift._overtime:
                    aShifts[day] += 1

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
                if shift.isMorningShift() and not shift.jobIsIgnored() and not shift._overtime:
                    totalTips += sum(morningTips[day]) / morningWorkers[day]
                elif shift.isAfternoonShift() and not shift.jobIsIgnored() and not shift._overtime:
                    totalTips += sum(afternoonTips[day]) / afternoonWorkers[day]
        worker._adjustedTips = totalTips
        worker.setPostTipWage(totalPay + totalTips)

    return workers

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

def main():
    # reads command line arguments if there are any
    proceed = inputManager.parseCommandLineOptions()

    if proceed:
        # get input filename, defaults to dataFile
        fileName    = inputManager.getInputFile(dataFile)
        # get data from file
        rawData     = inputManager.getDataFromFile(fileName)
        # pull out useful data
        trimmedData = inputManager.trimFileData(rawData)
        # consolidate into single line entries
        usefulData  = inputManager.consolidateData(trimmedData)

        # create worker objects with their own shift objects
        workers = createWorkers(usefulData)
        # recursive check of tip calculations
        workers = tipsPostProcessing(workers)
        # sets workers' wage based on hours and rate per shift
        calculateTotals(workers)
        # check pay totals for workers who worked multiple locations
        workers = workerLocationPostProcessing(workers)

        # calculate total tips per shift; returns morning list and afternoon value for each day in list
        mTips,aTips = calculateTotalTipsPerShift(workers)
        # splits workers into list by shift for use in tips averaging
        mWorkers, aWorkers = calculateWorkersPerShift(workers)
        # finalizes all total pay (tips and wage)
        workers = calculatePayroll(workers, mTips, aTips, mWorkers, aWorkers)
        # returns lists of workers by location for use in output
        FOH,BOH,reception,managers = sortWorkersByLocation(workers)

        # get output location
        fileName = outputManager.getOutputLocation(outputLocation)
        # generate output
        outputManager.generateOutput(fileName, workers, FOH, BOH, reception, managers, mTips, aTips, mWorkers, aWorkers)

        print ("Finished generating output.")

if __name__=="__main__":
    main()