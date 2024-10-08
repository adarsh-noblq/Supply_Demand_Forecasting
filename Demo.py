import streamlit as st
import pandas as pd
import webbrowser  # To open URL in a new tab
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.graph_objects as go
import time
import requests
import pyodbc
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

server = 'iallombardia.database.windows.net'  
database = 'IAL_Lombardia_DB'  
username = 'dbuser2'  
password = 'Welcome@12345'  
st.set_page_config(page_title="Supply and Demand Forecasting", page_icon="📈", layout="wide")


st.title('Supply and Demand Forecasting App')



st.sidebar.image("https://cdn1.iconfinder.com/data/icons/market-research-astute-vol-2/512/Quantitative_Research-512.png", use_column_width=True)
#st.sidebar.image("E://Adarsh//AI//Recco_Demo//Recco_Logo.png", use_column_width=True)


sample_csv_path = "E://Adarsh//AI//Recco_Demo//Supply_Demand_Forecasting//Supply_Demand_Forecasting.csv"

use_sample_data = st.checkbox("Use Recco Data")

if use_sample_data:
    with st.spinner('Loading sample data...'):
        time.sleep(2)  
        sample_data = pd.read_csv(sample_csv_path)
        st.success('Sample data loaded successfully!')
    
  
    st.write("Here is a preview of the sample CSV:")
    st.dataframe(sample_data)
    
   
    st.download_button(
        label="Download Sample CSV",
        data=sample_data.to_csv(index=False),
        file_name="sample_forecast_data.csv",
        mime="text/csv"
    )
    
    
    data = sample_data
else:
    
    uploaded_file = st.file_uploader("Upload your CSV file for forecasting", type=["csv"])
    
    if uploaded_file is not None:
        with st.spinner('Loading your data...'):
            time.sleep(2)  # Simulate loading
            data = pd.read_csv(uploaded_file)
        st.success('Your data loaded successfully!')


if 'data' in locals():
    st.markdown("### Data Cleaning and Processing...")

 
    data_cleaned = data.drop(columns=['Unnamed: 11'], errors='ignore')  
    data_cleaned = data_cleaned.dropna(subset=['Date'])
    data_cleaned['Date'] = pd.to_datetime(data_cleaned['Date'], format='%d-%m-%Y')
    data_cleaned.set_index('Date', inplace=True)

    
    st.write("Here is a preview of your data:")
    st.dataframe(data_cleaned.head())

    forecast_periods = st.slider('Select the number of periods to forecast:', min_value=1, max_value=36, value=12)

    # ========== SUPPLY FORECASTING ========== 
    supply_y = data_cleaned['Debit EUR']
    exogenous_features_supply = data_cleaned[['Vendor Quality History', 'Vendor Consistency', 'Processing Efficiency (%)']]

    train_size_supply = int(len(supply_y) * 0.8)
    train_supply_y, test_supply_y = supply_y[:train_size_supply], supply_y[train_size_supply:]
    train_supply_exog, test_supply_exog = exogenous_features_supply[:train_size_supply], exogenous_features_supply[train_size_supply:]

    arimax_supply_model = SARIMAX(train_supply_y, exog=train_supply_exog, order=(5, 1, 0))
    arimax_supply_fitted = arimax_supply_model.fit()

    supply_forecast = arimax_supply_fitted.forecast(steps=forecast_periods, exog=test_supply_exog[:forecast_periods])

    # ========== DEMAND FORECASTING ========== 
    demand_y = data_cleaned['Credit EUR']
    exogenous_features_demand = data_cleaned[['Vendor Quality History', 'Vendor Consistency', 'Processing Efficiency (%)']]

    train_size_demand = int(len(demand_y) * 0.8)
    train_demand_y, test_demand_y = demand_y[:train_size_demand], demand_y[train_size_demand:]
    train_demand_exog, test_demand_exog = exogenous_features_demand[:train_size_demand], exogenous_features_demand[train_size_demand:]

    arimax_demand_model = SARIMAX(train_demand_y, exog=train_demand_exog, order=(5, 1, 0))
    arimax_demand_fitted = arimax_demand_model.fit()

    demand_forecast = arimax_demand_fitted.forecast(steps=forecast_periods, exog=test_demand_exog[:forecast_periods])

    forecast_dates = pd.date_range(start=test_supply_y.index[-1] + pd.Timedelta(days=1), periods=forecast_periods, freq='D')

    forecast_df = pd.DataFrame({
        'Forecast Date': forecast_dates,
        'Supply Forecast ': supply_forecast.values,
        'Demand Forecast ': demand_forecast.values
    })

    st.subheader("Forecasted Values Table")
    st.dataframe(forecast_df)

    st.download_button(
        label="Download Forecast Data",
        data=forecast_df.to_csv(index=False),
        file_name="forecast_values.csv",
        mime="text/csv"
    )
    if st.button('Insert Forecast Data into Database'):
        def connect_to_db():
            connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
            return pyodbc.connect(connection_string)

        def insert_forecast_data(df):
            conn = connect_to_db()
            create_table_query = '''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SupplyDemandForecast' AND xtype='U')
            CREATE TABLE SupplyDemandForecast (
                ForecastDate DATE,
                SupplyForecast FLOAT,
                DemandForecast FLOAT
            );
            '''
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()

            # Insert data into the table
            insert_query = '''
            INSERT INTO ForecastData (ForecastDate, SupplyForecast, DemandForecast)
            VALUES (?, ?, ?);
            '''
            
            with conn.cursor() as cursor:
                for index, row in df.iterrows():
                    cursor.execute(insert_query, row['Forecast Date'], row['Supply Forecast '], row['Demand Forecast '])
                conn.commit()

            conn.close()

        # Simulate loading and inserting data
        with st.spinner('Inserting forecast data into the database...'):
            insert_forecast_data(forecast_df)
            st.success("Data has been successfully inserted into the SQL database.")


    # Add buttons to visualize graphs and open the external URL
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Visualize Forecasting Graphs"):
            with st.spinner('Generating visualizations...'):
                time.sleep(1)

                # Supply Forecasting Plot
                st.subheader('Supply Forecasting')
                supply_fig = go.Figure()

                supply_fig.add_trace(go.Scatter(
                    x=train_supply_y.index, y=train_supply_y,
                    mode='lines+markers', name='Training Data',
                    line=dict(color='lightblue'), marker=dict(symbol='circle')
                ))
                supply_fig.add_trace(go.Scatter(
                    x=test_supply_y.index, y=test_supply_y,
                    mode='lines+markers', name='Actual Supply (Test Data)',
                    line=dict(color='blue'), marker=dict(symbol='square')
                ))
                supply_fig.add_trace(go.Scatter(
                    x=forecast_dates, y=supply_forecast,
                    mode='lines+markers', name='Forecasted Supply',
                    line=dict(color='red', dash='dash'), marker=dict(symbol='x')
                ))
                supply_fig.update_layout(
                    title='Supply Forecasting',
                    xaxis_title='Date',
                    yaxis_title='Debit EUR (Supply)',
                    legend_title='Legend'
                )
                st.plotly_chart(supply_fig)

                # Demand Forecasting Plot
                st.subheader('Demand Forecasting')
                demand_fig = go.Figure()

                demand_fig.add_trace(go.Scatter(
                    x=train_demand_y.index, y=train_demand_y,
                    mode='lines+markers', name='Training Data',
                    line=dict(color='lightgreen'), marker=dict(symbol='circle')
                ))
                demand_fig.add_trace(go.Scatter(
                    x=test_demand_y.index, y=test_demand_y,
                    mode='lines+markers', name='Actual Demand (Test Data)',
                    line=dict(color='green'), marker=dict(symbol='square')
                ))
                demand_fig.add_trace(go.Scatter(
                    x=forecast_dates, y=demand_forecast,
                    mode='lines+markers', name='Forecasted Demand',
                    line=dict(color='red', dash='dash'), marker=dict(symbol='x')
                ))
                demand_fig.update_layout(
                    title='Demand Forecasting',
                    xaxis_title='Date',
                    yaxis_title='Credit EUR (Demand)',
                    legend_title='Legend'
                )
                st.plotly_chart(demand_fig)

    with col2:
        if st.button("Analytics Visualize"):
            with st.spinner('Opening Visualize dashboard....'):
                
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service)

                # Step 1: Navigate to the login page
                driver.get('https://nqbi.noblq.io/login/')

                # Step 2: Fill in the username and password
                username_input = driver.find_element(By.NAME, 'username')  # Adjust selector as necessary
                password_input = driver.find_element(By.NAME, 'password')  # Adjust selector as necessary

                username_input.send_keys('admin')  # Enter username
                password_input.send_keys('admin')  # Enter password

                # Step 3: Submit the login form
                password_input.send_keys(Keys.RETURN)

                # Wait for the login to complete
                time.sleep(3)  # Adjust sleep time based on how long the login takes

                # Step 4: Navigate to the desired dashboard after login
                driver.get('https://nqbi.noblq.io/superset/dashboard/56')

                # Now the dashboard should be opened, bypassing the login page
                st.success("Superset dashboard opened successfully!")
else:
    st.write("Please upload a CSV file to proceed or select to use the sample data.")
