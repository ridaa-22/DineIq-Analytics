from fastapi import FastAPI
import pandas as pd

app = FastAPI()

from fastapi import FastAPI
import pandas as pd
import glob
import os

app = FastAPI()


@app.get("/api/reports/{filename}")
def get_report(filename: str):

    file_path = f"../Reports/{filename}.csv"

    df = pd.read_csv(file_path)

    return df.to_dict(orient="records")