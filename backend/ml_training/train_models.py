"""
Training and evaluation pipeline for ASHA Voice Random Forest ML Models.
Builds three separate, reproducible Random Forest classifiers:
  1. Pregnancy Risk Model
  2. Newborn Risk Model
  3. Immunization Risk Model

Key requirements implemented:
  - Dataset-defined Danger_Flag used as binary target (1 = clinical concern, 0 = standard/low risk).
  - Supervised training filter: exclude invalid/contradictory records and missing target rows.
  - Leakage prevention: exclude identifiers, governance, labels, and targets.
  - Free-text descriptions excluded in v1 until clinically reviewed.
  - Structured vaccine lists parsed into count, deficit, deferred, overdue, and antigen indicator features.
  - Unknown and missing categorical values explicitly preserved as 'Unknown' rather than 'No'.
  - Numerical features imputed with median + missingness indicator flags.
  - GroupShuffleSplit grouped by Beneficiary_ID (80/20 train/test split) ensuring 0 beneficiary overlap.
  - Test set kept completely untouched until final evaluation.
  - Full preprocessing + model pipelines saved together using Joblib.
  - Evaluation reports generated with Accuracy, Precision, Recall, Specificity, F1-score, Confusion Matrix,
    and False Negative counts.
"""

import os
import json
import logging
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Constants
RANDOM_STATE = 42
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.dirname(BASE_DIR)
MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
REPORTS_DIR = os.path.join(BASE_DIR, "ml_training", "reports")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

ANTIGENS = ["BCG", "OPV", "HepB", "Pentavalent", "Rotavirus", "fIPV", "PCV", "MR", "JE", "Vitamin-A", "DPT"]


def parse_vaccine_features(df: pd.DataFrame) -> pd.DataFrame:
    """Parses structured vaccine lists into quantitative deficit and antigen indicators."""
    df = df.copy()
    due_raw = df["Vaccines_Due_Today"].fillna("").astype(str)
    given_raw = df["Vaccines_Given_Today"].fillna("").astype(str)

    def split_vax(s: str):
        if not s or s.lower() in ("none", "nan", "", "none (deferred due to acute illness)"):
            return []
        return [v.strip() for v in s.split(",") if v.strip()]

    due_lists = due_raw.apply(split_vax)
    given_lists = given_raw.apply(split_vax)

    df["count_vaccines_due"] = due_lists.apply(len).astype(float)
    df["count_vaccines_given"] = given_lists.apply(len).astype(float)

    def calc_deficit(row):
        due = set(row["due"])
        given = set(row["given"])
        if "deferred" in str(row["given_str"]).lower():
            return float(len(due))
        clean_due = {d.replace("(Overdue)", "").strip() for d in due}
        clean_given = {g.strip() for g in given}
        return float(len(clean_due - clean_given))

    temp_df = pd.DataFrame({"due": due_lists, "given": given_lists, "given_str": given_raw})
    df["dose_deficit_count"] = temp_df.apply(calc_deficit, axis=1)
    df["vaccines_deferred"] = given_raw.str.contains("deferred", case=False, na=False).astype(float)
    df["has_overdue_vaccine"] = due_raw.str.contains("overdue", case=False, na=False).astype(float)

    for antigen in ANTIGENS:
        clean_name = antigen.replace("-", "_").lower()
        df[f"due_{clean_name}"] = due_raw.str.contains(antigen, case=False, na=False).astype(float)
        df[f"given_{clean_name}"] = given_raw.str.contains(antigen, case=False, na=False).astype(float)

    return df


def build_and_train_model(
    dataset_name: str,
    file_path: str,
    sheet_name: str,
    num_features: list,
    cat_features: list,
    exclude_features: list,
    is_immunization: bool = False,
):
    """Builds, group-splits, trains, evaluates, and serializes a Random Forest pipeline."""
    logger.info(f"--- Training {dataset_name} Model ---")
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    # 1. Supervised filter: Exclude invalid/contradictory and missing Danger_Flag
    valid_mask = df["Danger_Flag"].notna() & ~df["Information_Completeness"].isin(["Invalid", "Contradictory"])
    df_clean = df[valid_mask].copy()
    logger.info(f"Filtered {len(df_clean)} valid supervised rows from {len(df)} total rows.")

    # 2. Vaccine parsing if immunization
    if is_immunization:
        df_clean = parse_vaccine_features(df_clean)

    # 3. Target and Group
    y = df_clean["Danger_Flag"].astype(int).values
    groups = df_clean["Beneficiary_ID"].values
    X = df_clean[num_features + cat_features].copy()

    # Ensure categorical columns are strings with explicit Unknown for missing
    for c in cat_features:
        X[c] = X[c].fillna("Unknown").astype(str)

    # 4. Group-based Train/Test Split (80/20)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(X, y, groups))

    X_train, X_test = X.iloc[train_idx].copy(), X.iloc[test_idx].copy()
    y_train, y_test = y[train_idx], y[test_idx]

    # Verify zero group leakage
    train_groups = set(groups[train_idx])
    test_groups = set(groups[test_idx])
    overlap = train_groups.intersection(test_groups)
    assert len(overlap) == 0, f"Data leakage detected! {len(overlap)} overlapping groups."
    logger.info(f"Split verified: Train={len(X_train)} (from {len(train_groups)} beneficiaries), Test={len(X_test)} (from {len(test_groups)} beneficiaries), Overlap=0.")

    # 5. Build Pipeline: numerical imputation (with missingness indicator) + categorical one-hot
    num_transformer = SimpleImputer(strategy="median", add_indicator=True)
    cat_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_transformer, num_features),
            ("cat", cat_transformer, cat_features),
        ],
        remainder="drop",
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", clf),
        ]
    )

    # 6. Fit Pipeline ONLY on Train Split
    pipeline.fit(X_train, y_train)

    # 7. Evaluate on untouched Test Split
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)
    # cm: [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = cm.ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    report_str = classification_report(y_test, y_pred, target_names=["Standard/Low Risk (0)", "Clinical Concern (1)"])

    metrics = {
        "dataset": dataset_name,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_beneficiaries": len(train_groups),
        "test_beneficiaries": len(test_groups),
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall_sensitivity": round(float(rec), 4),
        "specificity": round(float(spec), 4),
        "f1_score": round(float(f1), 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "false_negative_count": int(fn),
        "false_positive_count": int(fp),
        "classification_report": report_str,
    }

    logger.info(f"{dataset_name} Test Results -> Acc: {acc:.4f}, Prec: {prec:.4f}, Rec: {rec:.4f}, Spec: {spec:.4f}, F1: {f1:.4f}, FN: {fn}")

    # 8. Extract Feature Importances
    fitted_preprocessor = pipeline.named_steps["preprocessor"]
    fitted_clf = pipeline.named_steps["classifier"]

    # Get feature names from transformers
    num_cols_out = num_features.copy()
    # Check missing indicator names added
    if hasattr(fitted_preprocessor.named_transformers_["num"], "indicator_") and fitted_preprocessor.named_transformers_["num"].indicator_ is not None:
        ind_features = [f"{num_features[i]}_is_missing" for i in fitted_preprocessor.named_transformers_["num"].indicator_.features_]
        num_cols_out.extend(ind_features)

    cat_cols_out = list(fitted_preprocessor.named_transformers_["cat"].named_steps["onehot"].get_feature_names_out(cat_features))
    all_feature_names = num_cols_out + cat_cols_out

    importances = fitted_clf.feature_importances_
    feat_imp = sorted(
        [{"feature": name, "importance": round(float(imp), 4)} for name, imp in zip(all_feature_names, importances)],
        key=lambda x: x["importance"],
        reverse=True,
    )
    metrics["top_10_features"] = feat_imp[:10]

    # 9. Save Artifacts
    model_filename = f"{dataset_name.lower()}_rf_model.joblib"
    model_path = os.path.join(MODELS_DIR, model_filename)
    joblib.dump(pipeline, model_path)
    logger.info(f"Model saved to: {model_path}")

    report_filename = f"{dataset_name.lower()}_evaluation_report.json"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    with open(report_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return {
        "pipeline": pipeline,
        "metrics": metrics,
        "num_features": num_features,
        "cat_features": cat_features,
        "model_path": model_path,
        "report_path": report_path,
        "X_test": X_test,
        "y_test": y_test,
    }


def train_all_models():
    """Runs training for all three models and produces comprehensive evaluation summary."""
    results = {}

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Pregnancy Risk Model
    # ─────────────────────────────────────────────────────────────────────────
    preg_num = [
        "Gestational_Age_Weeks",
        "Pre_Pregnancy_BMI",
        "Current_Weight_kg",
        "Systolic_BP_mmHg",
        "Diastolic_BP_mmHg",
        "Haemoglobin_g_dL",
        "Blood_Sugar_mg_dL",
        "BP_Reading_Interval_Min",
        "Glucose_Load_Grams",
        "Time_After_Glucose_Load_Hr",
    ]
    preg_cat = [
        "Vaginal_Bleeding",
        "Severe_Headache_or_Blurred_Vision",
        "Fetal_Movement",
        "IFA_Calcium_Consumption",
        "BP_Repeat_Status",
        "Blood_Sugar_Test_Context",
        "Blood_Sugar_Sample_Type",
        "Weight_Context_Status",
    ]
    results["pregnancy"] = build_and_train_model(
        dataset_name="pregnancy",
        file_path=os.path.join(DATA_DIR, "Pregnancy_Beneficiary_Dataset.xlsx"),
        sheet_name="Pregnancy_Dataset",
        num_features=preg_num,
        cat_features=preg_cat,
        exclude_features=[],
        is_immunization=False,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Newborn Risk Model
    # ─────────────────────────────────────────────────────────────────────────
    newborn_num = [
        "Age_Days",
        "Birth_Weight_kg",
        "Current_Weight_kg",
        "Body_Temperature_C",
        "Respiratory_Rate_bpm",
    ]
    newborn_cat = [
        "Breastfeeding_Status",
        "Difficulty_in_Feeding",
        "Difficulty_in_Breathing",
        "Yellowing_of_Skin_or_Eyes",
        "Umbilical_Cord_Condition",
        "Temp_Measurement_Method",
    ]
    results["newborn"] = build_and_train_model(
        dataset_name="newborn",
        file_path=os.path.join(DATA_DIR, "Newborn_Beneficiary_Dataset.xlsx"),
        sheet_name="Newborn_Dataset",
        num_features=newborn_num,
        cat_features=newborn_cat,
        exclude_features=["Umbilical_Cord_Description"],
        is_immunization=False,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Immunization Risk Model
    # ─────────────────────────────────────────────────────────────────────────
    imm_num = [
        "Age_Months",
        "Current_Weight_kg",
        "Current_Height_Length_cm",
        "WAZ_Score",
        "HAZ_Score",
        "WHZ_Score",
        "count_vaccines_due",
        "count_vaccines_given",
        "dose_deficit_count",
        "vaccines_deferred",
        "has_overdue_vaccine",
    ]
    for antigen in ANTIGENS:
        clean = antigen.replace("-", "_").lower()
        imm_num.extend([f"due_{clean}", f"given_{clean}"])

    imm_cat = [
        "Gender",
        "General_Health_Condition",
        "Missed_Vaccination_Doses",
        "Previous_AEFI",
        "Growth_Reference_Indicator",
    ]
    results["immunization"] = build_and_train_model(
        dataset_name="immunization",
        file_path=os.path.join(DATA_DIR, "Immunization_Beneficiary_Dataset.xlsx"),
        sheet_name="Immunization_Dataset",
        num_features=imm_num,
        cat_features=imm_cat,
        exclude_features=["Health_Condition_Description", "Previous_AEFI_Description"],
        is_immunization=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Master Metadata Serialization
    # ─────────────────────────────────────────────────────────────────────────
    master_meta = {
        "project": "ASHA Voice Machine Learning Module",
        "algorithm": "RandomForestClassifier",
        "random_state": RANDOM_STATE,
        "clinical_safety_notice": (
            "EXPERIMENTAL ADVISORY ONLY. These models were trained on synthetic, clinically unvalidated datasets. "
            "Danger_Flag = 1 indicates general clinical/growth/schedule concern, not strictly emergency danger signs. "
            "The model output is NOT a medical diagnosis and MUST NEVER override or downgrade deterministic clinical danger alerts."
        ),
        "models": {
            k: {
                "dataset": v["metrics"]["dataset"],
                "model_artifact": os.path.basename(v["model_path"]),
                "num_features": v["num_features"],
                "cat_features": v["cat_features"],
                "metrics": {
                    "accuracy": v["metrics"]["accuracy"],
                    "precision": v["metrics"]["precision"],
                    "recall_sensitivity": v["metrics"]["recall_sensitivity"],
                    "specificity": v["metrics"]["specificity"],
                    "f1_score": v["metrics"]["f1_score"],
                    "false_negatives": v["metrics"]["false_negative_count"],
                    "confusion_matrix": v["metrics"]["confusion_matrix"],
                },
                "top_5_features": v["metrics"]["top_10_features"][:5],
            }
            for k, v in results.items()
        },
    }

    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(master_meta, f, indent=2)
    logger.info(f"Master metadata saved to: {meta_path}")

    return results


if __name__ == "__main__":
    train_all_models()
