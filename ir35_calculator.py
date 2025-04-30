import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import math

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'compare_mode' not in st.session_state:
    st.session_state.compare_mode = False

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
    total_days = (end_date - start_date).days + 1
    working_days = 0
    
    for day in range(total_days):
        current_date = start_date + timedelta(days=day)
        # Check if it's a weekday (0=Monday, 6=Sunday)
        if current_date.weekday() < 5 and current_date not in bank_holidays:
            working_days += 1
    
    # Adjust for partial weeks based on days_per_week
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    adjusted_working_days = (full_weeks * days_per_week) + min(remaining_days, days_per_week)
    
    return adjusted_working_days

def calculate_base_rate(client_rate, margin_percent):
    """Calculate Base Rate from Client Rate and margin"""
    return client_rate * (1 - margin_percent/100)

def calculate_client_rate(base_rate, margin_percent):
    """Calculate Client Rate from Base Rate and margin"""
    return base_rate / (1 - margin_percent/100)

def calculate_pay_rate(base_rate, employer_ni_percent=15, employer_pension_percent=3, apprentice_levy_percent=0.5):
    """Calculate Pay Rate from Base Rate with employer deductions"""
    total_deductions = (employer_ni_percent + employer_pension_percent + apprentice_levy_percent) / 100
    return base_rate * (1 - total_deductions)

def calculate_base_rate_from_pay(pay_rate, employer_ni_percent=15, employer_pension_percent=3, apprentice_levy_percent=0.5):
    """Calculate Base Rate from Pay Rate"""
    total_deductions = (employer_ni_percent + employer_pension_percent + apprentice_levy_percent) / 100
    return pay_rate / (1 - total_deductions)

def ir35_tax_calculator(pay_rate, working_days, pension_contribution_percent=0, 
                       student_loan_plan="None", status="Inside IR35", vat_registered=False):
    """Calculate take-home pay for consultants inside or outside IR35."""
    
    annual_income = pay_rate * working_days
    
    # VAT Calculation (only outside IR35)
    if status == "Outside IR35" and vat_registered:
        vat_amount = annual_income * 0.2
    else:
        vat_amount = 0
    
    personal_allowance = 12570  # Tax-free allowance (2024/25)
    basic_rate_threshold = 50270
    higher_rate_threshold = 125140
    
    # Tax bands
    basic_rate = 0.2
    higher_rate = 0.4
    additional_rate = 0.45
    
    # National Insurance (NI) - Employee only
    ni_threshold = 12570
    ni_lower = 0.08  # 8% for earnings above £12,570
    ni_upper = 0.02  # 2% for earnings above £50,270
    
    # Pension Contributions
    employee_pension = annual_income * (pension_contribution_percent / 100)
    
    # Income Tax Calculation
    taxable_income = annual_income - employee_pension
    if taxable_income <= personal_allowance:
        income_tax = 0
    elif taxable_income <= basic_rate_threshold:
        income_tax = (taxable_income - personal_allowance) * basic_rate
    elif taxable_income <= higher_rate_threshold:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((taxable_income - basic_rate_threshold) * higher_rate)
    else:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((higher_rate_threshold - basic_rate_threshold) * higher_rate) + ((taxable_income - higher_rate_threshold) * additional_rate)
    
    # National Insurance (NI) Calculation - Employee only
    if annual_income <= ni_threshold:
        ni_contribution = 0
    elif annual_income <= basic_rate_threshold:
        ni_contribution = (annual_income - ni_threshold) * ni_lower
    else:
        ni_contribution = ((basic_rate_threshold - ni_threshold) * ni_lower) + ((annual_income - basic_rate_threshold) * ni_upper)
    
    # Student Loan Calculation
    student_loan_repayment = 0
    if student_loan_plan == "Plan 1" and annual_income > 22015:
        student_loan_repayment = (annual_income - 22015) * 0.09
    elif student_loan_plan == "Plan 2" and annual_income > 27295:
        student_loan_repayment = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Plan 4" and annual_income > 31395:
        student_loan_repayment = (annual_income - 31395) * 0.09
    elif student_loan_plan == "Plan 5" and annual_income > 27295:
        student_loan_repayment = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Postgraduate Loan" and annual_income > 21000:
        student_loan_repayment = (annual_income - 21000) * 0.06
    
    # Final Take-Home Pay Calculation
    take_home_pay = annual_income - (income_tax + ni_contribution + student_loan_repayment + employee_pension)
    
    return {
        "Gross Income": annual_income,
        "Employee Pension": employee_pension,
        "Income Tax": income_tax,
        "Employee NI": ni_contribution,
        "Student Loan Repayment": student_loan_repayment,
        "Net Take-Home Pay": take_home_pay,
        "VAT Amount": vat_amount,
        "Working Days": working_days
    }

def generate_pdf(result):
    """Generate PDF report"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Main title
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(200, 10, "IR35 Tax Calculation Results", ln=True, align='C')
    pdf.ln(10)
    
    # Results section
    pdf.set_font("Arial", size=11)
    for key, value in result.items():
        if key not in ["VAT Amount"] or (key == "VAT Amount" and value > 0):
            pdf.cell(200, 8, f"{key}: £{value:,.2f}", ln=True)
    
    return pdf.output(dest='S').encode('latin1')

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

# Calculation Mode Selection
calculation_mode = st.radio(
    "Start Calculation From:",
    ["Client Rate", "Base Rate", "Pay Rate"],
    horizontal=True
)

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        # Dynamic inputs based on calculation mode
        if calculation_mode == "Client Rate":
            client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0.0, 
                value=800.0,
                step=10.0,
                help="The rate charged to the client"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=10.0,
                help="Your company's margin percentage"
            )
            base_rate = calculate_base_rate(client_rate, margin_percent)
            st.write(f"**Calculated Base Rate:** £{base_rate:,.2f}")
            
        elif calculation_mode == "Base Rate":
            base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0.0, 
                value=500.0,
                step=10.0,
                help="The rate after margin deduction"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=10.0,
                help="Your company's margin percentage"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{client_rate:,.2f}")
            
        else:  # Pay Rate
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0.0, 
                value=400.0,
                step=10.0,
                help="The rate paid to consultant before employee deductions"
            )
            base_rate = calculate_base_rate_from_pay(pay_rate)
            st.write(f"**Calculated Base Rate:** £{base_rate:,.2f}")
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=10.0,
                help="Your company's margin percentage"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{client_rate:,.2f}")
        
        # Common inputs
        days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=4,
            help="Number of days worked each week"
        )
        
        start_date = st.date_input(
            "Project Start Date:",
            value=datetime.today(),
            min_value=datetime.today() - timedelta(days=365),
            max_value=datetime.today() + timedelta(days=365*3)
        )
        
        end_date = st.date_input(
            "Project End Date:",
            value=datetime.today() + timedelta(days=90),
            min_value=datetime.today(),
            max_value=datetime.today() + timedelta(days=365*3)
        )
        
    with col2:
        # Calculate working days
        if start_date and end_date:
            working_days = calculate_working_days(start_date, end_date, days_per_week, bank_holidays)
            st.write(f"**Calculated Working Days:** {working_days}")
        else:
            working_days = 0
        
        # Only show Pay Rate input if not already the starting point
        if calculation_mode != "Pay Rate":
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0.0, 
                value=calculate_pay_rate(base_rate) if 'base_rate' in locals() else 400.0,
                step=10.0,
                help="The rate paid to consultant before employee deductions",
                disabled=calculation_mode != "Pay Rate"
            )
        
        pension_contribution_percent = st.number_input(
            "Employee Pension Contribution (%):", 
            min_value=0.0, 
            value=0.0,
            help="Percentage of salary going to your pension"
        )
        
        student_loan_plan = st.selectbox(
            "Student Loan Plan:", 
            ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
            help="Select your student loan repayment plan"
        )
        
        status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            help="Inside: Treated as employee. Outside: Self-employed"
        )
        
        if status == "Outside IR35":
            vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=False,
                help="Check if you're VAT registered (outside IR35 only)"
            )
        else:
            vat_registered = False
    
    # Submit button for the form
    submitted = st.form_submit_button("Calculate")
    
    if submitted:
        if start_date >= end_date:
            st.error("End date must be after start date")
        else:
            st.session_state.results = ir35_tax_calculator(
                pay_rate, working_days, pension_contribution_percent,
                student_loan_plan, status, vat_registered
            )
            st.session_state.calculation_mode = calculation_mode
            st.session_state.client_rate = client_rate if 'client_rate' in locals() else None
            st.session_state.base_rate = base_rate if 'base_rate' in locals() else None
            st.session_state.pay_rate = pay_rate
            st.session_state.working_days = working_days

# Results Display
if st.session_state.results:
    st.subheader("Results")
    
    # Rate Summary
    st.write("### Rate Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.session_state.calculation_mode == "Client Rate":
            st.metric("Client Rate", f"£{st.session_state.client_rate:,.2f}")
        else:
            st.metric("Calculated Client Rate", f"£{st.session_state.client_rate:,.2f}")
    with col2:
        if st.session_state.calculation_mode == "Base Rate":
            st.metric("Base Rate", f"£{st.session_state.base_rate:,.2f}")
        else:
            st.metric("Calculated Base Rate", f"£{st.session_state.base_rate:,.2f}")
    with col3:
        st.metric("Pay Rate", f"£{st.session_state.pay_rate:,.2f}")
    
    # Time Period Breakdown
    st.write("### Project Breakdown")
    days_in_month = 20  # Standard assumption
    
    # Daily rates
    daily_gross = st.session_state.pay_rate
    daily_net = st.session_state.results["Net Take-Home Pay"] / st.session_state.working_days
    
    # Monthly rates (20 working days)
    monthly_gross = daily_gross * days_in_month
    monthly_net = daily_net * days_in_month
    
    # Project totals
    project_gross = daily_gross * st.session_state.working_days
    project_net = st.session_state.results["Net Take-Home Pay"]
    
    # Display in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Daily Rates**")
        st.write(f"Gross: £{daily_gross:,.2f}")
        st.write(f"Net: £{daily_net:,.2f}")
    with col2:
        st.write("**Monthly Rates (20 days)**")
        st.write(f"Gross: £{monthly_gross:,.2f}")
        st.write(f"Net: £{monthly_net:,.2f}")
    with col3:
        st.write(f"**Project Total ({st.session_state.working_days} days)**")
        st.write(f"Gross: £{project_gross:,.2f}")
        st.write(f"Net: £{project_net:,.2f}")
    
    # Detailed Breakdown
    st.write("### Detailed Breakdown")
    for key, value in st.session_state.results.items():
        if key not in ["VAT Amount", "Working Days"] or (key == "VAT Amount" and value > 0):
            st.write(f"**{key}:** £{value:,.2f}")
    
    # Generate Report Button
    if st.button("Generate PDF Report"):
        pdf_data = generate_pdf(st.session_state.results)
        st.download_button(
            "Download Report",
            data=pdf_data,
            file_name="IR35_Tax_Report.pdf",
            mime="application/pdf"
        )

# Comparison Mode
st.subheader("Comparison Mode")
compare = st.checkbox("Enable Comparison Mode")

if compare:
    st.info("""
    **Comparison Explanation**: 
    This compares Inside vs Outside IR35 scenarios. 
    - Inside IR35: Pay Rate is after employer deductions (NI 15%, Pension 3%, Levy 0.5%)
    - Outside IR35: Pay Rate equals Base Rate (no employer deductions)
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Scenario 1 - Inside IR35**")
        inside_pay_rate = st.number_input("Pay Rate (£)", key="inside_pay_rate", value=400.0)
    
    with col2:
        st.write("**Scenario 2 - Outside IR35**")
        outside_base_rate = st.number_input("Base Rate (£)", key="outside_base_rate", value=500.0)
        outside_vat = st.checkbox("VAT Registered?", key="outside_vat", value=False)
    
    if st.button("Compare Scenarios"):
        # Calculate working days for comparison
        working_days = calculate_working_days(start_date, end_date, days_per_week, bank_holidays)
        
        # Inside IR35 scenario
        inside_result = ir35_tax_calculator(
            inside_pay_rate, working_days, pension_contribution_percent,
            student_loan_plan, "Inside IR35", False
        )
        
        # Outside IR35 scenario (Pay Rate = Base Rate)
        outside_result = ir35_tax_calculator(
            outside_base_rate, working_days, pension_contribution_percent,
            student_loan_plan, "Outside IR35", outside_vat
        )
        
        # Display comparison
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Inside IR35")
            st.write(f"**Pay Rate:** £{inside_pay_rate:,.2f}")
            st.write(f"**Daily Net:** £{inside_result['Net Take-Home Pay']/working_days:,.2f}")
            st.write(f"**Monthly Net (20 days):** £{inside_result['Net Take-Home Pay']/working_days*20:,.2f}")
            st.write(f"**Project Net:** £{inside_result['Net Take-Home Pay']:,.2f}")
        
        with col2:
            st.write("### Outside IR35")
            st.write(f"**Base Rate:** £{outside_base_rate:,.2f}")
            st.write(f"**Daily Net:** £{outside_result['Net Take-Home Pay']/working_days:,.2f}")
            st.write(f"**Monthly Net (20 days):** £{outside_result['Net Take-Home Pay']/working_days*20:,.2f}")
            st.write(f"**Project Net:** £{outside_result['Net Take-Home Pay']:,.2f}")
        
        # Difference calculation
        difference = outside_result['Net Take-Home Pay'] - inside_result['Net Take-Home Pay']
        st.write(f"**Difference (Outside - Inside):** £{difference:,.2f}")
