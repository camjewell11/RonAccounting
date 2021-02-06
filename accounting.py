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
                if data["name"][startRow] not in specialTips:
                    newWorker = Worker.worker(data, startRow, endRow)
                    workers.append(newWorker)
                startRow = x
            else:
                startRow = x
    # ignore "Grand Total"
    # workers.append(worker(data, startRow, len(data["name"])))

    return workers

# calculates pay for each worker; returns total tips and hours
def calculateTotals(workers):
    totalTips = 0
    totalHours = 0
    for worker in workers:
        weeklyPay = 0
        for shift in worker._workShifts:
            weeklyPay += shift._rate*shift._hours
        totalTips += worker._weeklyTips
        totalHours += worker._weeklyHours
        worker.setPreTipWage(weeklyPay)
    return [totalTips, totalHours]

# adds wages and tips at the hourly rate for each worker
def calculatePayroll(tipRate, workers):
    for worker in workers:
        totalPay = tipRate * worker._tipableHours + worker._wage
        worker.setPostTipWage(totalPay)

# main
def run():
    rawData = getDataFromFile(dataFile)
    trimmedData = trimFileData(rawData)
    usefulData = consolidateData(trimmedData)

    workers = createWorkers(usefulData)
    tips,hours = calculateTotals(workers)

    tipWageHourly = tips/hours
    calculatePayroll(tipWageHourly, workers)

    print ("hey")

if __name__=="__main__":
    run()