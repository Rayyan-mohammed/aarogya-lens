"""
BharatHealth Analyst — Data Pipeline
Cleans, normalises, and enriches NFHS-5 district data.
Outputs: cleaned Parquet, schema JSON, district summaries for ChromaDB.
"""

import pandas as pd
import numpy as np
import json
import re
import os
from pathlib import Path
from rapidfuzz import process, fuzz

# ─── Paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
DATASET_DIR = ROOT / "dataset"
BACKEND_DIR = ROOT / "backend"
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NFHS5_RAW = DATASET_DIR / "NFHS_5_India_Districts_Factsheet_Data_datafile.csv"
NFHS4_RAW = DATASET_DIR / "NFHS-4_NFHS3_Factsheet-All_India_Indicators_R1.csv"
CENSUS_RAW = DATASET_DIR / "india-districts-census-2011.csv"

OUTPUT_PARQUET = DATA_DIR / "nfhs5_clean.parquet"
OUTPUT_SCHEMA = DATA_DIR / "schema.json"
OUTPUT_SUMMARIES = DATA_DIR / "district_summaries.json"
OUTPUT_CSV = DATA_DIR / "nfhs5_clean.csv"


# ─── Column name mapping: raw → clean short names ────────────────────────────
COLUMN_MAP = {
    "District Names": "district",
    "State/UT": "state",
    "Number of Households surveyed": "households_surveyed",
    "Number of Women age 15-49 years interviewed": "women_interviewed",
    "Number of Men age 15-54 years interviewed": "men_interviewed",
    "Female population age 6 years and above who ever attended school (%)": "female_school_attendance_pct",
    "Population below age 15 years (%)": "pop_below_15_pct",
    " Sex ratio of the total population (females per 1,000 males)": "sex_ratio",
    "Sex ratio at birth for children born in the last five years (females per 1,000 males)": "sex_ratio_at_birth",
    "Children under age 5 years whose birth was registered with the civil authority (%)": "birth_registration_pct",
    "Deaths in the last 3 years registered with the civil authority (%)": "death_registration_pct",
    "Population living in households with electricity (%)": "electricity_access_pct",
    "Population living in households with an improved drinking-water source1 (%)": "clean_water_access_pct",
    "Population living in households that use an improved sanitation facility2 (%)": "improved_sanitation_pct",
    "Households using clean fuel for cooking3 (%)": "clean_cooking_fuel_pct",
    "Households using iodized salt (%)": "iodized_salt_pct",
    "Households with any usual member covered under a health insurance/financing scheme (%)": "health_insurance_pct",
    "Children age 5 years who attended pre-primary school during the school year 2019-20 (%)": "preprimary_school_pct",
    "Women (age 15-49) who are literate4 (%)": "women_literacy_pct",
    "Women (age 15-49)  with 10 or more years of schooling (%)": "women_10yr_school_pct",
    "Women age 20-24 years married before age 18 years (%)": "child_marriage_pct",
    "Births in the 5 years preceding the survey that are third or higher order (%)": "births_3rd_plus_order_pct",
    "Women age 15-19 years who were already mothers or pregnant at the time of the survey (%)": "teen_pregnancy_pct",
    "Women age 15-24 years who use hygienic methods of protection during their menstrual period5 (%)": "menstrual_hygiene_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Any method6 (%)": "fp_any_method_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Any modern method6 (%)": "fp_modern_method_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Female sterilization (%)": "fp_female_sterilization_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Male sterilization (%)": "fp_male_sterilization_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - IUD/PPIUD (%)": "fp_iud_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Pill (%)": "fp_pill_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Condom (%)": "fp_condom_pct",
    "Current Use of Family Planning Methods (Currently Married Women Age 15-49  years) - Injectables (%)": "fp_injectables_pct",
    "Total Unmet need for Family Planning (Currently Married Women Age 15-49  years)7 (%)": "unmet_fp_need_pct",
    "Unmet need for spacing (Currently Married Women Age 15-49  years)7 (%)": "unmet_fp_spacing_pct",
    "Health worker ever talked to female non-users about family planning (%)": "fp_counselling_pct",
    "Current users ever told about side effects of current method of family planning8 (%)": "fp_side_effects_counselled_pct",
    "Mothers who had an antenatal check-up in the first trimester  (for last birth in the 5 years before the survey) (%)": "anc_first_trimester_pct",
    "Mothers who had at least 4 antenatal care visits  (for last birth in the 5 years before the survey) (%)": "anc_4plus_visits_pct",
    "Mothers whose last birth was protected against neonatal tetanus (for last birth in the 5 years before the survey)9 (%)": "tetanus_protection_pct",
    "Mothers who consumed iron folic acid for 100 days or more when they were pregnant (for last birth in the 5 years before the survey) (%)": "ifa_100days_pct",
    "Mothers who consumed iron folic acid for 180 days or more when they were pregnant (for last birth in the 5 years before the survey} (%)": "ifa_180days_pct",
    "Registered pregnancies for which the mother received a Mother and Child Protection (MCP) card (for last birth in the 5 years before the survey) (%)": "mcp_card_pct",
    "Mothers who received postnatal care from a doctor/nurse/LHV/ANM/midwife/other health personnel within 2 days of delivery (for last birth in the 5 years before the survey) (%)": "postnatal_care_mother_pct",
    "Average out-of-pocket expenditure per delivery in a public health facility (for last birth in the 5 years before the survey) (Rs.)": "oop_delivery_cost_rs",
    "Children born at home who were taken to a health facility for a check-up within 24 hours of birth (for last birth in the 5 years before the survey} (%)": "home_birth_facility_checkup_pct",
    "Children who received postnatal care from a doctor/nurse/LHV/ANM/midwife/ other health personnel within 2 days of delivery (for last birth in the 5 years before the survey) (%)": "postnatal_care_child_pct",
    "Institutional births (in the 5 years before the survey) (%)": "institutional_delivery_pct",
    "Institutional births in public facility (in the 5 years before the survey) (%)": "institutional_delivery_public_pct",
    "Home births that were conducted by skilled health personnel  (in the 5 years before the survey)10 (%)": "skilled_home_birth_pct",
    "Births attended by skilled health personnel (in the 5 years before the survey)10 (%)": "skilled_birth_attendant_pct",
    "Births delivered by caesarean section (in the 5 years before the survey) (%)": "csection_pct",
    "Births in a private health facility that were delivered by caesarean section (in the 5 years before the survey) (%)": "csection_private_pct",
    "Births in a public health facility that were delivered by caesarean section (in the 5 years before the survey) (%)": "csection_public_pct",
    "Children age 12-23 months fully vaccinated based on information from either vaccination card or mother's recall11 (%)": "fully_vaccinated_recall_pct",
    "Children age 12-23 months fully vaccinated based on information from vaccination card only12 (%)": "fully_vaccinated_card_pct",
    "Children age 12-23 months who have received BCG (%)": "bcg_pct",
    "Children age 12-23 months who have received 3 doses of polio vaccine (%)": "polio3_pct",
    "Children age 12-23 months who have received 3 doses of DPT vaccine (%)": "dpt3_pct",
    "Children age 12-23 months who have received measles vaccine (%)": "measles_pct",
    "Children age 12-23 months who have received 3 doses of Hepatitis B vaccine (%)": "hepb3_pct",
    "Children age 12-23 months who received most of the vaccinations in public health facility (%)": "vaccinated_in_public_pct",
    "Children age 12-23 months who received most of the vaccinations in private health facility (%)": "vaccinated_in_private_pct",
    "Children with diarrhoea in the last 2 weeks who received oral rehydration salts (ORS) (%)": "diarrhoea_ors_pct",
    "Children with diarrhoea in the last 2 weeks who received zinc (%)": "diarrhoea_zinc_pct",
    "Children with diarrhoea in the last 2 weeks taken to a health facility (%)": "diarrhoea_facility_pct",
    "Children with fever or symptoms of ARI in the last 2 weeks preceding the survey taken to a health facility (%)": "ari_facility_pct",
    "Children under age 3 years breastfed within one hour of birth (%)": "early_breastfeed_pct",
    "Children under age 6 months exclusively breastfed (%)": "exclusive_breastfeed_pct",
    "Children age 6-8 months receiving solid or semi-solid food and breastmilk (%)": "complementary_feed_pct",
    "Breastfeeding children age 6-23 months receiving an adequate diet (%)": "adequate_diet_breastfed_pct",
    "Non-breastfeeding children age 6-23 months receiving an adequate diet (%)": "adequate_diet_nonbreastfed_pct",
    "Total children age 6-23 months receiving an adequate diet (%)": "adequate_diet_total_pct",
    "Children under 5 years who are stunted (height-for-age)13 (%)": "stunting_pct",
    "Children under 5 years who are wasted (weight-for-height)13 (%)": "wasting_pct",
    "Children under 5 years who are severely wasted (weight-for-height)13 (%)": "severe_wasting_pct",
    "Children under 5 years who are underweight (weight-for-age)13 (%)": "underweight_pct",
    "Children under 5 years who are overweight (weight-for-height)13 (%)": "overweight_children_pct",
    "Women whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2)14 (%)": "women_low_bmi_pct",
    "Women who are overweight or obese (BMI ≥25.0 kg/m2)14 (%)": "women_overweight_pct",
    "Men whose Body Mass Index (BMI) is below normal (BMI <18.5 kg/m2) (%)": "men_low_bmi_pct",
    "Men who are overweight or obese (BMI ≥25.0 kg/m2) (%)": "men_overweight_pct",
    "Children age 6-59 months who are anaemic (<11.0 g/dl) (%)": "anaemia_children_pct",
    "Non-pregnant women age 15-49 years who are anaemic (<12.0 g/dl) (%)": "anaemia_nonpregnant_women_pct",
    "Pregnant women age 15-49 years who are anaemic (<11.0 g/dl) (%)": "anaemia_pregnant_women_pct",
    "All women age 15-49 years who are anaemic (%)": "anaemia_all_women_pct",
    "Men age 15-49 years who are anaemic (<13.0 g/dl) (%)": "anaemia_men_pct",
    "Women - Blood sugar level - high (>140 mg/dl) (%)": "women_high_blood_sugar_pct",
    "Women - Blood sugar level - very high (>160 mg/dl) (%)": "women_very_high_blood_sugar_pct",
    "Men - Blood sugar level - high (>140 mg/dl) (%)": "men_high_blood_sugar_pct",
    "Men - Blood sugar level - very high (>160 mg/dl) (%)": "men_very_high_blood_sugar_pct",
    "Women - Slightly above normal (Systolic 140-159 mm of Hg and/or Diastolic 90-99 mm of Hg) (%)": "women_hypertension_mild_pct",
    "Women - Moderately high (Systolic 160-179 mm of Hg and/or Diastolic 100-109 mm of Hg) (%)": "women_hypertension_moderate_pct",
    "Women - Very high (Systolic ≥ 180 mm of Hg and/or Diastolic ≥ 110 mm of Hg) (%)": "women_hypertension_severe_pct",
    "Men - Slightly above normal (Systolic 140-159 mm of Hg and/or Diastolic 90-99 mm of Hg) (%)": "men_hypertension_mild_pct",
    "Men - Moderately high (Systolic 160-179 mm of Hg and/or Diastolic 100-109 mm of Hg) (%)": "men_hypertension_moderate_pct",
    "Men - Very high (Systolic ≥ 180 mm of Hg and/or Diastolic ≥ 110 mm of Hg) (%)": "men_hypertension_severe_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Cervix (%)": "cervix_exam_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Breast (%)": "breast_exam_pct",
    "Women Age 15-49 Years Who Have Ever Undergone Examinations of: - Oral cavity (%)": "oral_exam_pct",
    "Women who have comprehensive knowledge of HIV/AIDS (%)": "women_hiv_knowledge_pct",
    "Men who have comprehensive knowledge of HIV/AIDS (%)": "men_hiv_knowledge_pct",
    "Women who know that consistent condom use can reduce the chances of getting HIV/AIDS (%)": "women_condom_hiv_knowledge_pct",
    "Men who know that consistent condom use can reduce the chances of getting HIV/AIDS (%)": "men_condom_hiv_knowledge_pct",
    "Currently married women who usually participate in household decisions (%)": "women_household_decisions_pct",
    "Women who worked in the last 12 months who were paid in cash (%)": "women_paid_work_pct",
    "Ever-married women who have ever experienced spousal violence (%)": "spousal_violence_pct",
    "Ever-married women who have experienced violence during any pregnancy (%)": "pregnancy_violence_pct",
    "Women owning a house and/or land (alone or jointly with others) (%)": "women_property_ownership_pct",
    "Women having a bank or savings account that they themselves use (%)": "women_bank_account_pct",
    "Women having a mobile phone that they themselves use (%)": "women_mobile_phone_pct",
    "Men who use any kind of tobacco (%)": "men_tobacco_pct",
    "Men who consume alcohol (%)": "men_alcohol_pct",
}

# Indicator cluster mapping for short column names
INDICATOR_CLUSTERS = {
    "child_nutrition": ["stunting_pct", "wasting_pct", "severe_wasting_pct", "underweight_pct", "overweight_children_pct"],
    "maternal_health": ["institutional_delivery_pct", "institutional_delivery_public_pct", "anc_4plus_visits_pct",
                        "anc_first_trimester_pct", "postnatal_care_mother_pct", "csection_pct", "skilled_birth_attendant_pct"],
    "anaemia": ["anaemia_children_pct", "anaemia_nonpregnant_women_pct", "anaemia_pregnant_women_pct",
                "anaemia_all_women_pct", "anaemia_men_pct"],
    "vaccination": ["fully_vaccinated_recall_pct", "fully_vaccinated_card_pct", "bcg_pct", "polio3_pct", "dpt3_pct", "measles_pct", "hepb3_pct"],
    "sanitation": ["improved_sanitation_pct", "clean_water_access_pct", "electricity_access_pct", "clean_cooking_fuel_pct"],
    "ncd": ["women_high_blood_sugar_pct", "men_high_blood_sugar_pct", "women_hypertension_mild_pct",
            "men_hypertension_mild_pct", "women_overweight_pct", "men_overweight_pct"],
    "family_planning": ["fp_any_method_pct", "fp_modern_method_pct", "unmet_fp_need_pct"],
    "women_empowerment": ["women_literacy_pct", "women_bank_account_pct", "women_mobile_phone_pct",
                          "women_household_decisions_pct", "women_property_ownership_pct"],
}

# Schema descriptions for each short column
SCHEMA_DESCRIPTIONS = {
    "district": {"description": "District name", "unit": "text", "cluster": "identifier"},
    "state": {"description": "State or Union Territory name", "unit": "text", "cluster": "identifier"},
    "households_surveyed": {"description": "Number of households surveyed in NFHS-5", "unit": "count", "cluster": "sample"},
    "women_interviewed": {"description": "Number of women aged 15-49 years interviewed", "unit": "count", "cluster": "sample"},
    "men_interviewed": {"description": "Number of men aged 15-54 years interviewed", "unit": "count", "cluster": "sample"},
    "sex_ratio": {"description": "Females per 1,000 males in total population", "unit": "ratio", "cluster": "demography"},
    "sex_ratio_at_birth": {"description": "Females per 1,000 males among children born in last 5 years", "unit": "ratio", "cluster": "demography"},
    "electricity_access_pct": {"description": "% of population with electricity access", "unit": "percent", "cluster": "sanitation"},
    "clean_water_access_pct": {"description": "% with improved drinking water source", "unit": "percent", "cluster": "sanitation"},
    "improved_sanitation_pct": {"description": "% using improved sanitation facility", "unit": "percent", "cluster": "sanitation"},
    "clean_cooking_fuel_pct": {"description": "% using clean fuel for cooking", "unit": "percent", "cluster": "sanitation"},
    "health_insurance_pct": {"description": "% of households with health insurance coverage", "unit": "percent", "cluster": "healthcare_access"},
    "women_literacy_pct": {"description": "% of women aged 15-49 who are literate", "unit": "percent", "cluster": "women_empowerment"},
    "child_marriage_pct": {"description": "% of women aged 20-24 married before age 18 (child marriage rate)", "unit": "percent", "cluster": "women_empowerment"},
    "teen_pregnancy_pct": {"description": "% of women aged 15-19 who are already mothers or pregnant", "unit": "percent", "cluster": "maternal_health"},
    "fp_modern_method_pct": {"description": "% of currently married women using modern family planning methods", "unit": "percent", "cluster": "family_planning"},
    "unmet_fp_need_pct": {"description": "% of married women with unmet need for family planning", "unit": "percent", "cluster": "family_planning"},
    "anc_first_trimester_pct": {"description": "% of mothers with antenatal check-up in first trimester", "unit": "percent", "cluster": "maternal_health"},
    "anc_4plus_visits_pct": {"description": "% of mothers with 4 or more antenatal care visits", "unit": "percent", "cluster": "maternal_health"},
    "ifa_100days_pct": {"description": "% of mothers who consumed IFA tablets for 100+ days during pregnancy", "unit": "percent", "cluster": "maternal_health"},
    "postnatal_care_mother_pct": {"description": "% of mothers receiving postnatal care within 2 days", "unit": "percent", "cluster": "maternal_health"},
    "oop_delivery_cost_rs": {"description": "Average out-of-pocket delivery expenditure in public facility (Rs.)", "unit": "rupees", "cluster": "maternal_health"},
    "institutional_delivery_pct": {"description": "% of births occurring in a health facility (institutional delivery)", "unit": "percent", "cluster": "maternal_health"},
    "institutional_delivery_public_pct": {"description": "% of births in public health facilities", "unit": "percent", "cluster": "maternal_health"},
    "csection_pct": {"description": "% of births by caesarean section", "unit": "percent", "cluster": "maternal_health"},
    "skilled_birth_attendant_pct": {"description": "% of births attended by skilled health personnel", "unit": "percent", "cluster": "maternal_health"},
    "fully_vaccinated_recall_pct": {"description": "% of children 12-23 months fully vaccinated (card or recall)", "unit": "percent", "cluster": "vaccination"},
    "fully_vaccinated_card_pct": {"description": "% of children 12-23 months fully vaccinated (card only)", "unit": "percent", "cluster": "vaccination"},
    "bcg_pct": {"description": "% of children 12-23 months who received BCG vaccine", "unit": "percent", "cluster": "vaccination"},
    "polio3_pct": {"description": "% of children 12-23 months who received 3 doses of polio vaccine", "unit": "percent", "cluster": "vaccination"},
    "dpt3_pct": {"description": "% of children 12-23 months who received 3 doses of DPT vaccine", "unit": "percent", "cluster": "vaccination"},
    "measles_pct": {"description": "% of children 12-23 months who received measles vaccine", "unit": "percent", "cluster": "vaccination"},
    "hepb3_pct": {"description": "% of children 12-23 months who received 3 doses of Hepatitis B vaccine", "unit": "percent", "cluster": "vaccination"},
    "diarrhoea_ors_pct": {"description": "% of children with diarrhoea who received ORS", "unit": "percent", "cluster": "child_health"},
    "early_breastfeed_pct": {"description": "% of children breastfed within 1 hour of birth", "unit": "percent", "cluster": "child_nutrition"},
    "exclusive_breastfeed_pct": {"description": "% of infants under 6 months exclusively breastfed", "unit": "percent", "cluster": "child_nutrition"},
    "stunting_pct": {"description": "% of children under 5 who are stunted (low height-for-age, chronic malnutrition)", "unit": "percent", "cluster": "child_nutrition"},
    "wasting_pct": {"description": "% of children under 5 who are wasted (low weight-for-height, acute malnutrition)", "unit": "percent", "cluster": "child_nutrition"},
    "severe_wasting_pct": {"description": "% of children under 5 who are severely wasted", "unit": "percent", "cluster": "child_nutrition"},
    "underweight_pct": {"description": "% of children under 5 who are underweight (low weight-for-age)", "unit": "percent", "cluster": "child_nutrition"},
    "overweight_children_pct": {"description": "% of children under 5 who are overweight", "unit": "percent", "cluster": "child_nutrition"},
    "women_low_bmi_pct": {"description": "% of women 15-49 with BMI below normal (<18.5)", "unit": "percent", "cluster": "adult_nutrition"},
    "women_overweight_pct": {"description": "% of women 15-49 who are overweight or obese (BMI ≥25)", "unit": "percent", "cluster": "ncd"},
    "men_low_bmi_pct": {"description": "% of men 15-49 with BMI below normal (<18.5)", "unit": "percent", "cluster": "adult_nutrition"},
    "men_overweight_pct": {"description": "% of men 15-49 who are overweight or obese (BMI ≥25)", "unit": "percent", "cluster": "ncd"},
    "anaemia_children_pct": {"description": "% of children 6-59 months who are anaemic (<11.0 g/dl)", "unit": "percent", "cluster": "anaemia"},
    "anaemia_nonpregnant_women_pct": {"description": "% of non-pregnant women 15-49 who are anaemic (<12.0 g/dl)", "unit": "percent", "cluster": "anaemia"},
    "anaemia_pregnant_women_pct": {"description": "% of pregnant women 15-49 who are anaemic (<11.0 g/dl)", "unit": "percent", "cluster": "anaemia"},
    "anaemia_all_women_pct": {"description": "% of all women 15-49 who are anaemic", "unit": "percent", "cluster": "anaemia"},
    "anaemia_men_pct": {"description": "% of men 15-49 who are anaemic (<13.0 g/dl)", "unit": "percent", "cluster": "anaemia"},
    "women_high_blood_sugar_pct": {"description": "% of women with high blood sugar (>140 mg/dl)", "unit": "percent", "cluster": "ncd"},
    "men_high_blood_sugar_pct": {"description": "% of men with high blood sugar (>140 mg/dl)", "unit": "percent", "cluster": "ncd"},
    "women_hypertension_mild_pct": {"description": "% of women with mildly elevated blood pressure (140-159 systolic)", "unit": "percent", "cluster": "ncd"},
    "men_hypertension_mild_pct": {"description": "% of men with mildly elevated blood pressure (140-159 systolic)", "unit": "percent", "cluster": "ncd"},
    "women_hypertension_severe_pct": {"description": "% of women with severely high blood pressure (≥180 systolic)", "unit": "percent", "cluster": "ncd"},
    "men_hypertension_severe_pct": {"description": "% of men with severely high blood pressure (≥180 systolic)", "unit": "percent", "cluster": "ncd"},
    "spousal_violence_pct": {"description": "% of ever-married women who experienced spousal violence", "unit": "percent", "cluster": "women_empowerment"},
    "women_bank_account_pct": {"description": "% of women with a bank or savings account they use", "unit": "percent", "cluster": "women_empowerment"},
    "women_mobile_phone_pct": {"description": "% of women with a mobile phone they use", "unit": "percent", "cluster": "women_empowerment"},
    "women_household_decisions_pct": {"description": "% of married women who participate in household decisions", "unit": "percent", "cluster": "women_empowerment"},
    "women_property_ownership_pct": {"description": "% of women owning a house and/or land", "unit": "percent", "cluster": "women_empowerment"},
    "men_tobacco_pct": {"description": "% of men who use any kind of tobacco", "unit": "percent", "cluster": "lifestyle"},
    "men_alcohol_pct": {"description": "% of men who consume alcohol", "unit": "percent", "cluster": "lifestyle"},
    "menstrual_hygiene_pct": {"description": "% of women 15-24 using hygienic menstrual protection methods", "unit": "percent", "cluster": "women_empowerment"},
    "birth_registration_pct": {"description": "% of children under 5 whose birth was registered", "unit": "percent", "cluster": "demography"},
    "iodized_salt_pct": {"description": "% of households using iodized salt", "unit": "percent", "cluster": "nutrition"},
    "pop_below_15_pct": {"description": "% of population below age 15 years", "unit": "percent", "cluster": "demography"},
    "female_school_attendance_pct": {"description": "% of female population age 6+ who ever attended school", "unit": "percent", "cluster": "women_empowerment"},
}


def clean_numeric(val):
    """Convert messy numeric strings to float, return NaN if not possible."""
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    # Remove footnote markers like '(23.4)' becoming '23.4', remove non-numeric chars except . and -
    s = re.sub(r'[^0-9.\-]', '', s)
    if s == '' or s == '-':
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def normalize_name(name: str) -> str:
    """Normalize district/state name for matching."""
    return re.sub(r'\s+', ' ', str(name).strip().lower())


def load_and_clean_nfhs5() -> pd.DataFrame:
    print("Loading NFHS-5 raw data...")
    df = pd.read_csv(NFHS5_RAW, encoding='utf-8-sig', low_memory=False)

    # Strip column names
    df.columns = [c.strip() for c in df.columns]

    # Drop note columns (columns starting with 'Note of')
    df = df[[c for c in df.columns if not c.startswith('Note of')]]

    print(f"  Raw: {len(df)} rows × {len(df.columns)} columns (after dropping Note columns)")

    # Rename columns using our map — only rename columns that exist
    rename_map = {}
    for raw_name, clean_name in COLUMN_MAP.items():
        raw_stripped = raw_name.strip()
        if raw_stripped in df.columns:
            rename_map[raw_stripped] = clean_name
        else:
            # Try fuzzy match
            match, score, _ = process.extractOne(raw_stripped, df.columns.tolist(), scorer=fuzz.ratio)
            if score > 85:
                rename_map[match] = clean_name

    df = df.rename(columns=rename_map)

    # Keep only columns we've mapped (drop unnamed/extra)
    mapped_cols = list(COLUMN_MAP.values())
    available = [c for c in mapped_cols if c in df.columns]
    df = df[available].copy()

    # Clean district and state names
    df['district'] = df['district'].astype(str).str.strip()
    df['state'] = df['state'].astype(str).str.strip()

    # Drop rows where district or state is missing
    df = df.dropna(subset=['district', 'state'])
    df = df[df['district'].str.len() > 0]
    df = df[df['state'].str.len() > 0]

    # Convert all numeric columns
    numeric_cols = [c for c in df.columns if c not in ['district', 'state']]
    for col in numeric_cols:
        df[col] = df[col].apply(clean_numeric)

    print(f"  Clean: {len(df)} rows × {len(df.columns)} columns")
    return df.reset_index(drop=True)


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns: ranks, percentiles, composite scores."""
    print("Computing derived columns...")

    # National percentile rank for key indicators
    key_indicators = [
        'stunting_pct', 'wasting_pct', 'underweight_pct', 'anaemia_children_pct',
        'anaemia_all_women_pct', 'institutional_delivery_pct', 'fully_vaccinated_recall_pct',
        'improved_sanitation_pct', 'anc_4plus_visits_pct', 'women_literacy_pct',
        'child_marriage_pct', 'unmet_fp_need_pct', 'spousal_violence_pct',
    ]

    for col in key_indicators:
        if col in df.columns:
            # Percentile rank (0=worst, 100=best)
            # For "lower is better" indicators, reverse rank
            lower_is_better = ['stunting_pct', 'wasting_pct', 'underweight_pct',
                                'anaemia_children_pct', 'anaemia_all_women_pct',
                                'child_marriage_pct', 'unmet_fp_need_pct', 'spousal_violence_pct']
            rank_col = f"{col}_national_rank"
            pct_col = f"{col}_national_percentile"
            if col in lower_is_better:
                df[rank_col] = pd.array(df[col].rank(ascending=True, na_option='bottom').round().values, dtype='Int64')
                df[pct_col] = (100 - df[col].rank(pct=True, na_option='bottom') * 100).round(1)
            else:
                df[rank_col] = pd.array(df[col].rank(ascending=False, na_option='bottom').round().values, dtype='Int64')
                df[pct_col] = (df[col].rank(pct=True, na_option='bottom') * 100).round(1)

    # State-level rank for stunting and anaemia
    for col in ['stunting_pct', 'anaemia_children_pct', 'institutional_delivery_pct']:
        if col in df.columns:
            state_rank_col = f"{col}_state_rank"
            lower_is_better = col in ['stunting_pct', 'anaemia_children_pct']
            df[state_rank_col] = pd.array(
                df.groupby('state')[col].rank(ascending=lower_is_better, na_option='bottom').round().values,
                dtype='Int64'
            )

    # Composite child health score (0-100, higher = better)
    child_cols = ['stunting_pct', 'wasting_pct', 'underweight_pct', 'anaemia_children_pct', 'fully_vaccinated_recall_pct']
    child_cols_avail = [c for c in child_cols if c in df.columns]
    if len(child_cols_avail) >= 3:
        # For malnutrition (lower is better), invert; for vaccination (higher is better), keep
        malnutrition_cols = [c for c in child_cols_avail if c != 'fully_vaccinated_recall_pct']
        df['child_health_score'] = np.nan
        components = []
        for c in malnutrition_cols:
            col_max = df[c].max()
            if col_max > 0:
                components.append(100 - (df[c] / col_max * 100))
        if 'fully_vaccinated_recall_pct' in df.columns:
            col_max = df['fully_vaccinated_recall_pct'].max()
            if col_max > 0:
                components.append(df['fully_vaccinated_recall_pct'] / col_max * 100)
        if components:
            df['child_health_score'] = pd.concat(components, axis=1).mean(axis=1).round(1)

    # Composite maternal health score
    mat_cols = ['institutional_delivery_pct', 'anc_4plus_visits_pct', 'postnatal_care_mother_pct', 'skilled_birth_attendant_pct']
    mat_cols_avail = [c for c in mat_cols if c in df.columns]
    if mat_cols_avail:
        df['maternal_health_score'] = df[mat_cols_avail].mean(axis=1).round(1)

    # District ID
    df.insert(0, 'district_id', range(1, len(df) + 1))

    print(f"  Final: {len(df)} rows × {len(df.columns)} columns")
    return df


def generate_schema_json(df: pd.DataFrame) -> dict:
    """Generate schema JSON from dataframe columns and descriptions."""
    schema = {}
    for col in df.columns:
        if col in SCHEMA_DESCRIPTIONS:
            schema[col] = SCHEMA_DESCRIPTIONS[col].copy()
        elif col.endswith('_national_rank') or col.endswith('_state_rank'):
            base = col.replace('_national_rank', '').replace('_state_rank', '')
            schema[col] = {
                "description": f"National rank for {base} (1=worst district)",
                "unit": "rank",
                "cluster": "derived"
            }
        elif col.endswith('_national_percentile'):
            base = col.replace('_national_percentile', '')
            schema[col] = {
                "description": f"National percentile for {base} (100=best performing)",
                "unit": "percentile",
                "cluster": "derived"
            }
        elif col == 'child_health_score':
            schema[col] = {"description": "Composite child health score (0-100, 100=best)", "unit": "score", "cluster": "derived"}
        elif col == 'maternal_health_score':
            schema[col] = {"description": "Composite maternal health score (0-100, 100=best)", "unit": "score", "cluster": "derived"}
        elif col == 'district_id':
            schema[col] = {"description": "Unique district identifier", "unit": "id", "cluster": "identifier"}
        else:
            schema[col] = {"description": col.replace('_', ' '), "unit": "unknown", "cluster": "other"}

    # Add indicator cluster info
    for cluster, cols in INDICATOR_CLUSTERS.items():
        for col in cols:
            if col in schema:
                schema[col]['indicator_cluster'] = cluster

    return schema


def generate_district_summaries(df: pd.DataFrame) -> list:
    """Generate natural language summaries for ChromaDB embedding."""
    summaries = []
    for _, row in df.iterrows():
        district = row.get('district', 'Unknown')
        state = row.get('state', 'Unknown')

        def fmt(col, suffix='%'):
            val = row.get(col, None)
            if pd.isna(val) or val is None:
                return 'N/A'
            return f"{val:.1f}{suffix}"

        summary = (
            f"{district} district, {state}. "
            f"Child nutrition: stunting {fmt('stunting_pct')}, wasting {fmt('wasting_pct')}, "
            f"underweight {fmt('underweight_pct')}, anaemia in children {fmt('anaemia_children_pct')}. "
            f"Maternal health: institutional delivery {fmt('institutional_delivery_pct')}, "
            f"ANC 4+ visits {fmt('anc_4plus_visits_pct')}, C-section rate {fmt('csection_pct')}. "
            f"Anaemia in women {fmt('anaemia_all_women_pct')}. "
            f"Full vaccination coverage {fmt('fully_vaccinated_recall_pct')}. "
            f"Improved sanitation {fmt('improved_sanitation_pct')}. "
            f"Women literacy {fmt('women_literacy_pct')}. "
            f"Child marriage {fmt('child_marriage_pct')}. "
            f"Hypertension (women, mild) {fmt('women_hypertension_mild_pct')}. "
            f"High blood sugar women {fmt('women_high_blood_sugar_pct')}. "
            f"Clean cooking fuel {fmt('clean_cooking_fuel_pct')}. "
            f"Health insurance coverage {fmt('health_insurance_pct')}."
        )

        metadata = {
            "district_id": int(row.get('district_id', 0)),
            "district": district,
            "state": state,
            "stunting_pct": float(row.get('stunting_pct', float('nan'))) if not pd.isna(row.get('stunting_pct', float('nan'))) else None,
            "anaemia_children_pct": float(row.get('anaemia_children_pct', float('nan'))) if not pd.isna(row.get('anaemia_children_pct', float('nan'))) else None,
            "institutional_delivery_pct": float(row.get('institutional_delivery_pct', float('nan'))) if not pd.isna(row.get('institutional_delivery_pct', float('nan'))) else None,
            "fully_vaccinated_recall_pct": float(row.get('fully_vaccinated_recall_pct', float('nan'))) if not pd.isna(row.get('fully_vaccinated_recall_pct', float('nan'))) else None,
            "child_health_score": float(row.get('child_health_score', float('nan'))) if not pd.isna(row.get('child_health_score', float('nan'))) else None,
        }

        summaries.append({
            "id": f"district_{int(row.get('district_id', 0))}",
            "text": summary,
            "metadata": metadata
        })

    return summaries


def run_pipeline():
    print("=" * 60)
    print("BharatHealth Analyst — Data Pipeline")
    print("=" * 60)

    # Load and clean
    df = load_and_clean_nfhs5()

    # Add derived columns
    df = add_derived_columns(df)

    # Save Parquet
    df.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"[OK] Saved Parquet: {OUTPUT_PARQUET}")

    # Save CSV
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    print(f"[OK] Saved CSV: {OUTPUT_CSV}")

    # Generate schema
    schema = generate_schema_json(df)
    with open(OUTPUT_SCHEMA, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved schema: {OUTPUT_SCHEMA} ({len(schema)} columns)")

    # Generate district summaries
    summaries = generate_district_summaries(df)
    with open(OUTPUT_SUMMARIES, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved summaries: {OUTPUT_SUMMARIES} ({len(summaries)} districts)")

    # Print quick stats
    print("\n--- Dataset Statistics ---")
    print(f"Districts: {len(df)}")
    print(f"States/UTs: {df['state'].nunique()}")
    print(f"Columns: {len(df.columns)}")
    if 'stunting_pct' in df.columns:
        print(f"Stunting range: {df['stunting_pct'].min():.1f}% - {df['stunting_pct'].max():.1f}% (national avg: {df['stunting_pct'].mean():.1f}%)")
    if 'anaemia_all_women_pct' in df.columns:
        print(f"Anaemia (women) range: {df['anaemia_all_women_pct'].min():.1f}% - {df['anaemia_all_women_pct'].max():.1f}%")
    if 'institutional_delivery_pct' in df.columns:
        print(f"Institutional delivery range: {df['institutional_delivery_pct'].min():.1f}% - {df['institutional_delivery_pct'].max():.1f}%")

    print("\n[DONE] Pipeline complete.")
    return df, schema, summaries


if __name__ == '__main__':
    run_pipeline()
