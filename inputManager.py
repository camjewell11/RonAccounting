import accounting, pandas, os, sys
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# parses flags for input/output/nopick flags
def parseCommandLineOptions():
    if len(sys.argv) > 1 and sys.argv[1] == "-nopick":
        accounting.debugInput = True
        accounting.debugOutput = True
    # specify input file
    if "-i" in sys.argv:
        accounting.dataFile = sys.argv[sys.argv.index("-i")+1]
        accounting.debugInput = True
        if not os.path.exists(accounting.dataFile):
            print ("Could not located specified input file: " + accounting.dataFile)
            return 0
    # specify output directory
    if "-o" in sys.argv:
        accounting.outputLocation = sys.argv[sys.argv.index("-o")+1]
        accounting.debugOutput = True
        if not os.path.exists(accounting.outputLocation):
            print ("Could not located output location: " + accounting.outputLocation)
            return 0
    # display available commands
    if "-h" in sys.argv:
        print ("Available options:")
        print ("   -nopick \t\tUse the default input/output")
        print ("   Example: python accounting.py -nopick")
        print ()
        print ("   -i <input file> \tSpecify input file")
        print ("   Example: python accounting.py -i payroll.xlsx")
        print ()
        print ("   -o <output location> Specify output directory")
        print ("   Example: python accounting.py -o Data/Feb12/")
        print ()
        print ("   -h \t\t\tDisplay all command line options")
        print ("   Example: python accounting.py -h")
        print ()
        return 0

    return 1

# prompts user for file in explorer, defaults to dataFile
def getInputFile(dataFile):
    root = Tk()
    root.withdraw()

    fileName = dataFile
    if not accounting.debugInput:
        fileName = askopenfilename(title="Select payroll file(s)")
        if fileName == dataFile:
            print ("Using default datafile Data/payroll.xlsx")
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
    for entry in range(len(data["name"])-2):
        if data["start"][entry] == data["start"][entry+1]:
            if data["end"][entry] == data["end"][entry+1]:
                if data["working"][entry] == "Shift":
                    data["tips"][entry] = data["tips"][entry+1]
                else:
                    data["tips"][entry+1] = data["tips"][entry]
            # overtime met during shift
            elif data["end"][entry] == data["end"][entry+2]:
                data["tips"][entry+1] = data["tips"][entry]

    return data