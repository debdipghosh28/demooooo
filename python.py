import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import os


data_file = pd.read_csv("relivio.csv")
data_file.head(5)

print("\nMissing values and data types in each column:")
print(pd.DataFrame({
    'Missing Values': data_file.isnull().sum(),
    'Data Type': data_file.dtypes
}))

Fever_Severity_map = {'Normal':0, 'Mild Fever':1, 'High Fever': 2}
Gender_map = {'Female':0, 'Male':1}
No_Yes_map = {'No':0, 'Yes':1}
Physical_Activity_map = {'Sedentary':0, 'Moderate':1, 'Active':2}
Diet_Type_map = {'Non-Vegetarian':0, 'Vegetarian':1, 'Vegan':2}
Blood_Pressure_map = {'Low':-1, 'Normal':0, 'High':1}
Previous_Medication_map = {'Paracetamol':-1, 'Ibuprofen':1}
Medication_map = {'Paracetamol':0, 'Ibuprofen':1}

def preprocessing(df):
    df['Fever_Severity'] = df['Fever_Severity'].map(Fever_Severity_map)
    df['Gender'] = df['Gender'].map(Gender_map)
    df['Headache'] = df['Headache'].map(No_Yes_map)
    df['Body_Ache'] = df['Body_Ache'].map(No_Yes_map)
    df['Fatigue'] = df['Fatigue'].map(No_Yes_map)
    df['Chronic_Conditions'] = df['Chronic_Conditions'].map(No_Yes_map)
    df['Allergies'] = df['Allergies'].map(No_Yes_map)
    df['Smoking_History'] = df['Smoking_History'].map(No_Yes_map)
    df['Alcohol_Consumption'] = df['Alcohol_Consumption'].map(No_Yes_map)
    df['Physical_Activity'] = df['Physical_Activity'].map(Physical_Activity_map)
    df['Diet_Type'] = df['Diet_Type'].map(Diet_Type_map)
    df['Blood_Pressure'] = df['Blood_Pressure'].map(Blood_Pressure_map)
    df['Previous_Medication'] = df['Previous_Medication'].map(Previous_Medication_map).fillna(0)
    df['Recommended_Medication'] = df['Recommended_Medication'].map(Medication_map).astype(int)

    return df

data = preprocessing(data_file.copy())
data.head()

subplot_size = (4, 3)
n_cols = 3
n_rows = 7
fig, axes = plt.subplots(n_rows, n_cols, figsize=(subplot_size[0] * n_cols, subplot_size[1] * n_rows))
axes = axes.flatten()

index=0
for col in ['Recommended_Medication', 'Fever_Severity', 'Gender', 'Headache', 'Body_Ache', 'Fatigue', 'Chronic_Conditions', 'Allergies', 'Smoking_History', 'Alcohol_Consumption', 'Physical_Activity', 'Diet_Type', 'Blood_Pressure', 'Previous_Medication']:
    sns.countplot(x = data_file[col], ax=axes[index])
    index+=1

for col in ['Temperature', 'Age', 'BMI', 'Humidity', 'AQI', 'Heart_Rate']:
    sns.histplot(data[col], kde=True, bins=20, ax=axes[index])
    index+=1

plt.tight_layout()
plt.show()

plt.figure(figsize=(16, 6))
korelasi = data.copy().corr()
sns.heatmap(korelasi, cmap="BrBG", annot=True)


features = [
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

X = data[features].copy()
y = data.Recommended_Medication




best_params = {
    'learning_rate': 0.025,
    'max_depth': 5,
    'random_state': 42,
    'objective': 'binary:logistic',
}

# Split into validation and training data
train_X, val_X, train_y, val_y = train_test_split(X, y,test_size=0.25, random_state=1)

# Define the XGBoost model
# Start with some reasonable parameters
dtrain = xgb.DMatrix(train_X, label=train_y, enable_categorical=True)
dval = xgb.DMatrix(val_X, label=val_y, enable_categorical=True)

evals_result = {}
xgb_model = xgb.train(
    params=best_params,
    dtrain=dtrain,
    num_boost_round=1500,
    evals=[(dtrain, "train"), (dval, "valid")],
    early_stopping_rounds=50,
    evals_result=evals_result,
    verbose_eval=0
)


val_predictions = xgb_model.predict(dval, iteration_range=(0, xgb_model.best_iteration))
preds_binary = (val_predictions > 0.5).astype(int)
rmse = np.sqrt(mean_squared_error(val_y, preds_binary))

print("\nValidation RMSE for XGBoost Model: {:,.4f}".format(rmse))
results_df = pd.DataFrame({
    'Actual': val_y,
    'Predicted': preds_binary
})

print("\nSample Predictions:")
results_df.head(10)  # Show first 10 predictions VS Actual