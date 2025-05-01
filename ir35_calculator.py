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
        if current_date.weekday() < 5 and current_date not in bank_holidays:
            working_days += 1
    
    # Adjust for partial weeks based on days_per_week
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    adjusted_working_days = (full_weeks * days_per_week) + min(remaining_days, days_per_week)
    
    return adjusted_working_days

def calculate_holiday_components(pay_rate):
    """Calculate Basic Daily Rate and Holiday Pay from Pay Rate"""
    basic_daily_rate = pay_rate / (1 + 0.1454)  # 14.54% holiday pay
    holiday_pay = pay_rate - basic_daily_rate
    return round(basic_daily_rate), round(holiday_pay)

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

def ir35_tax_calculator(pay_rate, working_days, pension_contribution_percent=5, 
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
    
    # Round all values to nearest whole number
    return {
        "Gross Income": round(annual_income),
        "Employee Pension": round(employee_pension),
        "Income Tax": round(income_tax),
        "Employee NI": round(ni_contribution),
        "Student Loan Repayment": round(student_loan_repayment),
        "Net Take-Home Pay": round(take_home_pay),
        "VAT Amount": round(vat_amount),
        "Working Days": working_days
    }

def generate_pdf(result, calculation_mode, client_rate=None, base_rate=None, pay_rate=None):
    """Generate PDF report with all results and disclaimer"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Main title
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, "IR35 Tax Calculation Results", ln=True, align='C')
    pdf.ln(10)
    
    # Rate Summary
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Rate Summary", ln=True)
    pdf.set_font("Arial", size=11)
    
    if calculation_mode == "Client Rate":
        pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
        pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
    elif calculation_mode == "Base Rate":
        pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
        pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
    else:
        pdf.cell(200, 8, f"Pay Rate: £{round(pay_rate)}", ln=True)
        pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
        pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
    
    pdf.ln(5)
    
    # Project Breakdown
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Project Breakdown", ln=True)
    pdf.set_font("Arial", size=11)
    
    daily_gross = pay_rate
    daily_net = result["Net Take-Home Pay"] / result["Working Days"]
    monthly_gross = daily_gross * 20
    monthly_net = daily_net * 20
    
    pdf.cell(200, 8, f"Working Days: {result['Working Days']}", ln=True)
    pdf.cell(200, 8, f"Daily Gross: £{round(daily_gross)}", ln=True)
    pdf.cell(200, 8, f"Daily Net: £{round(daily_net)}", ln=True)
    pdf.cell(200, 8, f"Monthly Gross (20 days): £{round(monthly_gross)}", ln=True)
    pdf.cell(200, 8, f"Monthly Net (20 days): £{round(monthly_net)}", ln=True)
    pdf.cell(200, 8, f"Project Gross Total: £{round(result['Gross Income'])}", ln=True)
    pdf.cell(200, 8, f"Project Net Total: £{round(result['Net Take-Home Pay'])}", ln=True)
    
    # Payslip Breakdown
    basic_rate, holiday_pay = calculate_holiday_components(pay_rate)
    pdf.ln(5)
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Payslip Breakdown (Compliance)", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 8, f"Basic Daily Rate (excl. holiday pay): £{basic_rate}", ln=True)
    pdf.cell(200, 8, f"Holiday Pay (per day): £{holiday_pay}", ln=True)
    
    # Detailed Breakdown
    pdf.ln(5)
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Detailed Breakdown", ln=True)
    pdf.set_font("Arial", size=11)
    
    pdf.cell(200, 8, f"Gross Income: £{result['Gross Income']}", ln=True)
    pdf.cell(200, 8, f"Income Tax: £{result['Income Tax']}", ln=True)
    pdf.cell(200, 8, f"Employee NI: £{result['Employee NI']}", ln=True)
    pdf.cell(200, 8, f"Employee Pension: £{result['Employee Pension']}", ln=True)
    if result['Student Loan Repayment'] > 0:
        pdf.cell(200, 8, f"Student Loan Repayment: £{result['Student Loan Repayment']}", ln=True)
    if result['VAT Amount'] > 0:
        pdf.cell(200, 8, f"VAT Amount: £{result['VAT Amount']}", ln=True)
    
    # Disclaimer
    pdf.ln(10)
    pdf.set_font("Arial", size=8)
    pdf.set_text_color(128, 128, 128)  # Grey color
    pdf.cell(200, 8, "**Disclaimer:**", ln=True)
    pdf.multi_cell(190, 5, "The figures provided are for illustrative purposes only and may vary significantly depending on the consultant's individual tax code, year-to-date earnings, and other personal financial circumstances. This tool is not intended to provide tax, legal, or accounting advice and should not be relied upon for official tax filing or decision-making. No liability is accepted for any inaccuracies or decisions made based on this information. Users are strongly advised to seek independent professional advice tailored to their situation.")
    
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

# Set default dates
today = datetime.today().date()
default_end_date = today + timedelta(days=180)  # 6 months from today

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        # Dynamic inputs based on calculation mode
        if calculation_mode == "Client Rate":
            client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0, 
                value=800,
                step=50,
                help="The rate charged to the client"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage"
            )
            base_rate = calculate_base_rate(client_rate, margin_percent)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            
        elif calculation_mode == "Base Rate":
            base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0, 
                value=500,
                step=50,
                help="The rate after margin deduction"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
            
        else:  # Pay Rate
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=400,
                step=50,
                help="The rate paid to consultant before employee deductions"
            )
            base_rate = calculate_base_rate_from_pay(pay_rate)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
        
        # Common inputs
        days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=4,
            help="Number of days worked each week"
        )
        
        start_date = st.date_input(
            "Project Start Date:",
            value=today,
            min_value=today - timedelta(days=365),
            max_value=today + timedelta(days=365*3)
        )
        
        end_date = st.date_input(
            "Project End Date:",
            value=default_end_date,
            min_value=today,
            max_value=today + timedelta(days=365*3)
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
                min_value=0, 
                value=round(calculate_pay_rate(base_rate)) if 'base_rate' in locals() else 400,
                step=50,
                help="The rate paid to consultant before employee deductions",
                disabled=calculation_mode != "Pay Rate"
            )
        
        pension_contribution_percent = st.number_input(
            "Employee Pension Contribution (%):", 
            min_value=0.0, 
            value=5.0,
            step=0.5,
            help="Percentage of salary going to your pension"
        )
        
        employer_pension_percent = st.number_input(
            "Employer Pension Contribution (%):", 
            min_value=0.0, 
            value=3.0,
            step=0.5,
            help="Standard UK employer contribution is 3%+"
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
            st.metric("Client Rate", f"£{round(st.session_state.client_rate)}")
        else:
            st.metric("Calculated Client Rate", f"£{round(st.session_state.client_rate)}")
    with col2:
        if st.session_state.calculation_mode == "Base Rate":
            st.metric("Base Rate", f"£{round(st.session_state.base_rate)}")
        else:
            st.metric("Calculated Base Rate", f"£{round(st.session_state.base_rate)}")
    with col3:
        st.metric("Pay Rate", f"£{round(st.session_state.pay_rate)}")
    
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
        st.write(f"Gross: £{round(daily_gross)}")
        st.write(f"Net: £{round(daily_net)}")
    with col2:
        st.write("**Monthly Rates (20 days)**")
        st.write(f"Gross: £{round(monthly_gross)}")
        st.write(f"Net: £{round(monthly_net)}")
    with col3:
        st.write(f"**Project Total ({st.session_state.working_days} days)**")
        st.write(f"Gross: £{round(project_gross)}")
        st.write(f"Net: £{round(project_net)}")
    
    # Payslip Breakdown
    basic_rate, holiday_pay = calculate_holiday_components(st.session_state.pay_rate)
    st.write("### Payslip Breakdown (Compliance)")
    st.write(f"**Basic Daily Rate (excl. holiday pay):** £{basic_rate}")
    st.write(f"**Holiday Pay (per day):** £{holiday_pay}")
    st.caption("Note: These values are for compliance purposes only and not used in negotiations.")
    
    # Detailed Breakdown
    st.write("### Detailed Breakdown")
    for key, value in st.session_state.results.items():
        if key not in ["VAT Amount", "Working Days"] or (key == "VAT Amount" and value > 0):
            st.write(f"**{key}:** £{value}")
    
    # Generate Report Button
    if st.button("Generate PDF Report"):
        pdf_data = generate_pdf(
            st.session_state.results,
            st.session_state.calculation_mode,
            st.session_state.client_rate,
            st.session_state.base_rate,
            st.session_state.pay_rate
        )
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
        inside_pay_rate = st.number_input(
            "Pay Rate (£)", 
            key="inside_pay_rate", 
            value=400,
            step=50
        )
    
    with col2:
        st.write("**Scenario 2 - Outside IR35**")
        outside_base_rate = st.number_input(
            "Base Rate (£)", 
            key="outside_base_rate", 
            value=500,
            step=50
        )
        outside_vat = st.checkbox(
            "VAT Registered?", 
            key="outside_vat", 
            value=False
        )
    
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
            st.write(f"**Pay Rate:** £{round(inside_pay_rate)}")
            st.write(f"**Daily Net:** £{round(inside_result['Net Take-Home Pay']/working_days)}")
            st.write(f"**Monthly Net (20 days):** £{round(inside_result['Net Take-Home Pay']/working_days*20)}")
            st.write(f"**Project Net:** £{round(inside_result['Net Take-Home Pay'])}")
        
        with col2:
            st.write("### Outside IR35")
            st.write(f"**Base Rate:** £{round(outside_base_rate)}")
            st.write(f"**Daily Net:** £{round(outside_result['Net Take-Home Pay']/working_days)}")
            st.write(f"**Monthly Net (20 days):** £{round(outside_result['Net Take-Home Pay']/working_days*20)}")
            st.write(f"**Project Net:** £{round(outside_result['Net Take-Home Pay'])}")
        
        # Difference calculation
        difference = outside_result['Net Take-Home Pay'] - inside_result['Net Take-Home Pay']
        st.write(f"**Difference (Outside - Inside):** £{round(difference)}")
