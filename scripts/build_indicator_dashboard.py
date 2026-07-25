import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR,"data","nse_stocks")
weekly_folder = os.path.join(BASE_DIR,"data","nse_weekly")
monthly_folder = os.path.join(BASE_DIR,"data","nse_monthly")
quarter_folder = os.path.join(BASE_DIR,"data","nse_quarterly")

output_file = os.path.join(BASE_DIR,"data","indicator_dashboard.csv")

results = []

files = os.listdir(daily_folder)

for file in files:

    symbol = file.replace(".csv","")

    try:
        d = pd.read_csv(os.path.join(daily_folder,file))
        w = pd.read_csv(os.path.join(weekly_folder,file))
        m = pd.read_csv(os.path.join(monthly_folder,file))
        q = pd.read_csv(os.path.join(quarter_folder,file))
    except:
        continue

    if len(d)==0 or len(w)==0 or len(m)==0 or len(q)==0:
        continue

    d_last = d.iloc[-1]
    w_last = w.iloc[-1]
    m_last = m.iloc[-1]
    q_last = q.iloc[-1]

    results.append({

        "SYMBOL":symbol,

        "3M_RSI":round(q_last["RSI"],2),
        "3M_STOCHRSI":round(q_last["STOCHRSI"],2),
        "3M_K":round(q_last["K"],2),
        "3M_D":round(q_last["D"],2),

        "M_RSI":round(m_last["RSI"],2),
        "M_STOCHRSI":round(m_last["STOCHRSI"],2),
        "M_K":round(m_last["K"],2),
        "M_D":round(m_last["D"],2),

        "W_RSI":round(w_last["RSI"],2),
        "W_STOCHRSI":round(w_last["STOCHRSI"],2),
        "W_K":round(w_last["K"],2),
        "W_D":round(w_last["D"],2),

        "D_RSI":round(d_last["RSI"],2),
        "D_STOCHRSI":round(d_last["STOCHRSI"],2),
        "D_K":round(d_last["K"],2),
        "D_D":round(d_last["D"],2)

    })


dashboard = pd.DataFrame(results)

dashboard = dashboard.sort_values("SYMBOL")

dashboard.to_csv(output_file,index=False)

print("Dashboard created:",output_file)