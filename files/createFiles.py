import pandas as pd
import re
import os

input_file = "CNA_CS_ES.xlsx"

# === Step 1: Read the Excel file ===
df_raw = pd.read_excel(input_file, header=None)

# Find which row contains "Roll No"
header_row_index = None
for i in range(len(df_raw)):
    row_values = df_raw.iloc[i].astype(str).tolist()
    if any("Roll No" in cell for cell in row_values):
        header_row_index = i
        break

if header_row_index is None:
    raise ValueError("Couldn't find 'Roll No' in the Excel file. Check the sheet manually!")

df = pd.read_excel(input_file, header=header_row_index)
df.columns = df.columns.str.replace(r"[\u200b\xa0]", "", regex=True)
df.columns = df.columns.str.strip()
print("✅ Detected Columns:", df.columns.tolist())

# === Step 2: Define classification logic ===
def classify_branch(roll_no):
    if pd.isna(roll_no):
        return None
    roll_no = str(roll_no)
    if re.search(r"S202\d001\d+", roll_no):
        return "CSE"
    elif re.search(r"S202\d003\d+", roll_no):
        return "AIDS"
    elif re.search(r"S202\d002\d+", roll_no):
        return "ECE"
    else:
        return None

df["Branch"] = df["Roll No"].apply(classify_branch)
required_columns = ["Name of the student", "Roll No", "Section"]

# === Step 3: Append or create branch files ===
for branch in ["CSE", "AIDS", "ECE"]:
    branch_df = df[df["Branch"] == branch][required_columns]
    if branch_df.empty:
        print(f"⚠️ No students found for {branch}.")
        continue
    
    file_name = f"{branch}.xlsx"
    
    if os.path.exists(file_name):
        # Read existing file and append new rows
        existing_df = pd.read_excel(file_name)
        combined_df = pd.concat([existing_df, branch_df], ignore_index=True)
        combined_df.to_excel(file_name, index=False)
        print(f"✅ {branch}.xlsx updated with {len(branch_df)} new students.")
    else:
        # Create new file if it doesn't exist
        branch_df.to_excel(file_name, index=False)
        print(f"✅ {branch}.xlsx created with {len(branch_df)} students.")

print("\n🎉 Done! All files are updated.")
