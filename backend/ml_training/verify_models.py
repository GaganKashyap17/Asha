import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from services.ml_prediction_service import ml_prediction_service

def verify():
    print("=" * 70)
    print("  ASHA VOICE - RANDOM FOREST MACHINE LEARNING MODULE VERIFICATION")
    print("=" * 70)

    print("\n[STEP 1] Model Serialization & Performance Metrics:")
    meta = ml_prediction_service.get_metadata()
    for k in ['pregnancy', 'newborn', 'immunization']:
        is_loaded = k in ml_prediction_service._models
        m_meta = meta.get('models', {}).get(k, {})
        acc = m_meta.get('metrics', {}).get('accuracy', 0)
        prec = m_meta.get('metrics', {}).get('precision', 0)
        rec = m_meta.get('metrics', {}).get('recall_sensitivity', 0)
        f1 = m_meta.get('metrics', {}).get('f1_score', 0)
        print(f"  * {k.capitalize():<14}: Loaded={is_loaded} | Accuracy={acc*100:.2f}% | Precision={prec*100:.2f}% | Recall={rec*100:.2f}% | F1={f1:.4f}")

    print("\n[STEP 2] Inference Verification - Pregnancy Model:")
    # High risk case
    res_preg_danger = ml_prediction_service.predict(
        category='pregnancy',
        record={
            'Gestational_Age_Weeks': 28.0,
            'Haemoglobin_g_dL': 6.5,
            'Diastolic_BP_mmHg': 105,
            'Systolic_BP_mmHg': 165,
            'Fetal_Movement': 'Absent',
            'Vaginal_Bleeding': 'Yes'
        },
        existing_danger_alert=True
    )
    print("  A. High-Risk / Emergency Case:")
    print(f"     - Prediction: {res_preg_danger['prediction']} ({res_preg_danger['prediction_label']})")
    print(f"     - Concern Probability: {res_preg_danger['probability_clinical_concern']*100:.1f}%")
    print(f"     - Composite Status: {res_preg_danger['composite_status']}")
    print(f"     - Emergency Override Prevented: {res_preg_danger['clinical_rules_override_prevented']}")
    print(f"     - Clinical Explanations: {res_preg_danger['clinical_explanations']}")
    assert res_preg_danger['prediction'] == 1
    assert res_preg_danger['probability_clinical_concern'] > 0.70
    assert res_preg_danger['clinical_rules_override_prevented'] is True

    # Normal case
    res_preg_normal = ml_prediction_service.predict(
        category='pregnancy',
        record={
            'Gestational_Age_Weeks': 27.0,
            'Pre_Pregnancy_BMI': 25.3,
            'Current_Weight_kg': 57.2,
            'Systolic_BP_mmHg': 115.0,
            'Diastolic_BP_mmHg': 67.0,
            'Haemoglobin_g_dL': 12.6,
            'Blood_Sugar_mg_dL': 117.0,
            'Vaginal_Bleeding': 'No',
            'Severe_Headache_or_Blurred_Vision': 'No',
            'Fetal_Movement': 'Normal',
            'IFA_Calcium_Consumption': 'Regular'
        },
        existing_danger_alert=False
    )
    print("  B. Routine / Standard Case:")
    print(f"     - Prediction: {res_preg_normal['prediction']} ({res_preg_normal['prediction_label']})")
    print(f"     - Concern Probability: {res_preg_normal['probability_clinical_concern']*100:.1f}%")
    print(f"     - Composite Status: {res_preg_normal['composite_status']}")
    assert res_preg_normal['prediction'] == 0
    assert res_preg_normal['probability_clinical_concern'] < 0.50

    print("\n[STEP 3] Inference Verification - Newborn Model:")
    # Danger case
    res_nb_danger = ml_prediction_service.predict(
        category='newborn',
        record={
            'Age_Days': 3,
            'Birth_Weight_kg': 1.8,
            'Current_Weight_kg': 1.75,
            'Body_Temperature_C': 39.2,
            'Respiratory_Rate_bpm': 75.0,
            'Difficulty_in_Breathing': 'Yes',
            'Difficulty_in_Feeding': 'Yes',
            'Yellowing_of_Skin_or_Eyes': 'Deep yellow palms/soles'
        }
    )
    print("  A. High-Risk Neonatal Case:")
    print(f"     - Prediction: {res_nb_danger['prediction']} ({res_nb_danger['prediction_label']})")
    print(f"     - Concern Probability: {res_nb_danger['probability_clinical_concern']*100:.1f}%")
    print(f"     - Clinical Explanations: {res_nb_danger['clinical_explanations']}")
    assert res_nb_danger['prediction'] == 1
    assert res_nb_danger['probability_clinical_concern'] > 0.70

    # Normal case
    res_nb_normal = ml_prediction_service.predict(
        category='newborn',
        record={
            'Age_Days': 7,
            'Birth_Weight_kg': 3.3,
            'Current_Weight_kg': 3.41,
            'Body_Temperature_C': 37.2,
            'Respiratory_Rate_bpm': 47.0,
            'Breastfeeding_Status': 'Exclusive',
            'Difficulty_in_Feeding': 'No',
            'Difficulty_in_Breathing': 'No',
            'Yellowing_of_Skin_or_Eyes': 'No',
            'Umbilical_Cord_Condition': 'Normal'
        }
    )
    print("  B. Routine Neonatal Case:")
    print(f"     - Prediction: {res_nb_normal['prediction']} ({res_nb_normal['prediction_label']})")
    print(f"     - Concern Probability: {res_nb_normal['probability_clinical_concern']*100:.1f}%")
    print(f"     - Composite Status: {res_nb_normal['composite_status']}")
    assert res_nb_normal['prediction'] == 0
    assert res_nb_normal['probability_clinical_concern'] < 0.50

    print("\n[STEP 4] Inference Verification - Immunization Model:")
    # Deficit / Unwell case
    res_imm_danger = ml_prediction_service.predict(
        category='immunization',
        record={
            'Age_Months': 3.5,
            'Current_Weight_kg': 4.2,
            'Current_Height_Length_cm': 55.0,
            'WAZ_Score': -2.8,
            'HAZ_Score': -2.5,
            'Missed_Vaccination_Doses': 'Yes',
            'Vaccines_Due_Today': 'Pentavalent 1, OPV 1, Rotavirus 1',
            'Vaccines_Administered_Today': 'None (deferred due to acute illness)',
            'General_Health_Condition': 'Unwell'
        }
    )
    print("  A. Immunization Deficit / Malnutrition Case:")
    print(f"     - Prediction: {res_imm_danger['prediction']} ({res_imm_danger['prediction_label']})")
    print(f"     - Concern Probability: {res_imm_danger['probability_clinical_concern']*100:.1f}%")
    print(f"     - Clinical Explanations: {res_imm_danger['clinical_explanations']}")
    assert res_imm_danger['prediction'] == 1
    assert res_imm_danger['probability_clinical_concern'] > 0.70

    # Normal on-track case
    res_imm_normal = ml_prediction_service.predict(
        category='immunization',
        record={
            'Age_Months': 2.0,
            'Current_Weight_kg': 5.2,
            'Current_Height_Length_cm': 58.0,
            'WAZ_Score': 0.1,
            'HAZ_Score': 0.2,
            'WHZ_Score': 0.0,
            'Missed_Vaccination_Doses': 'No',
            'Vaccines_Due_Today': 'Pentavalent 1, OPV 1',
            'Vaccines_Administered_Today': 'Pentavalent 1, OPV 1',
            'General_Health_Condition': 'Normal'
        }
    )
    print("  B. Routine Immunization Case:")
    print(f"     - Prediction: {res_imm_normal['prediction']} ({res_imm_normal['prediction_label']})")
    print(f"     - Concern Probability: {res_imm_normal['probability_clinical_concern']*100:.1f}%")
    print(f"     - Composite Status: {res_imm_normal['composite_status']}")
    assert res_imm_normal['prediction'] == 0
    assert res_imm_normal['probability_clinical_concern'] < 0.50

    print("\n[STEP 5] Regression Unit Tests:")
    import subprocess
    cmd = [sys.executable, "-m", "pytest", "tests/test_ml_models.py", "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("  * test_ml_models.py output: " + result.stdout.strip())
    assert result.returncode == 0, f"Pytest failed: {result.stderr}"

    print("\n" + "=" * 70)
    print("  VERIFICATION RESULT: ALL 3 ML MODELS ARE OPERATING ACCURATELY & PROPERLY")
    print("=" * 70)

if __name__ == '__main__':
    verify()
