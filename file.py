import pandas as pd

excel_file = "F:\Maaz\employee Data\HRMS DATA-TILL DATE 21-01-2026.xlsx"
xls = pd.ExcelFile(excel_file)

for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    df.to_csv(f"{sheet}.csv", index=False)

print("Done.")
