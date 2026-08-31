import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import xgboost as xgb

# Define feature mappings
Fever_Severity_map = {'Normal': 0, 'Mild Fever': 1, 'High Fever': 2}
Gender_map = {'Female': 0, 'Male': 1}
No_Yes_map = {'No': 0, 'Yes': 1}
Physical_Activity_map = {'Sedentary': 0, 'Moderate': 1, 'Active': 2}
Diet_Type_map = {'Non-Vegetarian': 0, 'Vegetarian': 1, 'Vegan': 2}
Blood_Pressure_map = {'Low': -1, 'Normal': 0, 'High': 1}
Previous_Medication_map = {'Paracetamol': -1, 'Ibuprofen': 1}
Medication_map = {'Paracetamol': 0, 'Ibuprofen': 1}
Inverse_Medication_map = {0: 'Paracetamol', 1: 'Ibuprofen'}

FEATURES = [
    'Temperature',
    'Fever_Severity',
    'Alcohol_Consumption',
    'Fatigue',
    'Physical_Activity',
    'Humidity',
    'Headache',
    'Diet_Type',
    'Gender',
    'AQI',
    'Heart_Rate',
    'Allergies',
    'Smoking_History',
    'Blood_Pressure',
    'Chronic_Conditions',
    'Body_Ache',
    'Age',
    'BMI',
    'Previous_Medication'
]

def load_data(filepath=None):
    if filepath is None:
        if os.path.exists("relivio.csv"):
            filepath = "relivio.csv"
        elif os.path.exists("enhanced_fever_medicine_recommendation.csv"):
            filepath = "enhanced_fever_medicine_recommendation.csv"
        else:
            raise FileNotFoundError("Dataset CSV not found in workspace.")
    return pd.read_csv(filepath)

def preprocess_dataframe(df_input):
    df = df_input.copy()
    if 'Fever_Severity' in df.columns:
        df['Fever_Severity'] = df['Fever_Severity'].map(Fever_Severity_map)
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map(Gender_map)
    for col in ['Headache', 'Body_Ache', 'Fatigue', 'Chronic_Conditions', 'Allergies', 'Smoking_History', 'Alcohol_Consumption']:
        if col in df.columns:
            df[col] = df[col].map(No_Yes_map)
    if 'Physical_Activity' in df.columns:
        df['Physical_Activity'] = df['Physical_Activity'].map(Physical_Activity_map)
    if 'Diet_Type' in df.columns:
        df['Diet_Type'] = df['Diet_Type'].map(Diet_Type_map)
    if 'Blood_Pressure' in df.columns:
        df['Blood_Pressure'] = df['Blood_Pressure'].map(Blood_Pressure_map)
    if 'Previous_Medication' in df.columns:
        df['Previous_Medication'] = df['Previous_Medication'].map(Previous_Medication_map).fillna(0)
    if 'Recommended_Medication' in df.columns:
        df['Recommended_Medication'] = df['Recommended_Medication'].map(Medication_map).astype(int)
    return df

def train_and_save_model(data_path=None, model_out="model.json", pkl_out="model.pkl", meta_out="model_meta.json"):
    df_raw = load_data(data_path)
    df_clean = preprocess_dataframe(df_raw)

    X = df_clean[FEATURES].copy()
    y = df_clean['Recommended_Medication'].copy()

    # Train / Validation Split (75% train, 25% test)
    train_X, val_X, train_y, val_y = train_test_split(X, y, test_size=0.25, random_state=1, stratify=y)

    dtrain = xgb.DMatrix(train_X, label=train_y, feature_names=FEATURES)
    dval = xgb.DMatrix(val_X, label=val_y, feature_names=FEATURES)

    best_params = {
        'learning_rate': 0.025,
        'max_depth': 5,
        'random_state': 42,
        'objective': 'binary:logistic',
        'eval_metric': ['logloss', 'error']
    }

    evals_result = {}
    xgb_model = xgb.train(
        params=best_params,
        dtrain=dtrain,
        num_boost_round=1500,
        evals=[(dtrain, "train"), (dval, "valid")],
        early_stopping_rounds=50,
        evals_result=evals_result,
        verbose_eval=False
    )

    # Validation predictions
    val_probs = xgb_model.predict(dval, iteration_range=(0, xgb_model.best_iteration))
    val_preds = (val_probs > 0.5).astype(int)

    # Metrics
    acc = float(accuracy_score(val_y, val_preds))
    prec = float(precision_score(val_y, val_preds, zero_division=0))
    rec = float(recall_score(val_y, val_preds, zero_division=0))
    f1 = float(f1_score(val_y, val_preds, zero_division=0))
    roc_auc = float(roc_auc_score(val_y, val_probs))
    cm = confusion_matrix(val_y, val_preds).tolist()

    # Feature importances
    importance_scores = xgb_model.get_score(importance_type='gain')
    total_gain = sum(importance_scores.values()) if importance_scores else 1.0
    normalized_importance = {k: round(v / total_gain * 100, 2) for k, v in sorted(importance_scores.items(), key=lambda item: item[1], reverse=True)}

    # Save model files
    xgb_model.save_model(model_out)
    with open(pkl_out, 'wb') as f:
        pickle.dump(xgb_model, f)

    # Calculate column stats for ranges
    ranges = {}
    for col in ['Temperature', 'Age', 'BMI', 'Humidity', 'AQI', 'Heart_Rate']:
        ranges[col] = {
            'min': float(df_raw[col].min()),
            'max': float(df_raw[col].max()),
            'mean': round(float(df_raw[col].mean()), 2),
            'median': round(float(df_raw[col].median()), 2)
        }

    meta = {
        'features': FEATURES,
        'metrics': {
            'accuracy': round(acc * 100, 2),
            'precision': round(prec * 100, 2),
            'recall': round(rec * 100, 2),
            'f1_score': round(f1 * 100, 2),
            'roc_auc': round(roc_auc * 100, 2),
            'confusion_matrix': cm,
            'best_iteration': int(xgb_model.best_iteration)
        },
        'feature_importance': normalized_importance,
        'ranges': ranges,
        'mappings': {
            'Fever_Severity': Fever_Severity_map,
            'Gender': Gender_map,
            'No_Yes': No_Yes_map,
            'Physical_Activity': Physical_Activity_map,
            'Diet_Type': Diet_Type_map,
            'Blood_Pressure': Blood_Pressure_map,
            'Previous_Medication': Previous_Medication_map,
            'Medication_Target': Medication_map
        }
    }

    with open(meta_out, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"Model successfully trained and saved to {model_out} and {pkl_out}")
    print(f"Validation Accuracy: {acc * 100:.2f}% | ROC-AUC: {roc_auc * 100:.2f}% | F1: {f1 * 100:.2f}%")
    return xgb_model, meta

def transform_single_input(input_dict):
    """
    Transforms a dictionary of raw input features (numeric and string categories)
    into a formatted 1-row DataFrame ready for DMatrix creation.
    """
    row = {}
    
    # 1. Temperature (float)
    row['Temperature'] = float(input_dict.get('Temperature', 37.0))
    
    # 2. Fever_Severity
    fs = input_dict.get('Fever_Severity', 'Normal')
    row['Fever_Severity'] = Fever_Severity_map.get(fs, 0)
    
    # 3. Alcohol_Consumption
    row['Alcohol_Consumption'] = No_Yes_map.get(input_dict.get('Alcohol_Consumption', 'No'), 0)
    
    # 4. Fatigue
    row['Fatigue'] = No_Yes_map.get(input_dict.get('Fatigue', 'No'), 0)
    
    # 5. Physical_Activity
    pa = input_dict.get('Physical_Activity', 'Moderate')
    row['Physical_Activity'] = Physical_Activity_map.get(pa, 1)
    
    # 6. Humidity
    row['Humidity'] = float(input_dict.get('Humidity', 50.0))
    
    # 7. Headache
    row['Headache'] = No_Yes_map.get(input_dict.get('Headache', 'No'), 0)
    
    # 8. Diet_Type
    dt = input_dict.get('Diet_Type', 'Vegetarian')
    row['Diet_Type'] = Diet_Type_map.get(dt, 1)
    
    # 9. Gender
    gen = input_dict.get('Gender', 'Female')
    row['Gender'] = Gender_map.get(gen, 0)
    
    # 10. AQI
    row['AQI'] = float(input_dict.get('AQI', 100.0))
    
    # 11. Heart_Rate
    row['Heart_Rate'] = float(input_dict.get('Heart_Rate', 75.0))
    
    # 12. Allergies
    row['Allergies'] = No_Yes_map.get(input_dict.get('Allergies', 'No'), 0)
    
    # 13. Smoking_History
    row['Smoking_History'] = No_Yes_map.get(input_dict.get('Smoking_History', 'No'), 0)
    
    # 14. Blood_Pressure
    bp = input_dict.get('Blood_Pressure', 'Normal')
    row['Blood_Pressure'] = Blood_Pressure_map.get(bp, 0)
    
    # 15. Chronic_Conditions
    row['Chronic_Conditions'] = No_Yes_map.get(input_dict.get('Chronic_Conditions', 'No'), 0)
    
    # 16. Body_Ache
    row['Body_Ache'] = No_Yes_map.get(input_dict.get('Body_Ache', 'No'), 0)
    
    # 17. Age
    row['Age'] = float(input_dict.get('Age', 30))
    
    # 18. BMI
    row['BMI'] = float(input_dict.get('BMI', 22.5))
    
    # 19. Previous_Medication
    pm = input_dict.get('Previous_Medication', 'None')
    row['Previous_Medication'] = Previous_Medication_map.get(pm, 0)

    # Assemble DataFrame in exact feature order
    df_single = pd.DataFrame([row])[FEATURES]
    return df_single

def predict_single(model, input_dict):
    df_features = transform_single_input(input_dict)
    dmat = xgb.DMatrix(df_features, feature_names=FEATURES)
    prob_ibuprofen = float(model.predict(dmat)[0])
    prob_paracetamol = 1.0 - prob_ibuprofen
    
    predicted_class = 1 if prob_ibuprofen >= 0.5 else 0
    recommended_med = Inverse_Medication_map[predicted_class]
    confidence = prob_ibuprofen if predicted_class == 1 else prob_paracetamol

    return {
        'prediction': recommended_med,
        'confidence_percentage': round(confidence * 100, 2),
        'probabilities': {
            'Paracetamol': round(prob_paracetamol * 100, 2),
            'Ibuprofen': round(prob_ibuprofen * 100, 2)
        },
        'raw_score': prob_ibuprofen
    }

if __name__ == '__main__':
    train_and_save_model()
