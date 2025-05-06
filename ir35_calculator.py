import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import math

# Initialize all session state variables with proper defaults
def initialize_session_state():
    default_state = {
        'results': None,
        'compare_mode': False,
        'calculation_mode': "Client Rate",
        'status': "Inside IR35",
        'working_days': 0,
        'employer_pension_percent': 3.0,
        'employee_pension': 5.0,
        'student_loan': "None",
        'days_per_week': 5,
        'start_date': datetime.today().date(),
        'end_date': (datetime.today() + timedelta(days=180)).date(),
        'vat_registered': False,
        'client_rate': 800,
        'base_rate': 500,
        'pay_rate': 400,
        'margin_percent': 23.0,
        'inside_pay_rate': 400,
        'outside_base_rate': 500,
        'outside_vat': False
    }
    
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# UK Bank Holidays API
def get_uk_bank_holidays():
    try:
        response = requests.get('https://www.gov.uk/bank-holidays.json')
        data = response.json()
        england_holidays = data['england-and-wales']['events']
        return [datetime.strptime(event['date'], '%Y-%m-%d').date() for event in england_holidays]
    except:
        # Fallback to 2023 holidays if API fails
        return [
            datetime(2023, 1, 2).date(), datetime(2023, 4, 7).date(), 
            datetime(2023, 4, 10).date(), datetime(2023, 5, 1).date(),
            datetime(2023, 5, 8).date(), datetime(2023, 5, 29).date(),
            datetime(2023, 8, 28).date(), datetime(2023, 12, 25).date(),
            datetime(2023, 12, 26).date()
        ]

def calculate_working_days(start_date, end_date, days_per_week, bank_holidays):
    if start_date >= end_date:
        return 0
    
    total_days = (end_date - start_date).days + 1
    working_days = 0
    
    for day in range(total_days):
        current_date = start_date + timedelta(days=day)
        if current_date.weekday() < 5 and current_date not in bank_holidays:
            working_days += 1
    
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    adjusted_working_days = (full_weeks * days_per_week) + min(remaining_days, days_per_week)
    
    return adjusted_working_days

# [Keep all your existing calculation functions unchanged...]
# (calculate_holiday_components, calculate_base_rate, calculate_client_rate, 
#  calculate_pay_rate, calculate_base_rate_from_pay, calculate_employer_deductions,
#  calculate_margin, ir35_tax_calculator, generate_pdf)

# Streamlit App Configuration
st.set_page_config(page_title="IR35 Tax Calculator", layout="wide")

# Add company logo
try:
    logo = Image.open("B2e Logo.png")
    st.image(logo, width=200)
except:
    st.write("")  # Skip if logo not found

st.title("IR35 Tax Calculator")

# Get UK bank holidays
bank_holidays = get_uk_bank_holidays()

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        # IR35 Status Selection
        st.session_state.status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            index=0 if st.session_state.status == "Inside IR35" else 1,
            horizontal=True,
            key="status_radio"
        )
        
        # Calculation Mode Selection
        st.session_state.calculation_mode = st.radio(
            "Start Calculation From:",
            ["Client Rate", "Base Rate", "Pay Rate"],
            index=["Client Rate", "Base Rate", "Pay Rate"].index(st.session_state.calculation_mode),
            horizontal=True,
            key="calculation_mode_radio"
        )
        
        # Dynamic inputs based on calculation mode
        if st.session_state.calculation_mode == "Client Rate":
            st.session_state.client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0, 
                value=st.session_state.client_rate,
                step=50,
                key="client_rate_input"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            base_rate = calculate_base_rate(st.session_state.client_rate, st.session_state.margin_percent)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            
        elif st.session_state.calculation_mode == "Base Rate":
            st.session_state.base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0, 
                value=st.session_state.base_rate,
                step=50,
                key="base_rate_input"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            client_rate = calculate_client_rate(st.session_state.base_rate, st.session_state.margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
            
        else:  # Pay Rate
            st.session_state.pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=st.session_state.pay_rate,
                step=50,
                key="pay_rate_input"
            )
            base_rate = calculate_base_rate_from_pay(st.session_state.pay_rate)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            client_rate = calculate_client_rate(base_rate, st.session_state.margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
        
        # Common inputs
        st.session_state.days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=st.session_state.days_per_week - 1,
            key="days_per_week_select"
        )
        
        st.session_state.start_date = st.date_input(
            "Project Start Date:",
            value=st.session_state.start_date,
            key="start_date_input"
        )
        
        st.session_state.end_date = st.date_input(
            "Project End Date:",
            value=st.session_state.end_date,
            key="end_date_input"
        )
        
    with col2:
        # Calculate working days
        working_days = calculate_working_days(
            st.session_state.start_date, 
            st.session_state.end_date, 
            st.session_state.days_per_week, 
            bank_holidays
        )
        st.session_state.working_days = working_days
        st.write(f"**Calculated Working Days:** {working_days}")
        
        # Pay Rate input when not in Pay Rate mode
        if st.session_state.calculation_mode != "Pay Rate":
            st.session_state.pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=round(calculate_pay_rate(base_rate)) if 'base_rate' in locals() else st.session_state.pay_rate,
                step=50,
                key="pay_rate_derived"
            )
        
        if st.session_state.status == "Inside IR35":
            st.session_state.employee_pension = st.number_input(
                "Employee Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employee_pension,
                step=0.5,
                key="employee_pension_input"
            )
            
            st.session_state.employer_pension_percent = st.number_input(
                "Employer Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employer_pension_percent,
                step=0.5,
                key="employer_pension_input"
            )
            
            st.session_state.student_loan = st.selectbox(
                "Student Loan Plan:", 
                ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                index=["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"].index(st.session_state.student_loan),
                key="student_loan_select"
            )
        else:
            # Use a different approach for the VAT checkbox to avoid session state issues
            vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=st.session_state.vat_registered,
                key="vat_registered_checkbox"
            )
            st.session_state.vat_registered = vat_registered
    
    submitted = st.form_submit_button("Calculate")
    
    if submitted:
        if st.session_state.start_date >= st.session_state.end_date:
            st.error("End date must be after start date")
        else:
            try:
                # Calculate and store results
                results = ir35_tax_calculator(
                    st.session_state.pay_rate,
                    st.session_state.working_days,
                    st.session_state.employee_pension,
                    st.session_state.student_loan,
                    st.session_state.status,
                    st.session_state.vat_registered if st.session_state.status == "Outside IR35" else False
                )
                
                st.session_state.results = results
                
                if st.session_state.status == "Inside IR35":
                    base_rate = calculate_base_rate_from_pay(st.session_state.pay_rate)
                    st.session_state.employer_deductions = calculate_employer_deductions(base_rate, st.session_state.working_days)
                    st.session_state.margin = calculate_margin(
                        st.session_state.client_rate if st.session_state.calculation_mode == "Client Rate" else client_rate,
                        base_rate,
                        st.session_state.working_days
                    )
            except Exception as e:
                st.error(f"An error occurred during calculation: {str(e)}")

# [Rest of your code for results display, comparison mode, etc.]
# Make sure to use st.session_state for all variables
