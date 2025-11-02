import pandas as pd

# --- Load the files ---
df_general = pd.read_excel("2.xlsx")  # or "2.xlsx"
df_ps = pd.read_excel("1.xlsx")

print("1: ")
print(df_general.head())
print("2: ")
print(df_ps.head())

# --- See all columns (for debugging) ---
print("Columns in ps.xlsx:", list(df_ps.columns))

# --- Helper: Clean Roll Numbers ---
def clean_roll(s):
    return (s.astype(str)
              .str.upper()
              .str.replace(r'\s+', '', regex=True)
              .str.replace(r'[^A-Z0-9]', '', regex=True))

# --- Find the roll column automatically ---
roll_col_ps = None
for col in df_ps.columns:
    if 'roll no' in col.lower():
        roll_col_ps = col
        break

if roll_col_ps is None:
    raise KeyError("❌ Couldn't find a column with 'roll' in its name in ps.xlsx")

# --- Clean roll numbers in both dataframes ---
df_general['Roll No'] = clean_roll(df_general['Roll No'])
df_ps[roll_col_ps] = clean_roll(df_ps[roll_col_ps])

# --- Extract relevant columns from ps.xlsx ---
section_col = None
for col in df_ps.columns:
    if 'section' in col.lower():
        section_col = col
        break

if section_col is None:
    raise KeyError("❌ Couldn't find a column with 'section' in its name in ps.xlsx")

df_ps_trimmed = df_ps[[roll_col_ps, section_col]].rename(columns={section_col: 'sem2_sec'})

# --- Merge on Roll No ---
df_merged = pd.merge(df_general, df_ps_trimmed, left_on='Roll No', right_on=roll_col_ps, how='left')

# --- Drop duplicate column ---
df_merged.drop(columns=[roll_col_ps], inplace=True, errors='ignore')

# --- Save result ---
df_merged.to_excel("general_with_sem2_sec.xlsx", index=False)

print("✅ sem2_sec column added successfully!")
print(f"Total rows in final file: {len(df_merged)}")
print(f"Total rows matched: {df_merged['sem2_sec'].notna().sum()}")
