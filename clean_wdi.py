import pandas as pd
import numpy as np
import os

RAW_PATH   = "data/wdi_raw.csv"
CLEAN_PATH = "data/wdi_clean.csv"

INDICATORS = {
    "PA.NUS.FCRF":    "exchange_rate",
    "NY.GDP.PCAP.CD": "gdp_per_capita",
    "SI.POV.DDAY":    "poverty_headcount",
}

# World Bank regional/income aggregates to exclude
EXCLUDE_ISO3 = {
    "AFE", "AFW", "ARB", "CEB", "CSS", "EAP", "EAR", "EAS", "ECA", "ECS",
    "EMU", "EUU", "FCS", "HIC", "HPC", "IBD", "IBT", "IDA", "IDB", "IDX",
    "LAC", "LCN", "LDC", "LIC", "LMC", "LMY", "LTE", "MEA", "MIC", "MNA",
    "NAC", "OED", "OSS", "PRE", "PSS", "PST", "SAS", "SSA", "SSF", "SST",
    "TEA", "TEC", "TLA", "TMN", "TSA", "TSS", "UMC", "WLD", "XZN",
    "INX", "ZAF", "ZAR", "ZBL",
}

def clean_wdi(raw_path: str, clean_path: str) -> pd.DataFrame:
    print("=" * 60)
    print("WDI DATA CLEANING PIPELINE")
    print("=" * 60)

    # 1. Load
    print("\n[1] Loading raw data ...")
    df = pd.read_csv(raw_path)
    print(f"    Raw shape: {df.shape}")

    # 2. Select relevant columns
    year_cols = [c for c in df.columns if c[:4].isdigit()]
    keep_cols = ["Country Name", "Country Code", "Series Code"] + year_cols
    df = df[keep_cols].copy()

    # 3. Filter to our three indicators
    print("\n[2] Filtering to target indicators ...")
    df = df[df["Series Code"].isin(INDICATORS.keys())].copy()
    print(f"    Indicators found: {df['Series Code'].unique().tolist()}")

    # 4. Remove regional/income aggregates
    print("\n[3] Removing regional and income-group aggregates ...")
    before = df["Country Code"].nunique()
    df = df[~df["Country Code"].isin(EXCLUDE_ISO3)].copy()
    after = df["Country Code"].nunique()
    print(f"    Removed {before - after} non-country entries ({after} countries remaining)")

    # 5. Melt wide to long
    print("\n[4] Reshaping from wide to long format ...")
    df_long = df.melt(
        id_vars=["Country Name", "Country Code", "Series Code"],
        value_vars=year_cols,
        var_name="year_raw",
        value_name="value"
    )
    df_long["year"] = df_long["year_raw"].str.extract(r"(\d{4})").astype(int)
    df_long = df_long.drop(columns=["year_raw"])
    df_long["indicator"] = df_long["Series Code"].map(INDICATORS)

    # 6. Convert to numeric
    print("\n[5] Converting values to numeric ...")
    df_long["value"] = pd.to_numeric(df_long["value"], errors="coerce")

    # 7. Pivot
    print("\n[6] Pivoting indicators into columns ...")
    df_pivot = df_long.pivot_table(
        index=["Country Name", "Country Code", "year"],
        columns="indicator",
        values="value"
    ).reset_index()
    df_pivot.columns.name = None
    df_pivot = df_pivot.rename(columns={
        "Country Name": "country",
        "Country Code": "iso3",
    })

    # 8. Data types
    print("\n[7] Checking data types ...")
    df_pivot["year"] = df_pivot["year"].astype(int)
    for col in INDICATORS.values():
        df_pivot[col] = pd.to_numeric(df_pivot[col], errors="coerce")
    df_pivot["country"] = df_pivot["country"].astype(str).str.strip()
    df_pivot["iso3"] = df_pivot["iso3"].astype(str).str.strip().str.upper()
    print(f"    dtypes: {df_pivot.dtypes.to_dict()}")

    # 9. Drop fully empty rows
    print("\n[8] Dropping rows with no indicator data at all ...")
    indicator_cols = list(INDICATORS.values())
    before = len(df_pivot)
    df_pivot = df_pivot.dropna(subset=indicator_cols, how="all")
    print(f"    Dropped {before - len(df_pivot)} fully-empty rows")

    # 10. Missing value summary
    print("\n[9] Missing value summary:")
    for col in indicator_cols:
        n_missing = df_pivot[col].isna().sum()
        pct = 100 * n_missing / len(df_pivot)
        print(f"    {col}: {n_missing} missing ({pct:.1f}%)")

    # 11. Outlier check
    print("\n[10] Outlier check (values > 3 std from mean):")
    for col in indicator_cols:
        series = df_pivot[col].dropna()
        mean, std = series.mean(), series.std()
        outliers = df_pivot[
            df_pivot[col].notna() &
            (np.abs(df_pivot[col] - mean) > 3 * std)
        ][["country", "year", col]]
        if not outliers.empty:
            print(f"    {col}: {len(outliers)} potential outliers")
            print(outliers.sort_values(col, ascending=False).head(5).to_string(index=False))
        else:
            print(f"    {col}: no outliers detected")

    # 12. Negative value check
    print("\n[11] Checking for unexpected negative values ...")
    for col in ["exchange_rate", "gdp_per_capita", "poverty_headcount"]:
        neg = df_pivot[df_pivot[col] < 0]
        if not neg.empty:
            print(f"    WARNING - {col} has {len(neg)} negative values. Setting to NaN.")
            df_pivot.loc[df_pivot[col] < 0, col] = np.nan
        else:
            print(f"    {col}: no negatives found")

    # 13. Sort and save
    df_pivot = df_pivot.sort_values(["country", "year"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
    df_pivot.to_csv(clean_path, index=False)

    print("\n" + "=" * 60)
    print("CLEAN DATA SUMMARY")
    print("=" * 60)
    print(f"  Saved to:  {clean_path}")
    print(f"  Shape:     {df_pivot.shape}")
    print(f"  Countries: {df_pivot['country'].nunique()}")
    print(f"  Years:     {df_pivot['year'].min()} - {df_pivot['year'].max()}")
    print(f"\nSample rows:")
    print(df_pivot.dropna(subset=["exchange_rate"]).head(8).to_string(index=False))

    return df_pivot

if __name__ == "__main__":
    clean_wdi(RAW_PATH, CLEAN_PATH)