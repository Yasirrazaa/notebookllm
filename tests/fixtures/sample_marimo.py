import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def import_data():
    import pandas as pd
    df = pd.read_csv("data.csv")
    return pd, df


@app.cell
def analyze(df):
    result = df.describe()
    return result,


@app.cell
def display(result):
    return result,