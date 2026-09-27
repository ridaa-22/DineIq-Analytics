import pandas as pd
from config import REPORTS_DIR

df_spark = pd.read_csv(f"{REPORTS_DIR}/spark_predictions.csv")
df_python = pd.read_csv(f"{REPORTS_DIR}/python_predictions.csv")

df_spark["Order_Date"] = pd.to_datetime(df_spark["Order_Date"])
df_python["Order_Date"] = pd.to_datetime(df_python["Order_Date"])

comparison = df_python.merge(
    df_spark[["Order_Date", "Spark_Prediction"]],
    on="Order_Date", how="inner"
)

comparison = comparison.rename(columns={
    "Quantity": "Actual",
    "Python_Prediction": "Python_Prediction"
})

comparison["Numerical_Difference"] = abs(comparison["Spark_Prediction"] - comparison["Python_Prediction"])
comparison["Match_Status"] = comparison["Numerical_Difference"].apply(
    lambda x: "Close Match" if x < comparison["Numerical_Difference"].median() else "Divergent"
)

agreement_pct = (comparison["Match_Status"] == "Close Match").mean() * 100

comparison[["Order_Date", "Actual", "Spark_Prediction", "Python_Prediction", "Numerical_Difference", "Match_Status"]].to_csv(
    f"{REPORTS_DIR}/dual_pipeline_comparison.csv", index=False
)

summary = {
    "total_compared_records": len(comparison),
    "overall_agreement_percentage": round(agreement_pct, 2),
    "avg_numerical_difference": round(comparison["Numerical_Difference"].mean(), 2),
    "spark_avg_mae_vs_actual": round(abs(comparison["Actual"] - comparison["Spark_Prediction"]).mean(), 2),
    "python_avg_mae_vs_actual": round(abs(comparison["Actual"] - comparison["Python_Prediction"]).mean(), 2)
}

import json
with open(f"{REPORTS_DIR}/dual_pipeline_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("Dual-Pipeline Comparison Complete!")
print(summary)