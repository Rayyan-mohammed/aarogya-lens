"""
BharatHealth Analyst — NFHS-4 Trend Integration
Merges real NFHS-4 (2015-16) state-level indicators onto the NFHS-5 (2019-21)
district-level dataset to enable genuine trend analysis.

IMPORTANT DATA LIMITATION (documented, not hidden):
The NFHS-4 factsheet published for this project (NFHS-4_NFHS3_Factsheet-All_India_Indicators_R1.csv)
is a STATE-level factsheet (37 states/UTs x Total/Rural/Urban), not a district-level file.
NFHS-5 is district-level (706 districts). True district-to-district trend comparison is
therefore not possible from these two files. Instead, each NFHS-5 district is compared
against its own state's NFHS-4 baseline — e.g. "Adilabad district's NFHS-5 stunting rate
vs Telangana state's NFHS-4 stunting rate". This is a real, honest comparison (not
synthetic/fabricated data), but it is a state-baseline comparison, not a true district-level
one. Every derived trend column and the agent's grounding rules make this explicit.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
DATASET_DIR = ROOT / "dataset"

NFHS4_RAW = DATASET_DIR / "NFHS-4_NFHS3_Factsheet-All_India_Indicators_R1.csv"
NFHS5_PARQUET = DATA_DIR / "nfhs5_clean.parquet"

OUTPUT_PARQUET = DATA_DIR / "nfhs5_clean.parquet"          # enriched in place — single source of truth
OUTPUT_CSV = DATA_DIR / "nfhs5_clean.csv"
OUTPUT_TRENDS_PARQUET = DATA_DIR / "nfhs5_with_trends.parquet"  # kept as an alias/back-compat copy
OUTPUT_TRENDS_CSV = DATA_DIR / "nfhs5_with_trends.csv"
OUTPUT_SCHEMA = DATA_DIR / "schema.json"
OUTPUT_SUMMARIES = DATA_DIR / "district_summaries.json"
TREND_SUMMARY_PATH = DATA_DIR / "trend_analysis_summary.json"

# Indicators that get a trend sentence appended to each district's natural-language summary
SUMMARY_TREND_INDICATORS = [
    ("stunting_pct", "stunting"),
    ("anaemia_children_pct", "child anaemia"),
    ("institutional_delivery_pct", "institutional delivery"),
    ("fully_vaccinated_recall_pct", "full vaccination coverage"),
]


# ─── NFHS-4 raw column → NFHS-5 short column name (only genuinely overlapping indicators) ──
NFHS4_COLUMN_MAP = {
    "Population and Household Profile - Population (female) age 6 years and above who ever attended school (%)": "female_school_attendance_pct",
    "Population and Household Profile - Population below age 15 years (%)": "pop_below_15_pct",
    "Population and Household Profile - Sex ratio of the total population (females per 1000 males)": "sex_ratio",
    "Population and Household Profile - Sex ratio at birth for children born in the last five years (females per 1000 males)": "sex_ratio_at_birth",
    "Population and Household Profile - Children under age 5 years whose birth was registered (%)": "birth_registration_pct",
    "Population and Household Profile - Households with electricity (%)": "electricity_access_pct",
    "Population and Household Profile - Households with an improved drinking-water source (%)": "clean_water_access_pct",
    "Population and Household Profile - Households using improved sanitation facility (%)": "improved_sanitation_pct",
    "Population and Household Profile - Households using clean fuel for cooking (%)": "clean_cooking_fuel_pct",
    "Population and Household Profile - Households using iodized salt (%)": "iodized_salt_pct",
    "Population and Household Profile - Households with any usual member covered by a health scheme or health insurance (%)": "health_insurance_pct",
    "Characteristics of Adults (age 15-49) - Women who are literate (%)": "women_literacy_pct",
    "Characteristics of Adults (age 15-49) - Women with 10 or more years of schooling (%)": "women_10yr_school_pct",
    "Marriage and Fertility - Women age 20-24 years married before age 18 years (%)": "child_marriage_pct",
    "Marriage and Fertility - Women age 15-19 years who were already mothers or pregnant at the time of the survey (%)": "teen_pregnancy_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Any method (%)": "fp_any_method_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Any modern method (%)": "fp_modern_method_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Female sterilization (%)": "fp_female_sterilization_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Male sterilization (%)": "fp_male_sterilization_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - IUD/PPIUD (%)": "fp_iud_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Pill (%)": "fp_pill_pct",
    "Current Use of Family Planning Methods (currently married women age 15-49 years) - Condom (%)": "fp_condom_pct",
    "Unmet Need for Family Planning (currently married women age 15-49 years)5 - Total unmet need (%)": "unmet_fp_need_pct",
    "Unmet Need for Family Planning (currently married women age 15-49 years)5 - Unmet need for spacing (%)": "unmet_fp_spacing_pct",
    "Quality of Family Planning Services - Health worker ever talked to female non-users about family planning (%)": "fp_counselling_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Mothers who had antenatal check-up in the first trimester (%)": "anc_first_trimester_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Mothers who had at least 4 antenatal care visits (%)": "anc_4plus_visits_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Mothers who consumed iron folic acid for 100 days or more when they were pregnant (%)": "ifa_100days_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Registered pregnancies for which the mother received Mother and Child Protection (MCP) card (%)": "mcp_card_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Mothers who received postnatal care from a doctor/nurse/LHV/ANM/midwife/other health personnel within 2 days of delivery (%)": "postnatal_care_mother_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Average out of pocket expenditure per delivery in public health facility (Rs.)": "oop_delivery_cost_rs",
    "Maternity Care (for last birth in the 5 years before the survey) - Children born at home who were taken to a health facility for check-up within 24 hours of birth (%)": "home_birth_facility_checkup_pct",
    "Maternity Care (for last birth in the 5 years before the survey) - Children who received a health check after birth from a doctor/nurse/LHV/ANM/ midwife/other health personnel within 2 days of birth (%)": "postnatal_care_child_pct",
    "Delivery Care (for births in the 5 years before the survey) - Institutional births (%)": "institutional_delivery_pct",
    "Delivery Care (for births in the 5 years before the survey) - Institutional births in public facility (%)": "institutional_delivery_public_pct",
    "Delivery Care (for births in the 5 years before the survey) - Home delivery conducted by skilled health personnel (out of total deliveries) (%)": "skilled_home_birth_pct",
    "Delivery Care (for births in the 5 years before the survey) - Births assisted by a doctor/nurse/LHV/ANM/other health personnel (%)": "skilled_birth_attendant_pct",
    "Delivery Care (for births in the 5 years before the survey) - Births delivered by caesarean section (%)": "csection_pct",
    "Delivery Care (for births in the 5 years before the survey) - Births in a private health facility delivered by caesarean section (%)": "csection_private_pct",
    "Delivery Care (for births in the 5 years before the survey) - Births in a public health facility delivered by caesarean section (%)": "csection_public_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who have received BCG (%)": "bcg_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who have received 3 doses of polio vaccine (%)": "polio3_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who have received 3 doses of DPT vaccine (%)": "dpt3_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who have received measles vaccine (%)": "measles_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who have received 3 doses of Hepatitis B vaccine (%)": "hepb3_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who received most of the vaccinations in public health facility (%)": "vaccinated_in_public_pct",
    "Child Immunizations and Vitamin A Supplementation - Children age 12-23 months who received most of the vaccinations in private health facility (%)": "vaccinated_in_private_pct",
    "Treatment of Childhood Diseases (children under age 5 years) - Children with diarrhoea in the last 2 weeks who received oral rehydration salts (ORS) (%)": "diarrhoea_ors_pct",
    "Treatment of Childhood Diseases (children under age 5 years) - Children with diarrhoea in the last 2 weeks who received zinc (%)": "diarrhoea_zinc_pct",
    "Treatment of Childhood Diseases (children under age 5 years) - Children with diarrhoea in the last 2 weeks taken to a health facility (%)": "diarrhoea_facility_pct",
    "Treatment of Childhood Diseases (children under age 5 years) - Children with fever or symptoms of ARI in the last 2 weeks preceding the survey taken to a health facility (%)": "ari_facility_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under age 3 years breastfed within one hour of birth (%)": "early_breastfeed_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under age 6 months exclusively breastfed (%)": "exclusive_breastfeed_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children age 6-8 months receiving solid or semi-solid food and breastmilk (%)": "complementary_feed_pct",
    "Child Feeding Practices and Nutritional Status of Children - Breastfeeding children age 6-23 months receiving an adequate diet (%": "adequate_diet_breastfed_pct",
    "Child Feeding Practices and Nutritional Status of Children - Non-breastfeeding children age 6-23 months receiving an adequate diet (%": "adequate_diet_nonbreastfed_pct",
    "Child Feeding Practices and Nutritional Status of Children - Total children age 6-23 months receiving an adequate diet (%": "adequate_diet_total_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under 5 years who are stunted (height-for-age) (%)": "stunting_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under 5 years who are wasted (weight-for-height) (%)": "wasting_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under 5 years who are severely wasted (weight-for-height) (%)": "severe_wasting_pct",
    "Child Feeding Practices and Nutritional Status of Children - Children under 5 years who are underweight (weight-for-age) (%)": "underweight_pct",
    "Nutritional Status of Adults (age 15-49 years) - Women whose Body Mass Index (BMI) is below normal (BMI < 18.5 kg/m2) (%)": "women_low_bmi_pct",
    "Nutritional Status of Adults (age 15-49 years) - Men whose Body Mass Index (BMI) is below normal (BMI < 18.5 kg/m2) (%)": "men_low_bmi_pct",
    "Nutritional Status of Adults (age 15-49 years) - Women who are overweight or obese (BMI >= 25.0 kg/m2) (%)": "women_overweight_pct",
    "Nutritional Status of Adults (age 15-49 years) - Men who are overweight or obese (BMI >= 25.0 kg/m2) (%)": "men_overweight_pct",
    "Anaemia among Children and Adults15 - Children age 6-59 months who are anaemic (<11.0 g/dl) (%)": "anaemia_children_pct",
    "Anaemia among Children and Adults15 - Non-pregnant women age 15-49 years who are anaemic (<12.0 g/dl) (%)": "anaemia_nonpregnant_women_pct",
    "Anaemia among Children and Adults15 - Pregnant women age 15-49 years who are anaemic (<11.0 g/dl) (%)": "anaemia_pregnant_women_pct",
    "Anaemia among Children and Adults15 - All women age 15-49 years who are anaemic (%)": "anaemia_all_women_pct",
    "Anaemia among Children and Adults15 - Men age 15-49 years who are anaemic (<13.0 g/dl) (%)": "anaemia_men_pct",
    "Women - Blood sugar level - high (>140 mg/dl) (%)": "women_high_blood_sugar_pct",
    "Men - Blood sugar level - high (>140 mg/dl) (%)": "men_high_blood_sugar_pct",
    "Women - Slightly above normal (Systolic 140-159 mm of Hg and/or Diastolic 90-99 mm of Hg) (%)": "women_hypertension_mild_pct",
    "Men - Slightly above normal (Systolic 140-159 mm of Hg and/or Diastolic 90-99 mm of Hg) (%)": "men_hypertension_mild_pct",
    "Women - Very high (Systolic >= 180 mm of Hg and/or Diastolic >= 110 mm of Hg) (%)": "women_hypertension_severe_pct",
    "Men - Very high (Systolic >= 180 mm of Hg and/or Diastolic >= 110 mm of Hg) (%)": "men_hypertension_severe_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Cervix (%)": "cervix_exam_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Breast (%)": "breast_exam_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Oral cavity (%)": "oral_exam_pct",
    "Knowledge of HIV/AIDS among Adults (age 15-49 years) - Women who have comprehensive knowledge of HIV/AIDS (%)": "women_hiv_knowledge_pct",
    "Knowledge of HIV/AIDS among Adults (age 15-49 years) - Men who have comprehensive knowledge of HIV/AIDS (%)": "men_hiv_knowledge_pct",
    "Knowledge of HIV/AIDS among Adults (age 15-49 years) - Women who know that consistent condom use can reduce the chances of getting HIV/AIDS (%)": "women_condom_hiv_knowledge_pct",
    "Knowledge of HIV/AIDS among Adults (age 15-49 years) - Men who know that consistent condom use can reduce the chances of getting HIV/AIDS (%)": "men_condom_hiv_knowledge_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Currently married women who usually participate in household decisions (%)": "women_household_decisions_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Women who worked in the last 12 months who were paid in cash (%)": "women_paid_work_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Ever-married women who have ever experienced spousal violence (%)": "spousal_violence_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Ever-married women who have experienced violence during any pregnancy (%)": "pregnancy_violence_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Women owning a house and/or land (alone or jointly with others) (%)": "women_property_ownership_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Women having a bank or savings account that they themselves use (%)": "women_bank_account_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Women having a mobile phone that they themselves use (%)": "women_mobile_phone_pct",
    "Women's Empowerment and Gender Based Violence (age 15-49 years) - Women age 15-24 years who use hygienic methods of protection during their menstrual period (%)": "menstrual_hygiene_pct",
    "Tobacco Use and Alcohol Consumption among Adults (age 15-49 years) - Men who use any kind of tobacco (%)": "men_tobacco_pct",
    "Tobacco Use and Alcohol Consumption among Adults (age 15-49 years) - Men who consume alcohol (%)": "men_alcohol_pct",
}

# Indicators where a HIGHER NFHS-5 value than NFHS-4 baseline represents IMPROVEMENT.
# Everything not listed here is treated as "lower is better" (malnutrition, anaemia, violence, etc.)
HIGHER_IS_BETTER = {
    "female_school_attendance_pct", "electricity_access_pct", "clean_water_access_pct",
    "improved_sanitation_pct", "clean_cooking_fuel_pct", "iodized_salt_pct", "health_insurance_pct",
    "women_literacy_pct", "women_10yr_school_pct", "fp_any_method_pct", "fp_modern_method_pct",
    "fp_counselling_pct", "anc_first_trimester_pct", "anc_4plus_visits_pct", "ifa_100days_pct",
    "mcp_card_pct", "postnatal_care_mother_pct", "home_birth_facility_checkup_pct",
    "postnatal_care_child_pct", "institutional_delivery_pct", "institutional_delivery_public_pct",
    "skilled_birth_attendant_pct", "bcg_pct", "polio3_pct", "dpt3_pct", "measles_pct", "hepb3_pct",
    "diarrhoea_ors_pct", "diarrhoea_zinc_pct", "diarrhoea_facility_pct", "ari_facility_pct",
    "early_breastfeed_pct", "exclusive_breastfeed_pct", "complementary_feed_pct",
    "adequate_diet_breastfed_pct", "adequate_diet_nonbreastfed_pct", "adequate_diet_total_pct",
    "cervix_exam_pct", "breast_exam_pct", "oral_exam_pct", "women_hiv_knowledge_pct",
    "men_hiv_knowledge_pct", "women_condom_hiv_knowledge_pct", "men_condom_hiv_knowledge_pct",
    "women_household_decisions_pct", "women_paid_work_pct", "women_property_ownership_pct",
    "women_bank_account_pct", "women_mobile_phone_pct", "menstrual_hygiene_pct",
    "sex_ratio", "sex_ratio_at_birth", "birth_registration_pct",
}

# Explicit state-name overrides where fuzzy matching would fail or pick the wrong match
STATE_NAME_OVERRIDES = {
    "chattisgarh": "Chhattisgarh",
    "maharashtra": "Maharastra",           # NFHS-5 file has this typo'd spelling
    "delhi": "NCT of Delhi",
    "andaman and nicobar islands": "Andaman & Nicobar Islands",
}

# NFHS-5 states with no NFHS-4 equivalent (didn't exist as a separate entity in 2015-16)
NO_NFHS4_BASELINE = {"ladakh"}

# NFHS-4 UTs that were separate in 2015-16 but merged into one NFHS-5 UT in 2019-21
MERGE_INTO_NFHS5 = {
    "Dadra and Nagar Haveli & Daman and Diu": ["Dadra and Nagar Haveli", "Daman and Diu"],
}


def clean_numeric(val):
    if pd.isna(val):
        return np.nan
    s = re.sub(r"[^0-9.\-]", "", str(val).strip())
    if s in ("", "-"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def load_nfhs4_state_data() -> pd.DataFrame:
    """Load and clean the real NFHS-4 state-level factsheet (Survey=NFHS-4, Area=Total)."""
    if not NFHS4_RAW.exists():
        raise FileNotFoundError(f"NFHS-4 raw file not found at {NFHS4_RAW}")

    df = pd.read_csv(NFHS4_RAW, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    df = df[(df["Survey"] == "NFHS-4") & (df["Area"] == "Total")].copy()
    df = df[df["India/States/UTs"] != "India"].copy()

    rename_map = {}
    for raw_col, short_col in NFHS4_COLUMN_MAP.items():
        raw_stripped = raw_col.strip()
        if raw_stripped in df.columns:
            rename_map[raw_stripped] = short_col
        else:
            match, score, _ = process.extractOne(raw_stripped, df.columns.tolist(), scorer=fuzz.ratio)
            if score > 92:
                rename_map[match] = short_col

    df = df.rename(columns={"India/States/UTs": "state_nfhs4", **rename_map})
    keep_cols = ["state_nfhs4"] + [c for c in NFHS4_COLUMN_MAP.values() if c in df.columns]
    df = df[keep_cols].copy()

    for col in keep_cols[1:]:
        df[col] = df[col].apply(clean_numeric)

    print(f"  Loaded NFHS-4 state data: {len(df)} states/UTs x {len(keep_cols) - 1} indicators")
    return df.reset_index(drop=True)


def match_nfhs5_state(nfhs4_state: str, nfhs5_states: list) -> str | None:
    key = nfhs4_state.strip().lower()
    if key in NO_NFHS4_BASELINE:
        return None
    if key in STATE_NAME_OVERRIDES:
        return STATE_NAME_OVERRIDES[key]
    match, score, _ = process.extractOne(nfhs4_state, nfhs5_states, scorer=fuzz.token_sort_ratio)
    return match if score > 80 else None


def build_state_baseline(df4: pd.DataFrame, nfhs5_states: list) -> pd.DataFrame:
    """Map NFHS-4 rows onto NFHS-5 state names, averaging the merged Dadra/Daman UTs."""
    indicator_cols = [c for c in df4.columns if c != "state_nfhs4"]

    rows = []
    for nfhs5_target, nfhs4_sources in MERGE_INTO_NFHS5.items():
        subset = df4[df4["state_nfhs4"].isin(nfhs4_sources)]
        if subset.empty:
            continue
        averaged = subset[indicator_cols].mean(numeric_only=True)
        rows.append({"state": nfhs5_target, **averaged.to_dict()})

    already_merged_sources = {s for sources in MERGE_INTO_NFHS5.values() for s in sources}
    for _, row in df4[~df4["state_nfhs4"].isin(already_merged_sources)].iterrows():
        matched = match_nfhs5_state(row["state_nfhs4"], nfhs5_states)
        if matched is None:
            continue
        row_dict = {"state": matched, **{c: row[c] for c in indicator_cols}}
        rows.append(row_dict)

    baseline = pd.DataFrame(rows)
    print(f"  Matched {baseline['state'].nunique()}/{len(nfhs5_states)} NFHS-5 states to an NFHS-4 baseline")
    unmatched = set(nfhs5_states) - set(baseline["state"].unique())
    if unmatched:
        print(f"  No NFHS-4 baseline available for: {sorted(unmatched)}")
    return baseline


def integrate_nfhs4_with_nfhs5() -> pd.DataFrame:
    print("Integrating real NFHS-4 (2015-16) state baselines into NFHS-5 district data...")

    df4 = load_nfhs4_state_data()
    df5 = pd.read_parquet(NFHS5_PARQUET)

    # Drop any previously-added trend columns before re-merging (makes this script idempotent)
    df5 = df5[[c for c in df5.columns
               if not re.search(r"(_nfhs4_state$|_change_from_nfhs4$|_change_pct_from_nfhs4$)", c)]]

    nfhs5_states = sorted(df5["state"].unique().tolist())
    baseline = build_state_baseline(df4, nfhs5_states)

    indicator_cols = [c for c in baseline.columns if c != "state"]
    baseline_renamed = baseline.rename(columns={c: f"{c}_nfhs4_state" for c in indicator_cols})

    merged = df5.merge(baseline_renamed, on="state", how="left")

    new_cols = {}
    n_trend_indicators = 0
    for col in indicator_cols:
        nfhs4_col = f"{col}_nfhs4_state"
        if col not in merged.columns or nfhs4_col not in merged.columns:
            continue
        change_col = f"{col}_change_from_nfhs4"
        change_pct_col = f"{col}_change_pct_from_nfhs4"

        new_cols[change_col] = (merged[col] - merged[nfhs4_col]).round(2)
        new_cols[change_pct_col] = pd.Series(
            np.where(
                merged[nfhs4_col].notna() & (merged[nfhs4_col] != 0),
                ((merged[col] - merged[nfhs4_col]) / merged[nfhs4_col] * 100).round(2),
                np.nan,
            ),
            index=merged.index,
        )
        n_trend_indicators += 1

    merged = pd.concat([merged, pd.DataFrame(new_cols, index=merged.index)], axis=1)

    print(f"  Added real trend columns for {n_trend_indicators} indicators "
          f"({n_trend_indicators * 3} new columns: baseline, change, change_pct)")

    merged.to_parquet(OUTPUT_PARQUET, index=False)
    merged.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    merged.to_parquet(OUTPUT_TRENDS_PARQUET, index=False)
    merged.to_csv(OUTPUT_TRENDS_CSV, index=False, encoding="utf-8")
    print(f"[OK] Saved enriched dataset: {OUTPUT_PARQUET} ({len(merged)} rows x {len(merged.columns)} cols)")

    update_schema_with_trends(indicator_cols)
    generate_trend_summary(merged, indicator_cols)
    enrich_district_summaries(merged)

    return merged


def enrich_district_summaries(merged: pd.DataFrame) -> None:
    """Append a real trend sentence + trend metadata to each district's ChromaDB summary."""
    if not OUTPUT_SUMMARIES.exists():
        print("  [WARN] district_summaries.json not found — skipping summary enrichment")
        return

    with open(OUTPUT_SUMMARIES, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    by_district_id = {s["metadata"]["district_id"]: s for s in summaries}
    # Strip any stale trend sentence from a previous run before re-appending
    trend_marker = " Trend vs NFHS-4 (2015-16 state baseline):"
    for s in summaries:
        idx = s["text"].find(trend_marker)
        if idx != -1:
            s["text"] = s["text"][:idx]

    for _, row in merged.iterrows():
        district_id = int(row["district_id"])
        s = by_district_id.get(district_id)
        if s is None:
            continue

        parts = []
        for col, label in SUMMARY_TREND_INDICATORS:
            change_col = f"{col}_change_from_nfhs4"
            if change_col not in row or pd.isna(row[change_col]):
                continue
            change = row[change_col]
            direction = "up" if change > 0 else ("down" if change < 0 else "unchanged")
            parts.append(f"{label} {direction} {abs(change):.1f}pp")
            s["metadata"][change_col] = float(change)

        if parts:
            s["text"] += f"{trend_marker} " + ", ".join(parts) + "."

    with open(OUTPUT_SUMMARIES, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"[OK] Enriched district_summaries.json with real trend sentences ({len(summaries)} districts)")


def update_schema_with_trends(indicator_cols: list):
    """Add schema entries for the new baseline/change/change_pct columns."""
    if not OUTPUT_SCHEMA.exists():
        print("  [WARN] schema.json not found — skipping schema update")
        return

    with open(OUTPUT_SCHEMA, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Drop any stale trend schema entries from a previous run
    schema = {k: v for k, v in schema.items()
              if not re.search(r"(_nfhs4_state$|_change_from_nfhs4$|_change_pct_from_nfhs4$)", k)}

    for col in indicator_cols:
        base_desc = schema.get(col, {}).get("description", col.replace("_", " "))
        unit = schema.get(col, {}).get("unit", "percent")
        lower_is_better = col not in HIGHER_IS_BETTER

        schema[f"{col}_nfhs4_state"] = {
            "description": f"{base_desc} — NFHS-4 (2015-16) STATE-level baseline (district's parent state average, not district-level)",
            "unit": unit,
            "cluster": "trend",
        }
        schema[f"{col}_change_from_nfhs4"] = {
            "description": f"{base_desc} — change from NFHS-4 state baseline to NFHS-5 district value "
                            f"(negative = decrease, positive = increase; "
                            f"{'decrease is improvement' if lower_is_better else 'increase is improvement'})",
            "unit": unit,
            "cluster": "trend",
        }
        schema[f"{col}_change_pct_from_nfhs4"] = {
            "description": f"{base_desc} — relative % change from NFHS-4 state baseline to NFHS-5 district value",
            "unit": "percent_change",
            "cluster": "trend",
        }

    with open(OUTPUT_SCHEMA, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"[OK] Updated schema.json ({len(schema)} total columns documented)")


def generate_trend_summary(merged: pd.DataFrame, indicator_cols: list):
    summary = {
        "data_source_note": (
            "NFHS-4 (2015-16) is only available as a STATE-level factsheet in this project's "
            "dataset. Trend columns compare each NFHS-5 district to its own state's NFHS-4 "
            "baseline, not to a true district-level NFHS-4 figure."
        ),
        "districts_analyzed": int(len(merged)),
        "indicators_with_trend_data": n_valid_indicators(merged, indicator_cols),
        "survey_gap": "~4-5 years (2015-16 to 2019-21)",
    }

    if "stunting_pct_change_from_nfhs4" in merged.columns:
        avg_change = merged["stunting_pct_change_from_nfhs4"].mean()
        summary["national_stunting_change_from_nfhs4_state_baseline"] = round(float(avg_change), 2)

    if "stunting_pct_change_from_nfhs4" in merged.columns:
        state_change = merged.groupby("state")["stunting_pct_change_from_nfhs4"].mean().sort_values()
        summary["states_with_largest_stunting_reduction"] = {
            k: round(float(v), 2) for k, v in state_change.head(5).to_dict().items()
        }
        summary["states_with_largest_stunting_increase"] = {
            k: round(float(v), 2) for k, v in state_change.tail(5).to_dict().items()
        }

    with open(TREND_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"[OK] Saved trend summary: {TREND_SUMMARY_PATH}")


def n_valid_indicators(merged: pd.DataFrame, indicator_cols: list) -> int:
    count = 0
    for col in indicator_cols:
        change_col = f"{col}_change_from_nfhs4"
        if change_col in merged.columns and merged[change_col].notna().any():
            count += 1
    return count


if __name__ == "__main__":
    result = integrate_nfhs4_with_nfhs5()
    print(f"\n[DONE] NFHS-4 trend integration complete for {len(result)} districts.")
