import streamlit as st

def ir35_tax_calculator(day_rate, work_days_per_year=220):
    """Calculate take-home pay for consultants inside IR35."""
    
    # Constants
    annual_income = day_rate * work_days_per_year
    personal_allowance = 12570  # Tax-free allowance (2024/25)
    basic_rate_threshold = 50270
    higher_rate_threshold = 125140
    
    # Tax bands
    basic_rate = 0.2
    higher_rate = 0.4
    additional_rate = 0.45
    
    # National Insurance (NI)
    ni_threshold = 12570
    ni_lower = 0.08  # 8% for earnings above £12,570
    ni_upper = 0.02  # 2% for earnings above £50,270
    
    # Employer NI (deducted at source)
    employer_ni_rate = 0.133
    employer_ni = (annual_income - ni_threshold) * employer_ni_rate if annual_income > ni_threshold else 0
    annual_income -= employer_ni  # Deduct Employer NI before tax
    
    # Income Tax Calculation
    if annual_income <= personal_allowance:
        income_tax = 0
    elif annual_income <= basic_rate_threshold:
        income_tax = (annual_income - personal_allowance) * basic_rate
    elif annual_income <= higher_rate_threshold:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((annual_income - basic_rate_threshold) * higher_rate)
    else:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((higher_rate_threshold - basic_rate_threshold) * higher_rate) + ((annual_income - higher_rate_threshold) * additional_rate)
    
    # National Insurance (NI) Calculation
    if annual_income <= ni_threshold:
        ni_contribution = 0
    elif annual_income <= basic_rate_threshold:
        ni_contribution = (annual_income - ni_threshold) * ni_lower
    else:
        ni_contribution = ((basic_rate_threshold - ni_threshold) * ni_lower) + ((annual_income - basic_rate_threshold) * ni_upper)
    
    # Final Take-Home Pay Calculation
    take_home_pay = annual_income - (income_tax + ni_contribution)
    
    return {
        "Gross Income": annual_income + employer_ni,
        "Employer NI Deducted": employer_ni,
        "Income Tax": income_tax,
        "Employee NI": ni_contribution,
        "Net Take-Home Pay": take_home_pay
    }

# Streamlit Web App
st.title("IR35 Tax Calculator")

# User Input
day_rate = st.number_input("Enter your daily rate (£):", min_value=0, value=500)
work_days_per_year = st.number_input("Enter workdays per year:", min_value=1, max_value=365, value=220)

if st.button("Calculate"):
    result = ir35_tax_calculator(day_rate, work_days_per_year)
    
    st.subheader("Results")
    st.write(f"**Gross Income:** £{result['Gross Income']:,.2f}")
    st.write(f"**Employer NI Deducted:** £{result['Employer NI Deducted']:,.2f}")
    st.write(f"**Income Tax:** £{result['Income Tax']:,.2f}")
    st.write(f"**Employee NI:** £{result['Employee NI']:,.2f}")
    st.write(f"**Net Take-Home Pay:** £{result['Net Take-Home Pay']:,.2f}")